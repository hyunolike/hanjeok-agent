"""Local immutable-index commands; never deploy or switch cloud traffic."""
import argparse,json
from .index import build_index
from .lifecycle import validate_candidate,publish,rollback

def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
 b=s.add_parser('build');b.add_argument('--agent',required=True);b.add_argument('--wiki',required=True);b.add_argument('--destination',required=True);b.add_argument('--backend',choices=('tfidf','semantic'),default='tfidf');b.add_argument('--model-path')
 v=s.add_parser('validate');v.add_argument('--directory',required=True);v.add_argument('--version',required=True);v.add_argument('--agent',required=True);v.add_argument('--model-path')
 for cmd in ('publish','rollback'):
  c=s.add_parser(cmd);c.add_argument('--registry',required=True);c.add_argument('--version',required=True)
  if cmd=='publish':c.add_argument('--directory',required=True)
 a=p.parse_args()
 if a.command=='build':print(build_index(a.agent,a.wiki,a.destination,a.backend,a.model_path))
 elif a.command=='validate':
  r=validate_candidate(a.directory,a.version,a.agent,a.model_path);print(json.dumps({k:r[k] for k in ('indexVersion','passed','fixtureCount')}))
 elif a.command=='publish':print(json.dumps({'active':publish(a.directory,a.version,a.registry)['active'],'runtimeAutomaticallyUpdated':False}))
 else:print(json.dumps({'active':rollback(a.registry,a.version)['active'],'runtimeAutomaticallyUpdated':False}))

if __name__=='__main__':main()
