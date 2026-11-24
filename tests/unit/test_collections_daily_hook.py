import ast
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
ROOT = Path(__file__).resolve().parents[2]

class DailyStepTest(unittest.TestCase):

    def test_daily_preserves_last_good_on_unmeasured(self):
        tree = ast.parse((ROOT / 'seo_operator/regular.py').read_text())
        fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'step_editorial'))
        records = []
        ns = {'Context': object, 'Any': object, '_write_json': lambda p, r: records.append(r.copy()), 'daily_collections': lambda *a, **k: {'measured': False, 'healthy': False, 'reason': 'incomplete'}}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'step', 'exec'), ns)
        ctx = types.SimpleNamespace(mode='daily', sources={}, budget=types.SimpleNamespace(remaining=lambda: 60), state={'collections_last_good': {'fingerprint': 'old'}}, journal=types.SimpleNamespace(write=lambda *a, **k: None), step_path=lambda s: s)
        self.assertFalse(ns['step_editorial'](ctx)['healthy'])
        self.assertEqual(ctx.state['collections_last_good'], {'fingerprint': 'old'})
        self.assertFalse(records[0]['measured'])

    def test_healthy_identical_fingerprint_noop(self):
        tree = ast.parse((ROOT / 'seo_operator/regular.py').read_text())
        fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'step_editorial'))
        ns = {'Context': object, 'Any': object, '_write_json': lambda *a: None, 'daily_collections': lambda *a, **k: {'measured': True, 'healthy': True, 'fingerprint': 'same'}}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'step', 'exec'), ns)
        ctx = types.SimpleNamespace(mode='daily', sources={}, budget=types.SimpleNamespace(remaining=lambda: 60), state={'collections_last_good': {'fingerprint': 'same'}}, journal=types.SimpleNamespace(write=lambda *a, **k: None), step_path=lambda s: s)
        self.assertTrue(ns['step_editorial'](ctx)['no_op'])
        self.assertEqual(ctx.state['collections_last_good'], {'fingerprint': 'same'})

class NonfatalDailyLoopTest(unittest.TestCase):

    def test_collections_failure_continues_and_retry_only_failed_steps(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            calls = []
            good = [False]

            def read(path, default=None):
                return json.loads(path.read_text()) if path.exists() else default

            def write(path, value):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))

            class Context(types.SimpleNamespace):

                def step_path(self, step):
                    return self.root / 'runs' / self.run_id / (step + '.json')

                def result(self, step):
                    return read(self.step_path(step))

            class Checkpoint:

                def __init__(self, path):
                    self.path = path

                def completed(self, run):
                    return read(self.path, {}).get(run, [])

                def mark(self, run, step):
                    d = read(self.path, {})
                    d.setdefault(run, []).append(step)
                    write(self.path, d)

            def editorial(ctx):
                calls.append('editorial')
                return {'measured': good[0], 'healthy': good[0]}

            def independent(ctx):
                calls.append('independent')
                return {'ok': True}

            def report(ctx):
                calls.append('report')
                return {'collections': ctx.result('editorial')}
            ns = {'Context': Context, 'Checkpoint': Checkpoint, '_read_json': read, '_write_json': write, '_commit_state': lambda *a: None, '_prune_checkpoints': lambda *a, **k: None, 'Http': lambda *a: None, 'BudgetExceeded': type('BudgetExceeded', (Exception,), {}), 'EXIT_TEMPFAIL': 75, 'EXIT_NEW_CRITICAL': 3, 'utcnow': lambda: dt.datetime.now(dt.timezone.utc), 'iso': lambda v: v.isoformat(), 'PLANS': {'daily': [('editorial', editorial), ('independent', independent), ('report', report)]}}
            tree = ast.parse((ROOT / 'seo_operator/regular.py').read_text())
            fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_run_locked'))
            exec(compile(ast.Module(body=[fn], type_ignores=[]), 'actual_run_loop', 'exec'), ns)
            budget = types.SimpleNamespace(check_time=lambda: None, seconds=100, requests=400, used_requests=0)
            journal = types.SimpleNamespace(write=lambda *a, **k: None)
            args = ('daily', root, 'slot', dt.datetime.now(dt.timezone.utc), journal, budget, {}, None, 'fixture', 1)
            result = ns['_run_locked'](*args)
            self.assertEqual(result['exit_code'], 1)
            self.assertEqual(calls, ['editorial', 'independent', 'report'])
            self.assertEqual(read(root / 'checkpoints.json')['slot'], ['independent'])
            good[0] = True
            calls.clear()
            result = ns['_run_locked'](*args)
            self.assertEqual(result['exit_code'], 0)
            self.assertEqual(calls, ['editorial', 'report'])
if __name__ == '__main__':
    unittest.main()
