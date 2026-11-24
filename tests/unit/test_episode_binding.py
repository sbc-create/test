import hashlib,json,unittest
import test_collections_public_bindings as base
module=base.module
class Test(unittest.TestCase):
 check=base.BindingsTest.check
 def setUp(self):
  base.BindingsTest.setUp(self)
  self.source.write_text(json.dumps({'site':'animedia-01','revision':'rev1'}));self.details.write_text(json.dumps({'site':'animedia-01','catalog_revision':'rev1'}))
  self.binding['site_id']='animedia-01';self.registry.write_text(json.dumps({'cells':[{'site_id':'animedia-01','domain':'example.org'}]}))
  (self.release/'release-manifest.json').write_text(json.dumps({'site_id':'animedia-01','commit':self.commit}))
  self.result={'complete':True,'eligible_ids':['a'],'required_runtime_binding':{'episode_feed_source':'snapshot-diff'},'expected_public':[{'path':'/','region':{'attr':'data-collection-policy','value':'new_episodes'},'card_class':'aeps__item','ordered_hrefs':['/title/a/season-2/episode-1/']}],'manual_fingerprint':'kept','policy_version':'v1'}
  self.save()
  self.html='<section id="new-episodes" data-episode-feed-source="snapshot-diff"><div data-collection-policy="new_episodes"><a class="aeps__item" href="/title/a/season-2/episode-1/">A</a></div></section>'
 def save(self):
  self.helper.write_text('def collections_check(sources,today):\n return '+repr(self.result)+'\n');self.binding['helper_sha256']=hashlib.sha256(self.helper.read_bytes()).hexdigest()
 def test_exact_episode_path_and_source(self):self.assertTrue(self.check(self.html)['healthy'])
 def test_wrong_source(self):self.assertFalse(self.check(self.html.replace('snapshot-diff','other'))['healthy'])
 def test_missing_source(self):self.assertFalse(self.check(self.html.replace(' data-episode-feed-source="snapshot-diff"',''))['healthy'])
 def test_source_outside_card_region(self):
  self.assertFalse(self.check(self.html.replace('<div data-', '</section><div data-').replace('</div></section>','</div>'))['healthy'])
 def test_duplicate_source_section(self):self.assertFalse(self.check(self.html+'<section id="new-episodes" data-episode-feed-source="snapshot-diff"></section>')['healthy'])
 def test_unknown_claim_unmeasured(self):
  self.result['required_runtime_binding']={'episode_feed_source':'other'};self.save();self.assertFalse(self.check(self.html)['measured'])
 def test_absent_region_allowed_but_wrong_existing_source_refused(self):
  self.result['expected_public'][0].update(ordered_hrefs=[],absent_region=True);self.save();self.assertTrue(self.check('<main></main>')['healthy']);self.assertFalse(self.check('<section id="new-episodes" data-episode-feed-source="other"></section>')['healthy'])
 def test_after_fetch_source_change_refused(self):
  self.path.write_text(json.dumps(self.policy));calls=[0]
  def fetch(url):
   if url.endswith('/__template_version'):return json.dumps(self.metadata)
   calls[0]+=1;return self.html if calls[0]==1 else self.html.replace('snapshot-diff','other')
  x=module.проверить_суточные_подборки(self.path,now=self.now,fetch=fetch,retry_wait=lambda _:None)
  self.assertFalse(x['healthy'])
