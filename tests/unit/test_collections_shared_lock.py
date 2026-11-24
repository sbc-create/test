import ast,datetime,json,os,pathlib,runpy,tempfile,time,types,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[2]
REGULAR=ROOT/'seo_operator/regular.py'
scheduler=runpy.run_path(str(ROOT/'seo_operator/scheduler.py'))
def load_run(path,legacy=False):
 source=path.read_text();source=source.replace('stale_after=max(limit[0] for limit in LIMITS.values()) * 3','stale_after=seconds * 3') if legacy else source
 tree=ast.parse(source);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
 limits=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LIMITS' for t in n.targets))
 ns={'Path':pathlib.Path,'os':os,'FileLock':scheduler['FileLock'],'LockBusy':scheduler['LockBusy'],'PLANS':{'hourly':[],'daily':[]},'utcnow':lambda:datetime.datetime.now(datetime.timezone.utc),'slot_id':lambda *a:'fixture','Journal':lambda *a:types.SimpleNamespace(write=lambda *a,**k:None),'Budget':lambda *a:None,'SOURCES':{},'EXIT_TEMPFAIL':75,'_run_locked':lambda *a:{'state':'EXECUTED'}}
 module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),limits,fn],type_ignores=[]);exec(compile(ast.fix_missing_locations(module),str(path),'exec'),ns);return ns['run']
class Test(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=pathlib.Path(self.t.name)
 def lock(self,pid,age):
  (self.root/'run.lock').write_text(json.dumps({'pid':pid,'acquired_epoch':time.time()-age,'owner':'daily'}))
 def test_prior_hourly_steals_live_daily(self):
  self.lock(os.getpid(),240);self.assertEqual(load_run(REGULAR,legacy=True)('hourly',root=self.root)['state'],'EXECUTED')
 def test_new_hourly_preserves_live_daily_and_file(self):
  self.lock(os.getpid(),240);before=(self.root/'run.lock').read_bytes();self.assertEqual(load_run(REGULAR)('hourly',root=self.root)['state'],'LOCK_BUSY');self.assertEqual((self.root/'run.lock').read_bytes(),before)
 def test_dead_pid_recovery_preserved(self):
  self.lock(99999999,1)
  self.assertEqual(load_run(REGULAR)('hourly',root=self.root)['state'],'EXECUTED')
 def test_daily_same_shared_threshold(self):
  self.lock(os.getpid(),240);self.assertEqual(load_run(REGULAR)('daily',root=self.root)['state'],'LOCK_BUSY')
