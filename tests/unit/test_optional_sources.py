import json,unittest
from pathlib import Path
import test_collections_public_bindings as base
class OptionalTests(unittest.TestCase):
 def setUp(self):base.BindingsTest.setUp(self);self.event=self.root/'optional-events.json';self.binding['optional_sources']={'events':str(self.event)}
 def check(self,**kw):return base.BindingsTest.check(self,**kw)
 def test_missing_known_feed_is_omitted(self):
  r=self.check();self.assertTrue(r['healthy']);self.assertEqual(r['sites'][0]['optional_source_presence'],{'events':False});self.assertNotIn('events',r['sites'][0]['source_sha256'])
 def test_existing_feed_is_bound(self):
  self.event.write_text('{}');r=self.check();self.assertTrue(r['healthy']);self.assertTrue(r['sites'][0]['optional_source_presence']['events']);self.assertIn('events',r['sites'][0]['source_sha256'])
 def test_feed_appearing_gets_fresh_pinned_proof(self):
  def fetch(url):
   if url.endswith('/__template_version'):return json.dumps(self.metadata)
   self.event.write_text('{}');return '<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a></section>'
  self.path.write_text(json.dumps(self.policy));r=base.module.проверить_суточные_подборки(self.path,now=self.now,fetch=fetch,retry_wait=lambda _:None);self.assertTrue(r['measured']);self.assertTrue(r['healthy']);self.assertIn('presence changed',r['sites'][0]['source_race_attempts'][0]['reason']);self.assertTrue(all(r['sites'][0]['optional_source_presence'].values()))
class AvailabilityTests(OptionalTests):
 def setUp(self):
  super().setUp();self.binding['optional_sources']={'availability':str(self.event)}
 def test_missing_known_feed_is_omitted(self):
  r=self.check();self.assertTrue(r['healthy']);self.assertEqual(r['sites'][0]['optional_source_presence'],{'availability':False})
 def test_existing_feed_is_bound(self):
  self.event.write_text('{}');r=self.check();self.assertTrue(r['healthy']);self.assertIn('availability',r['sites'][0]['source_sha256'])
class HelperBudgetTests(OptionalTests):
 def test_helper_cap_ninety(self):
  from unittest.mock import patch
  import subprocess
  original=subprocess.run;caps=[]
  def run(*a,**kw):caps.append(kw['timeout']);return original(*a,**kw)
  with patch.object(subprocess,'run',side_effect=run):self.assertTrue(self.check()['healthy'])
  self.assertEqual(caps,[90])
 def test_helper_cap_clipped_by_remaining(self):
  from unittest.mock import patch
  import subprocess
  original=subprocess.run;caps=[]
  def run(*a,**kw):caps.append(kw['timeout']);return original(*a,**kw)
  self.path.write_text(json.dumps(self.policy))
  with patch.object(subprocess,'run',side_effect=run):
   r=base.module.проверить_суточные_подборки(self.path,now=self.now,budget_seconds=30,fetch=lambda url:json.dumps(self.metadata) if url.endswith('/__template_version') else '<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a></section>',retry_wait=lambda _:None)
  self.assertTrue(r['healthy']);self.assertTrue(0<caps[0]<=30)
if __name__=='__main__':unittest.main()
