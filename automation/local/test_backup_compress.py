import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('backup_compress', Path(__file__).with_name('backup-compress.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class CompressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def put(self, site='one', day=1, kind='catalog'):
        p = self.root / f'{site}-{kind}.json.before.daily-202610{day:02}T010000Z'
        p.write_bytes(b'{"items": [1, 2, 3]}\n' * 100)
        return p

    def test_plan_protects_dates_pairs_and_unknown_files(self):
        for day in range(1, 11):
            for kind in ('catalog', 'details'):
                self.put(day=day, kind=kind)
        for day in (1, 2):
            for kind in ('catalog', 'details'):
                self.put('quiet', day, kind)
        self.put('orphan', 1)
        self.put('invalid', 99)
        (self.root / 'unrelated.json').write_text('keep')
        (self.root / 'linked-catalog.json.before.daily-20261001T010000Z').symlink_to('unrelated.json')
        chosen = mod.plan(self.root)
        self.assertEqual(len(chosen), 6)
        self.assertTrue(all(p.name.startswith('one-') for p in chosen))
        self.assertTrue(all(p.name[-16:-8] in ('20261001', '20261002', '20261003') for p in chosen))

    def test_verified_archive_restores_exact_bytes(self):
        p = self.put()
        original = p.read_bytes()
        mod.compress_one(p)
        self.assertFalse(p.exists())
        self.assertEqual(gzip.decompress(Path(str(p) + '.gz').read_bytes()), original)
        self.assertEqual(list(self.root.glob('.compress-*')), [])

    def test_failed_verification_preserves_source(self):
        p = self.put()
        original = p.read_bytes()
        with patch.object(mod.gzip, 'open', side_effect=gzip.BadGzipFile('injected corruption')):
            with self.assertRaises(gzip.BadGzipFile):
                mod.compress_one(p)
        self.assertEqual(p.read_bytes(), original)
        self.assertFalse(Path(str(p) + '.gz').exists())
        self.assertEqual(list(self.root.glob('.compress-*')), [])

    def test_existing_archive_is_not_overwritten(self):
        p = self.put()
        dest = Path(str(p) + '.gz')
        dest.write_bytes(b'existing archive')
        with self.assertRaises(FileExistsError):
            mod.compress_one(p)
        self.assertTrue(p.exists())
        self.assertEqual(dest.read_bytes(), b'existing archive')

    def test_concurrent_source_change_is_preserved(self):
        p = self.put()
        original_open = gzip.open
        def change_then_open(*args, **kwargs):
            p.write_bytes(b'new publisher data')
            return original_open(*args, **kwargs)
        with patch.object(mod.gzip, 'open', side_effect=change_then_open):
            with self.assertRaisesRegex(RuntimeError, 'source changed'):
                mod.compress_one(p)
        self.assertEqual(p.read_bytes(), b'new publisher data')
        self.assertFalse(Path(str(p) + '.gz').exists())


if __name__ == '__main__':
    unittest.main()
