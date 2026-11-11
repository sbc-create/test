import importlib.util,pathlib,tempfile,json,os,unittest
spec=importlib.util.spec_from_file_location('receiver',pathlib.Path(__file__).resolve().parents[2]/'automation/host/k2-lords19-editorial-receiver.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Receiver(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.base=pathlib.Path(self.t.name);self.paths=[self.base/n for n in ['inbox','data','state']]
  for p in self.paths:p.mkdir()
  self.doc={'schema_version':1,'site_id':'lords-19','overrides':{'title-real':{'fields':{'description':'isolated fixture'},'actor':'test','reason':'test'}}}
  self.envelope={'site_id':'lords-19','expected_before_sha256':None,'changed_title_id':'title-real','content':self.doc}
  (self.paths[1]/'unrelated').write_text('preserve')
 def tearDown(self):self.t.cleanup()
 def run_apply(self):
  (self.paths[0]/'pending.json').write_bytes(m.canonical(self.envelope));return m.apply(*self.paths,owner=(os.getuid(),os.getgid()))
 def test_apply_idempotent(self):
  self.assertEqual(self.run_apply()['status'],'applied');self.assertEqual(self.run_apply()['status'],'applied');self.assertEqual((self.paths[1]/'unrelated').read_text(),'preserve')
 def test_stale(self):
  self.run_apply();old=(self.paths[1]/'editorial-overrides.json').read_bytes();self.doc['overrides']['title-real']['fields']['description']='new'
  with self.assertRaises(m.Refused):self.run_apply()
  self.assertEqual((self.paths[1]/'editorial-overrides.json').read_bytes(),old)
 def test_fifo(self):
  os.mkfifo(self.paths[0]/'pending.json')
  with self.assertRaises(m.Refused):m.apply(*self.paths,owner=(os.getuid(),os.getgid()))
 def test_preservation(self):
  before={'schema_version':1,'site_id':'lords-19','overrides':{'other':{'fields':{'name':'Other'},'actor':'owner','reason':'prior'},'title-real':{'fields':{'name':'Keep','description':'Old'},'actor':'owner','reason':'prior'}}}
  raw=m.canonical(before);(self.paths[1]/'editorial-overrides.json').write_bytes(raw);self.envelope['expected_before_sha256']=m.sha(raw)
  self.doc['overrides']['other']=before['overrides']['other'];self.doc['overrides']['title-real']['fields']['name']='Keep'
  self.run_apply();after=m.strict((self.paths[1]/'editorial-overrides.json').read_bytes());self.assertEqual(after['overrides']['other'],before['overrides']['other']);self.assertEqual(after['overrides']['title-real']['fields']['name'],'Keep')
 def test_reject_drop(self):
  self.run_apply();raw=(self.paths[1]/'editorial-overrides.json').read_bytes();self.envelope['expected_before_sha256']=m.sha(raw);self.envelope['changed_title_id']='other';self.doc['overrides']={}
  with self.assertRaises(m.Refused):self.run_apply()
  receipt=m.strict((self.paths[2]/'latest.json').read_bytes());self.assertEqual(receipt['status'],'refused');self.assertEqual(receipt['request_sha256'],m.sha(m.canonical(self.envelope)))
 def test_site(self):
  self.envelope['site_id']='lords-18'
  with self.assertRaises(m.Refused):self.run_apply()
 def test_forbidden(self):
  self.doc['overrides']['title-real']['fields']['publisher_id']=99
  with self.assertRaises(m.Refused):self.run_apply()
 def test_symlink_file(self):
  (self.paths[1]/'editorial-overrides.json').symlink_to(self.paths[1]/'unrelated')
  with self.assertRaises(OSError):self.run_apply()
  self.assertEqual((self.paths[1]/'unrelated').read_text(),'preserve')
 def test_symlink_dir(self):
  link=self.base/'link';link.symlink_to(self.paths[1],target_is_directory=True)
  with self.assertRaises(OSError):m.directory(link)
 def test_duplicate_json(self):
  with self.assertRaises(m.Refused):m.strict(b'{"a":1,"a":2}')
 def test_large_input(self):
  (self.paths[0]/'pending.json').write_bytes(b' '*(m.MAX+1))
  with self.assertRaises(m.Refused):m.apply(*self.paths,owner=(os.getuid(),os.getgid()))
unittest.main()
