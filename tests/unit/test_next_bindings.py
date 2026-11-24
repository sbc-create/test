import datetime as dt,hashlib,json,pathlib,tempfile,types,unittest
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parents[2]/'automation/local/editorial-sets-validate.py';m=types.ModuleType('checker');m.__file__=str(P);exec(compile(P.read_text(),str(P),'exec'),m.__dict__)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
class Test(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.p=pathlib.Path(self.t.name);self.now=dt.datetime(2026,11,24,10,tzinfo=dt.timezone.utc);self.commit='a'*40;self.root=self.p/self.commit;self.root.mkdir();self.sources={}
  for key in ('watcher','events','manual'):
   p=self.p/(key+'.json');p.write_text('{}');self.sources[key]=str(p)
  node=self.root/'collections-check.cjs';node.write_text('// fixture bundle');shim=self.root/'collections_check.py';shim.write_text("def collections_check(sources,today):\n assert sources['_public_observation']['status']=='ready'\n return {'complete':True,'eligible_ids':['a'],'policy_version':'org-home-v1','manual_fingerprint':'manual','expected_public':[{'path':'/','region':{'attr':'data-home-block','value':'top'},'card_class':'portal-top-cell','ordered_hrefs':['/anime/dyavolskiy-prints-enma-2011--01927e82-e401-73b8-9e7e-ab9dbbea5bb1']}]}\n")
  self.manifest={'schema':'k2-next-runtime/1','site_id':'yummy-org','source_commit':self.commit,'image_digest':'sha256:'+'b'*64,'source_paths':self.sources,'node_major':22,'helper_path':str(node),'helper_sha256':sha(node),'policy_path':str(node),'policy_sha256':sha(node),'shim_path':str(shim),'shim_sha256':sha(shim)};self.mp=self.p/'manifest.json';self.mp.write_text(json.dumps(self.manifest));registry=self.p/'registry';registry.write_text(json.dumps({'cells':[{'site_id':'yummy-org','domain':'yummyani.org'}]}));self.binding={'site_id':'yummy-org','domain':'yummyani.org','enabled':True,'sources':self.sources,'helper_path':str(shim),'helper_sha256':sha(shim),'next_runtime':{'manifest_path':str(self.mp),'manifest_sha256':sha(self.mp),'expected_commit':self.commit,'expected_image_digest':self.manifest['image_digest'],'artifact_root':str(self.root),'public_health_path':'/api/health?collections=1','policy_version':'org-home-v1'}};self.policy={'schema':'collections-refresh-bindings-v1','registry':str(registry),'sites':[self.binding]};self.pp=self.p/'policy.json'
  self.obs={'schema':'org-home-policy-proof/1','site_id':'yummy-org','status':'ready','build_revision':self.commit,'policy_sha256':sha(node),'policy_version':'org-home-v1','source_generation':{k+'_sha256':sha(pathlib.Path(self.sources[k])) for k in ('watcher','events')},'manual_fingerprint':sha(pathlib.Path(self.sources['manual'])),'observed_at':self.now.isoformat(),'canonical_mapping':[{'id':'a','href':'/anime/dyavolskiy-prints-enma-2011--01927e82-e401-73b8-9e7e-ab9dbbea5bb1'}],'base_newest':[]};self.html='<section data-home-block="top"><a class="portal-top-cell" href="/anime/dyavolskiy-prints-enma-2011--01927e82-e401-73b8-9e7e-ab9dbbea5bb1">A</a></section>'
 def check(self,fetch=None):
  self.pp.write_text(json.dumps(self.policy))
  def get(url):return json.dumps({'collections_policy':self.obs}) if '/api/health?' in url else self.html
  with patch('subprocess.check_output',return_value='v22.23.2\n'):
   return m.проверить_суточные_подборки(self.pp,now=self.now,fetch=fetch or get,retry_wait=lambda _:None)
 def test_exact_contract(self):self.assertTrue(self.check()['healthy'])
 def test_public_revision_mismatch(self):self.obs['build_revision']='c'*40;self.assertFalse(self.check()['measured'])
 def test_source_generation_mismatch(self):self.obs['source_generation']['watcher_sha256']='wrong';self.assertFalse(self.check()['measured'])
 def test_stale_public_status(self):self.obs['status']='stale';self.assertFalse(self.check()['measured'])
 def test_manifest_pin_mismatch(self):self.binding['next_runtime']['manifest_sha256']='wrong';self.assertFalse(self.check()['measured'])
 def test_image_mismatch(self):self.binding['next_runtime']['expected_image_digest']='sha256:'+'c'*64;self.assertFalse(self.check()['measured'])
 def test_future_public_timestamp(self):self.obs['observed_at']='2026-11-24T10:02:00+00:00';self.assertFalse(self.check()['measured'])
 def test_wrong_node(self):
  self.pp.write_text(json.dumps(self.policy))
  with patch('subprocess.check_output',return_value='v20.0.0'):
   r=m.проверить_суточные_подборки(self.pp,now=self.now,fetch=lambda u:'')
  self.assertFalse(r['measured'])
 def test_duplicate_mapping(self):self.obs['canonical_mapping']*=2;self.assertFalse(self.check()['measured'])
 def test_source_race(self):
  def get(url):
   if '/api/health?' in url:return json.dumps({'collections_policy':self.obs})
   pathlib.Path(self.sources['events']).write_text('{"changed":true}');return self.html
  self.assertFalse(self.check(get)['measured'])
 def test_public_mapping_race(self):
  calls=[0]
  def get(url):
   if '/api/health?' not in url:return self.html
   calls[0]+=1
   if calls[0]>1:self.obs['canonical_mapping'][0]['href']='/anime/povelitel-besstrashnogo-duha--01915137-083b-738b-9791-5025cf1327da'
   return json.dumps({'collections_policy':self.obs})
  self.assertFalse(self.check(get)['measured'])
 def test_footer_does_not_satisfy(self):self.html='<footer><a class="portal-top-cell" href="/anime/dyavolskiy-prints-enma-2011--01927e82-e401-73b8-9e7e-ab9dbbea5bb1">A</a></footer>';self.assertFalse(self.check()['healthy'])
 def test_encoded_path_escape_rejected(self):
  self.obs['canonical_mapping'][0]['href']='/anime/%2e%2e%2fsecret';self.assertFalse(self.check()['measured'])
 def test_old_python_route_rejected(self):
  self.obs['canonical_mapping'][0]['href']='/title/a/';self.assertFalse(self.check()['measured'])
if __name__=='__main__':unittest.main()

def test_time_spent_before_next_binding_does_not_make_fresh_proof_future(self):
  self.obs['observed_at']=(self.now+dt.timedelta(seconds=80)).isoformat()
  calls=[0]
  def monotonic():
   calls[0]+=1
   return 100 if calls[0]==1 else 180
  with patch('time.monotonic',side_effect=monotonic):
   self.assertTrue(self.check()['healthy'])

Test.test_time_spent_before_next_binding_does_not_make_fresh_proof_future=test_time_spent_before_next_binding_does_not_make_fresh_proof_future
