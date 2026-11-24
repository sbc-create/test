import ast
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
ROOT = Path(__file__).resolve().parents[2]
P = ROOT / 'automation/local/editorial-sets-validate.py'
module = types.ModuleType('validator')
module.__file__ = str(P)
exec(compile(P.read_text(), str(P), 'exec'), module.__dict__)

class BindingsTest(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = dt.datetime(2026, 11, 24, 7, tzinfo=dt.timezone.utc)
        self.source = self.root / 'catalog.json'
        self.source.write_text(json.dumps({'site': 'pilot', 'revision': 'rev1'}))
        self.details = self.root / 'details.json'
        self.details.write_text(json.dumps({'site': 'pilot', 'catalog_revision': 'rev1'}))
        self.release = self.root / 'release'
        self.release.mkdir()
        self.current = self.root / 'current'
        self.current.symlink_to(self.release)
        self.commit = 'a' * 40
        (self.release / 'release-manifest.json').write_text(json.dumps({'site_id': 'pilot', 'commit': self.commit}))
        self.metadata = {'site_repo_commit': self.commit, 'catalog_revision': 'rev1', 'details_catalog_revision': 'rev1'}
        self.helper = self.release / 'policy.py'
        self.helper.write_text('def collections_check(sources, today):\n return {"complete":True,"eligible_ids":["a"],"expected_public":[{"path":"/collections/","region":{"attr":"data-collection-policy","value":"top_rated"},"card_class":"c","ordered_hrefs":["/title/a/"]}],"manual_fingerprint":"kept","policy_version":"v1"}\n')
        self.registry = self.root / 'registry.json'
        self.registry.write_text(json.dumps({'cells': [{'site_id': 'pilot', 'domain': 'example.org'}]}))
        self.receipt = {'status': 'live_verified', 'site_id': 'pilot', 'domain': 'example.org', 'verified_at': '2026-11-24T03:30:00Z', 'native_source_sha256': {'catalog': hashlib.sha256(self.source.read_bytes()).hexdigest()}}
        self.receipt_path = self.root / 'receipt.json'
        self.binding = {'site_id': 'pilot', 'domain': 'example.org', 'enabled': True, 'sources': {'catalog': str(self.source), 'details': str(self.details)}, 'local_runtime': {'current_path': str(self.current), 'expected_commit': self.commit}, 'helper_path': str(self.helper), 'helper_sha256': hashlib.sha256(self.helper.read_bytes()).hexdigest(), 'delivery_receipt': str(self.receipt_path)}
        self.policy = {'schema': 'collections-refresh-bindings-v1', 'registry': str(self.registry), 'sites': [self.binding]}
        self.path = self.root / 'bindings.json'

    def check(self, body='<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a></section>', **kw):
        self.receipt_path.write_text(json.dumps(self.receipt))
        self.path.write_text(json.dumps(self.policy))
        return module.проверить_суточные_подборки(self.path, now=kw.get('now', self.now), fetch=lambda url: json.dumps(self.metadata) if url.endswith('/__template_version') else body, retry_wait=lambda _: None)

    def test_healthy_repeat_deterministic(self):
        a = self.check()
        b = self.check()
        self.assertTrue(a['healthy'])
        self.assertEqual(a['fingerprint'], b['fingerprint'])

    def test_day_alone_preserves_composition_fingerprint(self):
        a = self.check()
        b = self.check(now=self.now + dt.timedelta(days=1))
        self.assertTrue(b['healthy'])
        self.assertEqual(a['fingerprint'], b['fingerprint'])

    def test_wrong_rollout_commit_unmeasured(self):
        self.binding['local_runtime']['expected_commit'] = 'b' * 40
        self.assertFalse(self.check()['measured'])

    def test_source_mismatch_unmeasured(self):
        self.source.write_text('{"changed":true}')
        self.assertFalse(self.check()['measured'])

    def test_missing_public_link_defect(self):
        r = self.check('')
        self.assertTrue(r['measured'])
        self.assertFalse(r['healthy'])

    def test_hidden_public_link_defect(self):
        self.assertFalse(self.check('<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a><a class="c" href="/title/hidden/">B</a></section>')['healthy'])

    def test_disabled_unmeasured(self):
        self.binding['enabled'] = False
        self.assertFalse(self.check()['measured'])

    def test_helper_hash_unmeasured(self):
        self.binding['helper_sha256'] = '0' * 64
        self.assertFalse(self.check()['measured'])

    def test_excluded_domain_unmeasured(self):
        self.binding['domain'] = 'animedia.space'
        self.assertFalse(self.check()['measured'])

    def test_partial_never_healthy(self):
        self.policy['sites'].append(dict(self.binding, site_id='missing'))
        self.assertFalse(self.check()['measured'])

    def test_duplicate_binding_rejected(self):
        self.policy['sites'].append(self.binding.copy())
        self.assertFalse(self.check()['measured'])

    def test_transport_exception_unmeasured(self):
        self.check()

        def fail(url):
            raise TimeoutError('private URL not logged')
        result = module.проверить_суточные_подборки(self.path, now=self.now, fetch=fail)
        self.assertFalse(result['measured'])
        self.assertEqual(result['sites'][0]['reason'], 'TimeoutError')

    def rewrite_helper(self, source):
        self.helper.write_text(source)
        self.binding['helper_sha256'] = hashlib.sha256(self.helper.read_bytes()).hexdigest()

    def test_footer_only_not_accepted(self):
        r = self.check('<section data-collection-policy="top_rated"></section><footer><a class="c" href="/title/a/">A</a></footer>')
        self.assertTrue(r['measured'])
        self.assertFalse(r['healthy'])

    def test_duplicate_card_not_accepted(self):
        self.assertFalse(self.check('<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a><a class="c" href="/title/a/">A</a></section>')['healthy'])

    def test_wrong_card_order_not_accepted(self):
        self.rewrite_helper(self.helper.read_text().replace('"ordered_hrefs":["/title/a/"]', '"ordered_hrefs":["/title/a/","/title/b/"]'))
        self.assertFalse(self.check('<section data-collection-policy="top_rated"><a class="c" href="/title/b/">B</a><a class="c" href="/title/a/">A</a></section>')['healthy'])

    def test_duplicate_regions_not_accepted(self):
        body = '<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a></section>'
        self.assertFalse(self.check(body + body)['healthy'])

    def test_wrong_region_not_accepted(self):
        self.assertFalse(self.check('<section data-collection-policy="new"><a class="c" href="/title/a/">A</a></section>')['healthy'])

    def test_non_card_link_not_accepted(self):
        self.assertFalse(self.check('<section data-collection-policy="top_rated"><a href="/title/a/">A</a></section>')['healthy'])

    def test_nested_wrappers_and_void_images_valid(self):
        self.assertTrue(self.check('<section data-collection-policy="top_rated"><div><a class="card c" href="/title/a/"><img src="x"><span>A</span></a></div></section>')['healthy'])

    def test_unclosed_region_not_accepted(self):
        self.assertFalse(self.check('<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a>')['healthy'])

    def test_eligible_order_changes_fingerprint(self):
        self.rewrite_helper(self.helper.read_text().replace('"eligible_ids":["a"]', '"eligible_ids":["a","b"]'))
        a = self.check()
        self.rewrite_helper(self.helper.read_text().replace('"eligible_ids":["a","b"]', '"eligible_ids":["b","a"]'))
        b = self.check()
        self.assertNotEqual(a['fingerprint'], b['fingerprint'])

    def test_day_expiry_changes_recomputed_eligibility(self):
        source = self.helper.read_text().replace('"eligible_ids":["a"]', '"eligible_ids":(["a"] if today=="2026-11-24" else [])')
        self.rewrite_helper(source)
        a = self.check()
        b = self.check(now=self.now + dt.timedelta(days=1))
        self.assertNotEqual(a['fingerprint'], b['fingerprint'])

    def test_public_fetch_still_runs_on_same_composition(self):
        self.check()
        calls = []

        def fetch(url):
            calls.append(url)
            if url.endswith('/__template_version'):
                return json.dumps(self.metadata)
            return '<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a></section>'
        a = module.проверить_суточные_подборки(self.path, now=self.now, fetch=fetch)
        b = module.проверить_суточные_подборки(self.path, now=self.now, fetch=fetch)
        self.assertEqual(len(calls), 6)
        self.assertEqual(a['fingerprint'], b['fingerprint'])

    def test_local_pair_mismatch(self):
        self.details.write_text(json.dumps({'site': 'pilot', 'catalog_revision': 'old'}))
        self.assertFalse(self.check()['measured'])

    def test_public_pair_mismatch(self):
        self.metadata['details_catalog_revision'] = 'old'
        self.assertFalse(self.check()['measured'])

    def test_public_commit_mismatch(self):
        self.metadata['site_repo_commit'] = 'b' * 40
        self.assertFalse(self.check()['measured'])

    def test_missing_expected_empty_region_healthy(self):
        self.rewrite_helper(self.helper.read_text().replace('"ordered_hrefs":["/title/a/"]', '"ordered_hrefs":[],"absent_region":True'))
        self.assertTrue(self.check('<main>No eligible cards</main>')['healthy'])

    def test_present_expected_empty_region_defect(self):
        self.rewrite_helper(self.helper.read_text().replace('"ordered_hrefs":["/title/a/"]', '"ordered_hrefs":[],"absent_region":True'))
        self.assertFalse(self.check('<section data-collection-policy="top_rated"></section>')['healthy'])

    def test_data_changed_during_public_probe_unmeasured(self):
        self.check()

        def fetch(url):
            if url.endswith('/__template_version'):
                return json.dumps(self.metadata)
            self.source.write_text(json.dumps({'site': 'pilot', 'revision': 'changed'}))
            return '<section data-collection-policy="top_rated"><a class="c" href="/title/a/">A</a></section>'
        self.assertFalse(module.проверить_суточные_подборки(self.path, now=self.now, fetch=fetch)['measured'])

    def test_explicit_live_build_identity(self):
        self.binding['local_runtime']['public_commit_field'] = 'live_build_id'
        self.metadata = {'live_build_id': self.commit[:12] + '-pilot', 'catalog_revision': 'rev1', 'details_catalog_revision': 'rev1'}
        self.assertTrue(self.check()['healthy'])

    def test_legacy_build_id_never_guessed(self):
        self.binding['local_runtime']['public_commit_field'] = 'live_build_id'
        self.metadata = {'build_id': self.commit[:12] + '-pilot', 'catalog_revision': 'rev1', 'details_catalog_revision': 'rev1'}
        self.assertFalse(self.check()['measured'])

    def test_async_expiry_first_lastgood_then_current(self):
        self.check()
        seen = []

        def fetch(url):
            if url.endswith('/__template_version'):
                return json.dumps(self.metadata)
            seen.append(url)
            href = '/title/expired/' if len(seen) == 1 else '/title/a/'
            return '<section data-collection-policy="top_rated"><a class="c" href="' + href + '">A</a></section>'
        r = module.проверить_суточные_подборки(self.path, now=self.now, fetch=fetch, retry_wait=lambda _: None)
        self.assertTrue(r['healthy'])
        self.assertEqual(r['sites'][0]['refresh_confirmations'], 1)
        self.assertEqual(len(seen), 2)

    def test_confirmation_refuses_changed_input(self):
        self.check()

        def fetch(url):
            if url.endswith('/__template_version'):
                return json.dumps(self.metadata)
            self.source.write_text(json.dumps({'site': 'pilot', 'revision': 'changed'}))
            return '<section data-collection-policy="top_rated"></section>'
        r = module.проверить_суточные_подборки(self.path, now=self.now, fetch=fetch, retry_wait=lambda _: None)
        self.assertFalse(r['measured'])
        self.assertEqual(r['sites'][0]['reason'], 'local source pair differs')
        self.assertEqual(r['sites'][0]['source_race_attempts'][0]['reason'], 'source data changed during check')

    def test_confirmation_budget_no_unbounded_wait(self):
        self.check()
        r = module.проверить_суточные_подборки(self.path, now=self.now, fetch=lambda _: '', budget_seconds=0, retry_wait=lambda _: None)
        self.assertFalse(r['measured'])
        self.assertEqual(r['sites'][0]['reason'], 'daily confirmation time budget exhausted')

    def test_async_refresh_waits_for_explicit_readiness(self):
        self.binding['local_runtime']['readiness_path'] = '/__site'
        self.check()
        reads = []
        home = []

        def fetch(url):
            if url.endswith('/__template_version'):
                return json.dumps(self.metadata)
            if url.endswith('/__site'):
                reads.append(url)
                return json.dumps({'site_id': 'pilot', 'freshness': {'reload_in_progress': len(reads) < 4, 'last_error': ''}})
            home.append(url)
            href = '/title/old/' if len(home) == 1 else '/title/a/'
            return '<section data-collection-policy="top_rated"><a class="c" href="' + href + '">A</a></section>'
        r = module.проверить_суточные_подборки(self.path, now=self.now, fetch=fetch, retry_wait=lambda _: None)
        self.assertTrue(r['healthy'])
        self.assertEqual(len(reads), 4)
        self.assertEqual(len(home), 2)

    def test_readiness_error_is_sanitized_and_not_success(self):
        self.binding['local_runtime']['readiness_path'] = '/__site'
        self.check()

        def fetch(url):
            if url.endswith('/__template_version'):
                return json.dumps(self.metadata)
            if url.endswith('/__site'):
                return json.dumps({'site_id': 'pilot', 'freshness': {'reload_in_progress': False, 'last_error': 'SECRET URL instruction'}})
            return ''
        r = module.проверить_суточные_подборки(self.path, now=self.now, fetch=fetch, retry_wait=lambda _: None)
        self.assertFalse(r['measured'])
        self.assertNotIn('SECRET', str(r))
        self.assertEqual(r['sites'][0]['reason'], 'existing site refresh reports an error')
if __name__ == '__main__':
    unittest.main()
