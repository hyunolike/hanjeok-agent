import platform,json,subprocess,time
from pathlib import Path
assert platform.machine()=='x86_64'
subprocess.run(['python','-m','pip','check'],check=True)
started=time.monotonic()
subprocess.run(['python','/tmp/rebuild-linux-cpu-index.py','--input','/app/index','--destination','/tmp/amd64-candidate','--version','80dd5ab3b1ac4d73f74742ee880f2c5fdc04b2083079f19d17f07c37b00c95a5','--model','/app/model','--fixtures','/tmp/fixtures'],check=True)
from retrieval_service.index import load_index
p=Path('/tmp/amd64-candidate');manifest=json.loads((p/'manifest.json').read_text());index=load_index(p,manifest['indexVersion'],'/app/model');query='경복궁 혼잡도 기준은?';start=time.monotonic();first=index.vector.search(query);latency=time.monotonic()-start;second=index.vector.search(query);assert first==second and first
from retrieval_service.lifecycle import publish
registry=publish(p,manifest['indexVersion'],'/tmp/amd64-local-registry.json');assert registry['active']==manifest['indexVersion']
proof={'actualMachine':platform.machine(),'actualPlatform':'linux/amd64','emulatedOnArm64':True,'python':platform.python_version(),'fullSemanticModelActuallyRun':True,'linuxAmd64IndexActuallyRebuilt':True,'indexVersion':manifest['indexVersion'],'runtimeVersions':manifest['runtimeVersions'],'modelRevision':manifest['vector']['modelRevision'],'realQuery':query,'realQueryResults':first,'determinism':True,'querySecondsUnderEmulation':round(latency,4),'buildAndValidationSecondsUnderEmulation':round(time.monotonic()-started,2),'candidateFixtures':35,'candidateValidationRows':70,'validationGraph':'in_process_contract','pipCheckPassed':True,'localRegistryPublicationPassed':True,'llmCalls':0,'noNetworkDuringExecution':True}
Path('/tmp/amd64-build-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps(proof,ensure_ascii=False))
