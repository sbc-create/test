import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).parent
NOW=1793880000.0


def load(name, filename):
    spec=importlib.util.spec_from_file_location(name, ROOT/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


MODULES=[load('episode_sync_test_shared','episode_sync.py'),
         load('episode_sync_test_zona02','episode_sync.zona02.py')]


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.details=self.root/'lords-02-details.json'
        self.cache=self.root/'lords-02-new-series.json';self.legacy=self.root/'updates-feed.json'
        self.now='2026-11-05T12:00:00Z'
        from datetime import datetime
        self.epoch=datetime.fromisoformat(self.now.replace('Z','+00:00')).timestamp()

    def write(self, records, schema='k2.episode-feed/1'):
        self.cache.write_text(json.dumps({'schema':schema,'confirmed_episode_slugs':records}))

    def read(self, module):
        with patch.object(module.time,'time',return_value=self.epoch), patch.object(module.urllib.request,'urlopen',side_effect=AssertionError('reader must not use network')):
            return module.лента_изменений(self.details)

    def record(self, slug='confirmed', stamp=None):
        return {'slug':slug,'source_observed_at':stamp or self.now}

    def test_union_preserves_legacy_and_files(self):
        self.legacy.write_text(json.dumps({'schema':'nova.updates-feed/1','built_at':self.now,'items':[{'slug':'legacy'}]}))
        self.write([self.record()])
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}
        for m in MODULES:self.assertEqual(self.read(m),{'legacy','confirmed'})
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()})

    def test_missing_or_bad_cache_keeps_legacy(self):
        self.legacy.write_text(json.dumps({'schema':'nova.updates-feed/1','built_at':self.now,'items':[{'slug':'legacy'}]}))
        for value in [None,'{','[]','null','{"schema":"wrong"}',json.dumps({'schema':'k2.episode-feed/1','confirmed_episode_slugs':{}})]:
            if value is None:
                if self.cache.exists():self.cache.unlink()
            else:self.cache.write_text(value)
            for m in MODULES:self.assertEqual(self.read(m),{'legacy'})

    def test_cache_independent_of_missing_stale_or_invalid_legacy(self):
        self.write([self.record()])
        for value in [None,'{','{"schema":"wrong"}',json.dumps({'schema':'nova.updates-feed/1','built_at':'2000-01-01T00:00:00Z','items':[{'slug':'stale'}]})]:
            if value is None:
                if self.legacy.exists():self.legacy.unlink()
            else:self.legacy.write_text(value)
            for m in MODULES:self.assertEqual(self.read(m),{'confirmed'})

    def test_freshness_offsets_boundaries_and_underflow(self):
        rows=[self.record('now'),self.record('offset','2026-11-05T15:00:00+03:00'),
              self.record('boundary','2026-11-04T12:00:00Z'),
              self.record('stale','2026-11-04T11:59:59.999999Z'),
              self.record('future','2026-11-05T12:00:00.000001Z'),
              self.record('naive','2026-11-05T12:00:00'),self.record('bad','bad'),
              self.record('underflow','0001-01-01T00:00:00+01:00')]
        self.write(rows)
        for m in MODULES:self.assertEqual(self.read(m),{'now','offset','boundary'})

    def test_types_and_dedup(self):
        self.write([None,[],7,{'slug':7,'source_observed_at':self.now},self.record(''),self.record(' '),
                    {'slug':'missing-date'},{'slug':'bad-date','source_observed_at':7},self.record(),self.record()])
        for m in MODULES:self.assertEqual(self.read(m),{'confirmed'})

    def test_exact_schema_and_byte_bound(self):
        self.write([self.record()],schema='k2.episode-feed/2')
        for m in MODULES:self.assertEqual(self.read(m),set())
        self.write([self.record()]);raw=self.cache.read_bytes()
        self.cache.write_bytes(raw+b' '*(8*1024*1024-len(raw)))
        for m in MODULES:self.assertEqual(self.read(m),{'confirmed'})
        with self.cache.open('ab') as stream:stream.write(b' ')
        for m in MODULES:self.assertEqual(self.read(m),set())

    def test_200_record_cap_preserves_unbounded_legacy(self):
        self.write([self.record('new-'+str(i)) for i in range(250)])
        self.legacy.write_text(json.dumps({'schema':'nova.updates-feed/1','built_at':self.now,'items':[{'slug':'old-'+str(i)} for i in range(250)]}))
        expected={'new-'+str(i) for i in range(200)}|{'old-'+str(i) for i in range(250)}
        for m in MODULES:self.assertEqual(self.read(m),expected)

    def test_slugs_are_filtered_by_existing_layers(self):
        self.write([self.record('real'),self.record('unknown'),self.record('film')])
        details={'real':{'year':2026,'seasons':[{'n':1,'eps':2,'avail':2}]},'film':{'seasons':[]}}
        for m in MODULES:
            priorities=m.слои(details,{},2025,названы=self.read(m))
            self.assertEqual(priorities['изменённые'],['real'])
            self.assertNotIn('unknown',sum(priorities.values(),[]))

    def test_wrong_snapshot_filename_does_not_read_other_cache(self):
        self.write([self.record()])
        for m in MODULES:self.assertEqual(m._подтверждённые_серии(self.root/'catalog.json'),set())


if __name__=='__main__':unittest.main()


class CandidateRoleTests(unittest.TestCase):
    def test_candidate_returns_before_runtime_access_or_thread(self):
        import contextlib,io
        for module in MODULES:
            output=io.StringIO()
            with patch.dict(module.os.environ,{'SITE_CELL_ROLE':'candidate'}),patch.object(module.threading,'Thread',side_effect=AssertionError('candidate must not start thread')),contextlib.redirect_stdout(output):
                self.assertFalse(module.запустить(object()))
            self.assertIn('SITE_CELL_ROLE=candidate',output.getvalue())
    def test_main_and_unset_keep_existing_start_behavior(self):
        from types import SimpleNamespace
        runtime=SimpleNamespace(ПЛЕЕР={'publisher_id':'fixture','source_mode':'provider-id'})
        for module in MODULES:
            for role in ['main','']:
                with patch.dict(module.os.environ,{'SITE_CELL_ROLE':role,'LORDS_SITE_HOST':'fixture.invalid'}),patch.object(module.threading,'Thread') as thread:
                    self.assertTrue(module.запустить(runtime));thread.return_value.start.assert_called_once()
