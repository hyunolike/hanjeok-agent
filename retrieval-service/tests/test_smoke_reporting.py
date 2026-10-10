import json,runpy,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock,patch

class SmokeReportingTest(unittest.TestCase):
    def test_graph_load_only_does_not_claim_http_execution(self):
        script=Path(__file__).resolve().parents[2]/'deployment/retrieval/local-api-smoke.py'
        index=SimpleNamespace(identity={'indexVersion':'fixture'},snapshot=object())
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'proof.json'
            args=[str(script),'--index',temp,'--version','fixture','--output',str(output),'--load-owned-graph','--load-only']
            with patch.object(sys,'argv',args),patch('retrieval_service.index.load_index',return_value=index),patch('retrieval_lab.live.driver_for',return_value=MagicMock()),patch('retrieval_lab.live.components',return_value=['mock']),patch('retrieval_lab.live.load_snapshot'),patch('retrieval_lab.live.verify_snapshot',return_value={'mock':True}),patch('subprocess.check_output',return_value='hanjeok-retrieval-task8'),patch('urllib.request.urlopen',side_effect=AssertionError('load-only must not call HTTP')):
                with self.assertRaises(SystemExit) as stopped:runpy.run_path(str(script),run_name='__main__')
            self.assertEqual(stopped.exception.code,0)
            self.assertFalse(json.loads(output.read_text())['actualHttp'])

if __name__=='__main__':unittest.main()
