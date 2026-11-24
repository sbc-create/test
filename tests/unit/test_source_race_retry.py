import json,unittest
import test_collections_public_bindings as base
class Test(unittest.TestCase):
 def setUp(self):base.BindingsTest.setUp(self)
 def run_check(self,repeat=False):
  self.path.write_text(json.dumps(self.policy));calls=[0]
  def fetch(url):
   if url.endswith('/__template_version'):return json.dumps(self.metadata)
   calls[0]+=1
   if repeat or calls[0]==1:
    doc=json.loads(self.source.read_text());doc['producer_version']=calls[0];self.source.write_text(json.dumps(doc))
   return '<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a></section>'
  out=base.module.проверить_суточные_подборки(self.path,now=self.now,fetch=fetch,retry_wait=lambda _:None)
  return out,calls
 def test_one_atomic_advance_rechecks_only_site_fresh(self):
  out,calls=self.run_check();self.assertTrue(out['healthy']);self.assertEqual(calls[0],2);row=out['sites'][0];self.assertEqual(len(row['source_race_attempts']),1);self.assertFalse(row['source_race_attempts'][0]['measured']);self.assertNotEqual(row['input_sha256_observed'],row['source_race_attempts'][0]['input_sha256_observed'])
 def test_repeated_source_race_remains_unmeasured_and_bounded(self):
  out,calls=self.run_check(True);self.assertFalse(out['measured']);self.assertEqual(calls[0],2);self.assertEqual(len(out['sites'][0]['source_race_attempts']),1)
 def test_remaining_global_budget_prevents_retry(self):
  from unittest.mock import patch
  clock=[100.0];self.path.write_text(json.dumps(self.policy));calls=[0]
  def fetch(url):
   if url.endswith('/__template_version'):return json.dumps(self.metadata)
   calls[0]+=1;doc=json.loads(self.source.read_text());doc['producer_version']=1;self.source.write_text(json.dumps(doc));clock[0]=209.5
   return '<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a></section>'
  with patch('time.monotonic',side_effect=lambda:clock[0]):
   out=base.module.проверить_суточные_подборки(self.path,now=self.now,fetch=fetch,retry_wait=lambda _:None,budget_seconds=110)
  self.assertFalse(out['measured']);self.assertEqual(calls[0],1);self.assertEqual(out['sites'][0]['source_race_retry'],'remaining budget exhausted')
 def test_healthy_other_site_is_not_repeated(self):
  import copy
  other=copy.deepcopy(self.binding);other['site_id']='pilot-two';other['domain']='second.example.org';release=self.root/'second-release';release.mkdir();(release/'release-manifest.json').write_text(json.dumps({'site_id':'pilot-two','commit':self.commit}));current=self.root/'second-current';current.symlink_to(release);other['local_runtime']['current_path']=str(current);(release/'policy.py').write_bytes(self.helper.read_bytes());other['helper_path']=str(release/'policy.py')
  for name,key in [('catalog','revision'),('details','catalog_revision')]:
   p=self.root/('second-'+name+'.json');p.write_text(json.dumps({'site':'pilot-two',key:'rev1'}));other['sources'][name]=str(p)
  self.policy['sites'].append(other);self.registry.write_text(json.dumps({'cells':[{'site_id':'pilot','domain':'example.org'},{'site_id':'pilot-two','domain':'second.example.org'}]}));self.path.write_text(json.dumps(self.policy));calls={'first':0,'second':0}
  def fetch(url):
   if url.endswith('/__template_version'):return json.dumps(self.metadata)
   name='second' if 'second.example.org' in url else 'first';calls[name]+=1
   if name=='first' and calls[name]==1:
    doc=json.loads(self.source.read_text());doc['producer_version']=1;self.source.write_text(json.dumps(doc))
   return '<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a></section>'
  out=base.module.проверить_суточные_подборки(self.path,now=self.now,fetch=fetch,retry_wait=lambda _:None);self.assertTrue(out['healthy']);self.assertEqual(calls,{'first':2,'second':1})

 def test_midnight_retry_cannot_mix_policy_days(self):
  from unittest.mock import patch
  import datetime
  self.now=self.now.replace(hour=23,minute=59,second=59,microsecond=0)
  self.path.write_text(json.dumps(self.policy));clock=[100.0];calls=[0]
  def fetch(url):
   if url.endswith('/__template_version'):return json.dumps(self.metadata)
   calls[0]+=1
   if calls[0]==1:
    doc=json.loads(self.source.read_text());doc['producer_version']=1;self.source.write_text(json.dumps(doc));clock[0]=102.0
   return '<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a></section>'
  with patch('time.monotonic',side_effect=lambda:clock[0]):
   out=base.module.проверить_суточные_подборки(self.path,now=self.now,fetch=fetch,retry_wait=lambda _:None)
  self.assertFalse(out['measured']);self.assertFalse(out['healthy']);self.assertEqual(out['policy_day'],self.now.date().isoformat());self.assertEqual(out['sites'][0]['source_race_retry'],'UTC policy day changed')
