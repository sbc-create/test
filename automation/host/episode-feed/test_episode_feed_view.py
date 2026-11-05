import unittest
from datetime import datetime, timezone
from episode_feed_view import select_events, render_section


A = '12345678-1234-4234-8234-123456789abc'
B = '22345678-1234-4234-8234-123456789abc'


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [dict(slug='a', title='Title', url='/series/a', poster='/a.jpg'),
                        dict(slug='b', title='Other', url='/series/b')]
        self.details = {s: dict(id=i, seasons=[dict(n=1, avail=True, eps=9, nums=[2, 9])])
                        for s, i in [('a', A), ('b', B)]}
        self.event = dict(kind='EPISODE_ADDED', titleId=A, observedAt='2026-11-01T12:00:00.123+02:00',
                          season=1, episode=2, playable=True)

    def select(self, events=None, **kwargs):
        return select_events([self.event] if events is None else events, self.catalog, self.details,
                             now=datetime(2026, 11, 2, tzinfo=timezone.utc), **kwargs)

    def test_exact_id(self):
        for ident in [None, 'invalid', B.replace('2', '3')]:
            with self.subTest(ident=ident):
                self.assertEqual(self.select([dict(self.event, titleId=ident, title='Title')]), [])
        del self.details['a']['id']
        self.assertEqual(self.select(), [])

    def test_availability(self):
        self.assertEqual(self.select([dict(self.event, episode=3)]), [])
        season = self.details['a']['seasons'][0]
        del season['nums']
        self.assertEqual(self.select(), [])
        self.assertEqual(len(self.select(current_available=lambda d, s, e: True)), 1)
        season['nums'] = []
        self.assertEqual(self.select(current_available=lambda *args: True), [])
        season.update(nums=[2], avail=False)
        self.assertEqual(self.select(), [])

    def test_invalid_events(self):
        for change in [dict(playable=False), dict(playable=1), dict(season=0), dict(episode=-1),
                       dict(episode=True), dict(kind='OTHER'), dict(observedAt='2026-11-03T00:00:00Z'),
                       dict(observedAt='2026-11-01T00:00:00'), dict(observedAt='bad')]:
            with self.subTest(change=change):
                self.assertEqual(self.select([dict(self.event, **change)]), [])

    def test_utc_dedupe_limit_and_allowed(self):
        events = [self.event, dict(self.event, titleId=B, observedAt='2026-11-01T11:30:00+00:00'),
                  dict(self.event, episode=9, observedAt='2026-11-01T14:00:00+03:00')]
        rows = self.select(events)
        self.assertEqual([r['titleId'] for r in rows], [B, A])
        self.assertEqual(rows[1]['episode'], 9)
        self.assertEqual(len(self.select(events, limit=1)), 1)
        self.assertEqual(self.select(events, allowed=[]), [])
        self.assertEqual([r['titleId'] for r in self.select(events, allowed=[A])], [A])
        self.assertEqual(self.select(events, limit=0), [])

    def test_time_labels_and_classes(self):
        row = self.select()[0]
        self.assertEqual(row['observedAt'], self.event['observedAt'])
        html = render_section([row], classes={'section': 'existing'})
        self.assertIn('<section class="existing"><h2>Новые серии</h2>', html)
        self.assertIn('Сезон 1, серия 2', html)
        self.assertIn('Обнаружено у источника: 2026-11-01 13:00:00.123000 МСК', html)
        self.assertIn('datetime="' + self.event['observedAt'] + '"', html)
        self.assertIn('href="/series/a"', html)
        self.assertNotIn('style=', html)

    def test_malicious_content_and_urls(self):
        self.catalog[0].update(title='<script>"&', poster='javascript:alert(1)')
        row = self.select([dict(self.event, episode_url='//evil.test/x')])[0]
        html = render_section([row], heading='<bad>', classes={'card': 'x" onclick="bad'})
        self.assertNotIn('<script>', html)
        self.assertNotIn('javascript:', html)
        self.assertIn('&lt;script&gt;&quot;&amp;', html)
        self.assertIn('<h2>&lt;bad&gt;</h2>', html)
        self.assertIn('href="/series/a"', html)
        for url in ['javascript:alert(1)', '//evil.test', '/\\evil.test', '/x\nfoo']:
            self.catalog[0]['url'] = url
            self.assertEqual(self.select(), [])

    def test_event_urls_never_override_matched_catalog(self):
        row = self.select([dict(self.event, episode_url='/watch/2?a=1&b=2')])[0]
        self.assertNotIn('episode_url', row)
        self.assertIn('href="/series/a"', render_section([row]))
        self.assertIn('href="/series/a"', render_section([dict(row, episode_url='/title/other/')]))
        row = self.select([dict(self.event, episode_url='https://evil.test/2')])[0]
        self.assertNotIn('episode_url', row)

    def test_utc_conversion_underflow_fails_closed(self):
        event = dict(self.event, observedAt='0001-01-01T00:00:00+01:00')
        self.assertEqual(self.select([event]), [])
        self.assertNotIn('<li', render_section([event]))

    def test_equal_timestamp_stable(self):
        rows = self.select([self.event, dict(self.event, episode=9), dict(self.event, titleId=B)])
        self.assertEqual([r['titleId'] for r in rows], [A, B])
        self.assertEqual(rows[0]['episode'], 2)


if __name__ == '__main__':
    unittest.main()
