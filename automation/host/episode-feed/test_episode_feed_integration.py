import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))
import episode_feed_integration as adapter

A = '12345678-1234-4234-8234-123456789abc'
B = '22345678-1234-4234-8234-123456789abc'
NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.runtime = SimpleNamespace(КАТАЛОГ_ФАЙЛ=str(self.path/'test-catalog.json'))
        self.catalog = [dict(slug='a', title='Site title', url='/canonical/a/', poster='/a.jpg',
                             kind='Сериал', _ck='series'),
                        dict(slug='b', title='Anime', url='/canonical/b/', kind='Сериал', _ck='animation')]
        self.raw = {s: dict(id=i, playable=True, seasons=[dict(n=1, avail=9, eps=9)])
                    for s, i in [('a', A), ('b', B)]}
        self.effective = deepcopy(self.raw)
        for d in self.effective.values():
            d['seasons'][0]['nums'] = [2, 9]
        self.calls = []

        def get(slug):
            self.calls.append(slug)
            return self.effective[slug]

        self.view = SimpleNamespace(п=SimpleNamespace(записи=self.raw), деталь=get)
        self.event = dict(kind='EPISODE_ADDED', titleId=A, playable=True, season=1, episode=2,
                          observedAt='2026-11-04T12:34:56.123+02:00')
        self.write([self.event])

    def write(self, events):
        (self.path/'test-new-series.json').write_text(json.dumps(dict(events=events,
            snapshot={'titles': {A: {'name': 'Do not use', 'poster': 'javascript:bad'}}})))

    def load(self, **kwargs):
        return adapter.load_rows(self.view, self.runtime, 'test', self.catalog, now=NOW, **kwargs)

    def test_runtime_nums_overlay_and_source_metadata(self):
        original = deepcopy(self.raw)
        rows = self.load()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['title'], 'Site title')
        self.assertEqual(rows[0]['url'], '/canonical/a/')
        self.assertEqual(rows[0]['slug'], 'a')
        self.assertEqual(rows[0]['observedAt'], self.event['observedAt'])
        self.assertEqual(self.calls, ['a'])
        self.assertEqual(self.raw, original)

    def test_unknown_removed_and_explicit_unplayable(self):
        self.effective['a']['seasons'][0].pop('nums')
        self.assertEqual(self.load(), [])
        self.effective['a']['seasons'][0]['nums'] = [9]
        self.assertEqual(self.load(), [])
        self.effective['a']['seasons'][0]['nums'] = [2]
        self.effective['a']['playable'] = False
        self.assertEqual(self.load(), [])

    def test_uuid_missing_and_current_identity_change(self):
        self.raw['a'].pop('id')
        self.assertEqual(self.load(), [])
        self.assertEqual(self.calls, [])
        self.raw['a']['id'] = A
        self.effective['a']['id'] = B
        self.assertEqual(self.load(), [])

    def test_filter_before_limit_no_anime_and_no_count_fallback(self):
        self.write([dict(self.event, titleId=B, observedAt='2026-11-04T22:00:00Z'), self.event])
        rows = self.load(eligible=lambda item, detail: item['_ck'] == 'series', limit=1)
        self.assertEqual([r['titleId'] for r in rows], [A])
        self.runtime.доступные_номера = lambda season: self.fail('must not expand counts')
        self.effective['a']['seasons'][0].pop('nums')
        self.assertEqual(self.load(eligible=lambda item, detail: item['_ck'] == 'series'), [])

    def test_one_runtime_get_per_matching_slug(self):
        self.write([self.event, dict(self.event, episode=9), dict(self.event, titleId='bad')])
        self.assertEqual(len(self.load()), 1)
        self.assertEqual(self.calls, ['a'])

    def test_request_detail_cache_can_be_supplied(self):
        rows = self.load(detail_getter=lambda slug: self.effective[slug])
        self.assertEqual(len(rows), 1)
        self.assertEqual(self.calls, [])

    def test_missing_malformed_and_limits(self):
        path = self.path/'test-new-series.json'
        for value in ['null', '[]', '{', '{"events":{}}', '{"events":[null]}']:
            path.write_text(value)
            self.assertEqual(self.load(), [])
        path.unlink()
        self.assertEqual(self.load(), [])
        self.write([self.event])
        old = adapter.MAX_FEED_BYTES
        try:
            adapter.MAX_FEED_BYTES = 5
            self.assertEqual(self.load(), [])
        finally:
            adapter.MAX_FEED_BYTES = old
        self.write([self.event] * (adapter.MAX_EVENTS + 1))
        self.assertEqual(self.load(), [])

    def test_re_read_cache_and_current_availability_each_render(self):
        self.assertEqual(self.load()[0]['episode'], 2)
        self.write([dict(self.event, episode=9)])
        self.assertEqual(self.load()[0]['episode'], 9)
        self.effective['a']['seasons'][0]['nums'] = [2]
        self.assertEqual(self.load(), [])

    def test_all_styles_safe_and_preserve_labels(self):
        row = self.load()[0]
        row.update(title='<script>"&', poster='javascript:bad', episode_url='//bad.test/')
        for style in ['lords', 'zona', 'zona-cc', 'generic']:
            with self.subTest(style=style):
                html = adapter.render_rows([row], style=style)
                self.assertIn('Сезон 1, серия 2', html)
                self.assertIn('Обнаружено у источника: 2026-11-04 13:34:56.123000 МСК', html)
                self.assertIn('datetime="' + self.event['observedAt'] + '"', html)
                self.assertIn('href="/canonical/a/"', html)
                self.assertIn('&lt;script&gt;', html)
                self.assertNotIn('<script>', html)
                self.assertNotIn('javascript:', html)
                self.assertNotIn('style=', html)
                self.assertEqual(adapter.render_rows([], style=style), '')
        row['episode_url'] = '/watch/2?x=1&y=2'
        self.assertIn('href="/watch/2?x=1&amp;y=2"', adapter.render_rows([row], style='zona-cc'))
        row['url'] = 'javascript:bad'
        row.pop('episode_url')
        self.assertEqual(adapter.render_rows([row], style='lords'), '')




if __name__ == "__main__":
    unittest.main()
