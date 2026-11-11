import importlib.util,json,pathlib,tempfile,unittest,unittest.mock as mock,subprocess
s=importlib.util.spec_from_file_location('safe',pathlib.Path(__file__).with_name('k2-lords18-catalog-safe.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class SafeApply(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();p=pathlib.Path(self.tmp.name);self.calls=[]
  for k,v in {'ROOT':p/'site','INCOMING':p/'incoming','STATE':p/'state','UP':p/'route','MANIFEST':p/'manifest'}.items():setattr(m,k,v)
  (m.ROOT/'data').mkdir(parents=True);release=m.ROOT/'releases'/'fixed';(release/'config').mkdir(parents=True);(m.ROOT/'current').symlink_to(release)
  (release/'config/site.json').write_text(json.dumps({'data_contract':{'user_writable':['editorial.json']},'indexing':{'runtime_state_file':str(p/'index')}}));(release/'config/player.json').write_text('publisher kept');(m.ROOT/'data/editorial.json').write_text('user text');m.UP.write_bytes(b'server 127.0.0.1:9136;\n');m.MANIFEST.write_text(json.dumps({'cells':{m.SID:{'account':'lordserials1-cc','port':9136,'unit':m.UNIT,'reload':'restart'}}}))
  box=m.INCOMING/m.SID;box.mkdir(parents=True)
  for n in m.NAMES:(box/n).write_text('new '+n);(m.ROOT/'data'/n).write_text('old '+n)
  (box/'SHA256SUMS').write_text('checks delegated to native helper')
  self.patches=[mock.patch.object(m,'health',lambda *a:None),mock.patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],3)),mock.patch.object(m,'run',self.fake_run)]
  for p in self.patches:p.start()
  self.fail=False
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def fake_run(self,*args,**kw):
  self.calls.append(args)
  if args==(m.APPLY,m.SID):
   self.assertEqual(m.UP.read_bytes(),b'server 127.0.0.1:10136;\n')
   for n in m.NAMES:(m.ROOT/'data'/n).write_text('new '+n)
   if self.fail:raise RuntimeError('simulated apply failure')
 def test_success_preserves_text_route_and_order(self):
  self.assertEqual(m.apply_locked(),'applied');self.assertEqual((m.ROOT/'data/editorial.json').read_text(),'user text');self.assertEqual(m.UP.read_bytes(),b'server 127.0.0.1:9136;\n');self.assertFalse((m.ROOT/'candidate').is_symlink());self.assertFalse((m.INCOMING/m.SID).exists());self.assertTrue(list(m.STATE.glob('*/success.json')))
 def test_failed_native_apply_restores_prior_catalog(self):
  self.fail=True
  with self.assertRaisesRegex(RuntimeError,'simulated'):m.apply_locked()
  for n in m.NAMES:self.assertEqual((m.ROOT/'data'/n).read_text(),'old '+n)
  self.assertEqual(m.UP.read_bytes(),b'server 127.0.0.1:9136;\n');self.assertTrue((m.INCOMING/m.SID).exists());self.assertFalse((m.ROOT/'candidate').is_symlink())
 def test_unexpected_route_refused_before_mutation(self):
  m.UP.write_bytes(b'server other;\n')
  with self.assertRaises(AssertionError):m.apply_locked()
  self.assertFalse(self.calls)
 def test_shared_lock_prevents_parallel_apply(self):
  m.LOCK=pathlib.Path(self.tmp.name)/'lock'
  with m.LOCK.open('a') as held:
   m.fcntl.flock(held,m.fcntl.LOCK_EX|m.fcntl.LOCK_NB)
   with mock.patch.object(m,'apply_locked') as apply, mock.patch.object(m.os,'geteuid',return_value=0):
    m.main();apply.assert_not_called()
 def test_missing_provenance_refused(self):
  (m.INCOMING/m.SID/m.NAMES[-1]).unlink()
  with self.assertRaises(AssertionError):m.apply_locked()
  self.assertFalse(self.calls)
if __name__=='__main__':unittest.main()
