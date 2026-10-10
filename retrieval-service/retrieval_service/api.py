"""Minimal ASGI HTTP boundary: auth, streamed body cap, deadline, one admission slot."""
import asyncio,hmac,json,threading,ipaddress
from concurrent.futures import ThreadPoolExecutor
from .index import encoded,strict_json,load_index
from retrieval_lab.corpus import require

def private_test_network(value):
 network=ipaddress.ip_network(value,strict=True)
 require(network.version==4 and network.prefixlen>=16 and any(network.subnet_of(ipaddress.ip_network(n)) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')),'explicit narrow RFC1918 test network required')
 return network

class RetrievalApp:
 def __init__(self,engine,auth_mode,local_token='',platform_service='',deadline=2.0,test_network=''):
  require(auth_mode in ('loopback-test','isolated-container-test','cloud-run-iam'),'unknown auth mode')
  require(auth_mode not in ('loopback-test','isolated-container-test') or bool(local_token),'explicit local token required')
  require(auth_mode!='cloud-run-iam' or bool(platform_service),'Cloud Run platform required')
  self.test_network=private_test_network(test_network) if auth_mode=='isolated-container-test' else None
  require(auth_mode!='isolated-container-test' or not platform_service,'container test forbidden on cloud platform')
  self.engine,self.auth_mode,self.local_token,self.deadline=engine,auth_mode,local_token,deadline
  self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='retrieval');self.slot=threading.BoundedSemaphore(1)
  self.counts={'selected':0,'fallback':0,'abstain':0,'busy':0,'timeout':0,'error':0}
 async def close(self):self.pool.shutdown(wait=False,cancel_futures=True)
 async def reply(self,send,status,data):
  body=encoded(data)
  if len(body)>65536:status,body=503,encoded({'code':'RETRIEVAL_UNAVAILABLE'})
  await send({'type':'http.response.start','status':status,'headers':[(b'content-type',b'application/json; charset=utf-8'),(b'cache-control',b'no-store'),(b'content-length',str(len(body)).encode())]})
  await send({'type':'http.response.body','body':body})
 async def __call__(self,scope,receive,send):
  if scope['type']=='lifespan':
   while True:
    event=await receive()
    if event['type']=='lifespan.startup':await send({'type':'lifespan.startup.complete'})
    elif event['type']=='lifespan.shutdown':await self.close();await send({'type':'lifespan.shutdown.complete'});return
  if scope['type']!='http':return
  path,method=scope['path'],scope['method']
  headers={k.lower():v for k,v in scope.get('headers',[])}
  if path=='/health/live' and method=='GET':return await self.reply(send,200,{'status':'UP'})
  auth=headers.get(b'authorization',b'').decode('ascii',errors='ignore')
  if self.auth_mode=='loopback-test':
   authorized=scope.get('client',('',))[0] in ('127.0.0.1','::1') and hmac.compare_digest(auth,'Bearer '+self.local_token)
  elif self.auth_mode=='isolated-container-test':
   try:peer=ipaddress.ip_address(scope.get('client',('',))[0]);authorized=peer in self.test_network and hmac.compare_digest(auth,'Bearer '+self.local_token)
   except ValueError:authorized=False
  else:
   # Platform IAM validates the token before delivery. This is not JWT verification.
   authorized=auth.startswith('Bearer ') and len(auth)>10
  if not authorized:return await self.reply(send,401,{'code':'UNAUTHORIZED'})
  if path in ('/health/ready','/v1/provenance') and method=='GET':
   if not self.slot.acquire(blocking=False):return await self.reply(send,503,{'status':'BUSY'})
   def check_ready():
    try:
     load_index(self.engine.index.root,self.engine.index.version)
     if self.engine.index.vector.backend=='semantic':require(self.engine.index.vector.model is not None,'model unavailable')
     if self.engine.graph is not None and hasattr(self.engine.graph,'driver'):
      self.engine.graph.driver.verify_connectivity()
      actual=self.engine.graph.expand(tuple('document:'+p for p in self.engine.index.corpus.evidence_ids),limit=9)
      require(set(actual)==set(self.engine.index.corpus.evidence_ids),'graph integrity/namespace drift')
    finally:self.slot.release()
   future=self.pool.submit(check_ready)
   try:await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)),timeout=self.deadline)
   except Exception:return await self.reply(send,503,{'status':'DOWN'})
   return await self.reply(send,200,dict(status='UP',identity=self.engine.index.identity,graph=('neo4j' if hasattr(self.engine.graph,'driver') else 'in_process_contract') if self.engine.graph is not None else 'disabled',authBoundary=self.auth_mode,reviewTruthVerified=False,counters=dict(self.counts)))
  if path!='/v1/retrieve':return await self.reply(send,404,{'code':'NOT_FOUND'})
  if method!='POST':return await self.reply(send,405,{'code':'METHOD_NOT_ALLOWED'})
  if headers.get(b'content-type',b'').split(b';')[0]!=b'application/json':return await self.reply(send,400,{'code':'INVALID_REQUEST'})
  started=asyncio.get_running_loop().time()
  try:
   length=int(headers.get(b'content-length',b'0'));require(0<=length<=8192,'body cap');body=bytearray()
   async with asyncio.timeout(self.deadline):
    while True:
     event=await receive();require(event['type']=='http.request','disconnected request');require(len(body)+len(event.get('body',b''))<=8192,'body cap');body.extend(event.get('body',b''))
     if not event.get('more_body'):break
   r=strict_json(body);self.engine.validate(r)
  except TimeoutError:return await self.reply(send,408,{'code':'REQUEST_TIMEOUT'})
  except Exception:
   status=409 if isinstance(locals().get('r'),dict) and r.get('identity')!=self.engine.index.identity else 400
   return await self.reply(send,status,{'code':'INVALID_REQUEST'})
  if not self.slot.acquire(blocking=False):self.counts['busy']+=1;return await self.reply(send,429,{'code':'BUSY'})
  def work():
   try:return self.engine.retrieve(r)
   finally:self.slot.release()
  future=self.pool.submit(work)
  try:
   result=await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)),timeout=max(.001,self.deadline-(asyncio.get_running_loop().time()-started)))
   self.counts[result['status']]+=1;return await self.reply(send,200,result)
  except TimeoutError:self.counts['timeout']+=1;return await self.reply(send,504,{'code':'RETRIEVAL_TIMEOUT'})
  except Exception:self.counts['error']+=1;return await self.reply(send,503,{'code':'RETRIEVAL_UNAVAILABLE'})

def create_app(engine,auth_mode='loopback-test',local_token='',platform_service='',deadline=2.0,test_network=''):
 return RetrievalApp(engine,auth_mode,local_token,platform_service,deadline,test_network)
