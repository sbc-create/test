import json,unittest
import test_episode_binding as base
class Test(base.Test):
 def setUp(self):
  super().setUp();self.use_site('animego-02')
  self.html='<section data-collection-policy="new_episodes" data-episode-feed-source="snapshot-diff"><a class="aeps__item" href="/title/a/season-2/episode-1/">A</a></section>'
 def use_site(self,site):
  self.binding['site_id']=site;self.source.write_text(json.dumps({'site':site,'revision':'rev1'}));self.details.write_text(json.dumps({'site':site,'catalog_revision':'rev1'}));self.registry.write_text(json.dumps({'cells':[{'site_id':site,'domain':'example.org'}]}));(self.release/'release-manifest.json').write_text(json.dumps({'site_id':site,'commit':self.commit}))
 def test_closed_three_profiles(self):
  for site in ['animego-02','animego-03','animego-04']:
   self.use_site(site);self.assertTrue(self.check(self.html)['healthy'])
 def test_unknown_site_not_admitted(self):
  self.use_site('animego-05');self.assertFalse(self.check(self.html)['measured'])
 def test_source_outside_card_region(self):
  self.assertFalse(self.check('<section data-episode-feed-source="snapshot-diff"></section>'+self.html.replace(' data-episode-feed-source="snapshot-diff"',''))['healthy'])
 def test_duplicate_source_section(self):self.assertFalse(self.check(self.html+self.html)['healthy'])
 def test_div_cannot_impersonate_fixed_section(self):self.assertFalse(self.check(self.html.replace('section','div'))['healthy'])
 def test_absent_region_allowed_but_wrong_existing_source_refused(self):
  self.result['expected_public'][0].update(ordered_hrefs=[],absent_region=True);self.save();self.assertTrue(self.check('<main></main>')['healthy']);self.assertFalse(self.check('<section data-collection-policy="new_episodes" data-episode-feed-source="other"></section>')['healthy'])
