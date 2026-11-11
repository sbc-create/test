import importlib.util,pathlib,tempfile,json,sys,types,unittest,ast
from unittest.mock import patch
cell=types.ModuleType('factory.cell');cell.editorial_store=types.SimpleNamespace(текст=lambda d:json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
def save(p,d):p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(d))
cell.queue=types.SimpleNamespace(записать_атомарно=save)
sys.modules['factory']=types.ModuleType('factory');sys.modules['factory.cell']=cell
spec=importlib.util.spec_from_file_location('adapter',pathlib.Path(__file__).resolve().parents[1]/'factory/cell/k2_lords20_editorial.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class Response:
 status=200
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self):return b'{"ok":true,"service":"lords","revision":"unknown"}'
class Adapter(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();a.CACHE=pathlib.Path(self.t.name)/'cache';a.CACHE.mkdir();self.facts=b'{"site":"lords-20"}';self.info={'site_id':'lords-20','domain':a.DOMAIN,'contract_verified':True,'runtime_digest_match':True,'runtime_commit':'a'*40,'release':'a'*12,'overlay':None,'overlay_sha256':None,'inspected_at':a.datetime.datetime.now(a.datetime.timezone.utc).isoformat(),'details_sha256':a.sha(self.facts)}
 def tearDown(self):self.t.cleanup()
 def remote(self,cmd,*args,**kwargs):return json.dumps(self.info).encode() if '--inspect' in cmd else self.facts
 def test_redacted_public_verified_remote(self):
  with patch.object(a,'remote',self.remote),patch.object(a.urllib.request,'urlopen',return_value=Response()):r=a.refresh(True)
  self.assertTrue(r['runtime_digest_match']);self.assertTrue((a.CACHE/'lords-20-details.json').is_file())
 def test_stale_root_proof(self):
  self.info['inspected_at']='2020-01-01T00:00:00+00:00'
  with patch.object(a,'remote',self.remote),patch.object(a.urllib.request,'urlopen',return_value=Response()),self.assertRaises(a.Refused):a.refresh(True)
 def test_bad_internal_digest(self):
  self.info['runtime_digest_match']=False
  with patch.object(a,'remote',self.remote),patch.object(a.urllib.request,'urlopen',return_value=Response()),self.assertRaises(a.Refused):a.refresh(True)
 def test_envelope_native_bytes(self):
  doc={'schema_version':1,'site_id':a.SITE,'overrides':{'one':{'fields':{'description':'Text'},'actor':'a','reason':'r'}}};env=a.make_envelope(doc,None);self.assertEqual(env['changed_title_id'],'one');self.assertEqual(a.canonical(env),(json.dumps(env,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode())
 def test_multititle_refused(self):
  with self.assertRaises(a.Refused):a.make_envelope({'overrides':{'one':{},'two':{}}},None)
 def test_native_merge_preserves(self):
  source=(pathlib.Path(__file__).resolve().parents[1]/'factory/qwen/editorial.py').read_text();tree=ast.parse(source);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='состав_правок');ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'native-merge','exec'),ns)
  prior={'one':{'fields':{'name':'Keep','description':'Old'},'actor':'prior','reason':'old'},'other':{'fields':{'description':'Other'},'actor':'other','reason':'history'}}
  row={'title_id':'one','body':'Updated'};merged=ns['состав_правок'](prior,[row],[row]);self.assertEqual(merged['other'],prior['other']);self.assertEqual(merged['one']['fields']['name'],'Keep')
 def test_source_dirty_or_wrong_commit(self):
  a.SOURCE=pathlib.Path(self.t.name)/'source';(a.SOURCE/'config').mkdir(parents=True);(a.SOURCE/'.git').mkdir();(a.SOURCE/'config/site.json').write_text(json.dumps({'site_id':a.SITE,'domain':a.DOMAIN,'publisher_id_expected':10623}))
  for outputs in [['a'*40+'\n',' M config/site.json\n'],['b'*40+'\n','']]:
   with patch.object(a.subprocess,'check_output',side_effect=outputs),self.assertRaises(a.Refused):a.source_identity({'runtime_commit':'a'*40})
 def test_stale_merge_baseline(self):
  (a.CACHE/'status.json').write_text('{"overlay_sha256":null}')
  with patch.object(a,'refresh',return_value={'overlay_sha256':'different'}),self.assertRaises(a.Refused):a.submit(a.SITE,{'site_id':a.SITE},'a'*40)
unittest.main()
