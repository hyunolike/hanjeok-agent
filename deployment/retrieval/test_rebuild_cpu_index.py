import unittest,tempfile,json,importlib.util
from pathlib import Path
SCRIPT=Path(__file__).with_name('rebuild-linux-cpu-index.py')
spec=importlib.util.spec_from_file_location('rebuild',SCRIPT);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
from retrieval_service.index import encoded
from retrieval_lab.corpus import digest
class CpuCandidateGuardTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'bundle.txt').write_text('public fixture')
  self.old={'numpy':'2.2.6','scikit-learn':'1.7.2','neo4j':'5.26.0','sentence-transformers':'6.1.0','transformers':'5.19.0','torch':'2.14.1'};self.current=dict(self.old,torch='2.14.1+cpu')
  self.m={'files':{'bundle.txt':digest((self.root/'bundle.txt').read_bytes())},'runtimeVersions':self.old,'vector':{'backend':'semantic','modelRevision':module.MODEL_REVISION}}
  self.save()
 def save(self):
  self.version=digest(encoded(self.m));(self.root/'manifest.json').write_bytes(encoded(dict(self.m,indexVersion=self.version)))
 def verify(self):return module.verify_input(self.root,self.version,self.current)
 def test_nested_destination_rejected_before_model_load(self):
  with self.assertRaisesRegex(ValueError,'destination inside input'):module.rebuild(self.root,self.root/'nested',self.version,'unused','unused')
 def model_fixture(self):
  model=self.root/'model';model.mkdir();(model/'weights.safetensors').write_bytes(b'public fixture bytes')
  pin={'modelId':'fixed-model','revision':module.MODEL_REVISION,'files':{'weights.safetensors':digest(b'public fixture bytes')}}
  (self.root/'model.json').write_bytes(encoded(pin));(model/'retrieval-model-manifest.json').write_bytes(encoded(pin));return model,pin
 def test_exact_model_file_map_accepted(self):
  model,pin=self.model_fixture();module.verify_model(self.root,model)
 def test_self_labelled_changed_model_map_rejected(self):
  model,pin=self.model_fixture();pin['files']['weights.safetensors']=digest(b'other bytes');(model/'weights.safetensors').write_bytes(b'other bytes');(model/'retrieval-model-manifest.json').write_bytes(encoded(pin))
  with self.assertRaisesRegex(ValueError,'model source pin'):module.verify_model(self.root,model)
 def test_changed_model_bytes_rejected(self):
  model,pin=self.model_fixture();(model/'weights.safetensors').write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'model artifact hash drift'):module.verify_model(self.root,model)
 def test_existing_output_is_preserved(self):
  destination=self.root/'existing';destination.mkdir();sentinel=destination/'keep';sentinel.write_text('other writer')
  with self.assertRaises(FileExistsError):module.copy_candidate(self.root,destination)
  self.assertEqual(sentinel.read_text(),'other writer')
 def test_verified_exact_cpu_variant(self):self.assertEqual(self.verify()['runtimeVersions'],self.old)
 def test_tampered_bytes_rejected(self):
  (self.root/'bundle.txt').write_text('changed')
  with self.assertRaisesRegex(ValueError,'hash drift'):self.verify()
 def test_extra_artifact_rejected(self):
  (self.root/'extra.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'inventory'):self.verify()
 def test_wrong_expected_identity_rejected(self):
  with self.assertRaisesRegex(ValueError,'identity'):module.verify_input(self.root,'0'*64,self.current)
 def test_other_dependency_drift_rejected(self):
  self.current['transformers']='0.0.0'
  with self.assertRaisesRegex(ValueError,'only the exact'):self.verify()
 def test_non_cpu_torch_rejected(self):
  self.current['torch']='2.14.1'
  with self.assertRaisesRegex(ValueError,'only the exact'):self.verify()
 def test_symlink_rejected(self):
  (self.root/'link').symlink_to(self.root/'bundle.txt')
  with self.assertRaisesRegex(ValueError,'symlink'):self.verify()
 def test_wrong_model_revision_rejected(self):
  self.m['vector']['modelRevision']='0'*40;self.save()
  with self.assertRaisesRegex(ValueError,'semantic model'):self.verify()
if __name__=='__main__':unittest.main()
