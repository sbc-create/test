#!/usr/bin/env python3
"""Fixed lords-18 native catalog receiver; old process serves during restart."""
import datetime,fcntl,hashlib,json,os,pathlib,re,shutil,subprocess,time,urllib.request
P=pathlib.Path
SID='lords-18';ROOT=P('/srv/lordserials1-cc');INCOMING=P('/home/k2deploy/stage/incoming-lords18');STATE=P('/var/lib/k2-lords18-catalog');LOCK=P('/run/lock/k2-lords18-catalog.lock');UP=P('/etc/nginx/cells/lords-18.upstream')
UNIT='nova-lordserials1-cc.service';CANDIDATE='nova-lordserials1-cc-candidate.service';APPLY='/usr/local/sbin/k2-catalog-apply.sh';MANIFEST=P('/home/k2deploy/stage/MANIFEST.json')
NAMES=[SID+'-'+k+'.json' for k in ['catalog','details','data-provenance']]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def run(*args,**kw):return subprocess.run(args,check=True,**kw)
def health(port,release):
 deadline=time.monotonic()+180
 while time.monotonic()<deadline:
  try:
   with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/healthz',timeout=5) as r:d=json.load(r)
   if str(d.get('runtime_path','')).startswith(str(release)+'/') and d.get('runtime_digest_match'):return d
  except Exception:pass
  time.sleep(2)
 raise RuntimeError('health timeout port '+str(port))
def protected():
 cfg=json.loads((ROOT/'current/config/site.json').read_text());out={}
 for p in [ROOT/'data'/s for s in cfg['data_contract']['user_writable']]+[ROOT/'current/config/player.json',P(cfg['indexing']['runtime_state_file']),P('/etc/nginx/cells/lords-18.robots')]:
  if p.is_symlink():out[str(p)]={'symlink':os.readlink(p)}
  elif p.is_dir():out[str(p)]={str(x.relative_to(p)):sha(x) for x in p.rglob('*') if x.is_file()}
  else:out[str(p)]=sha(p) if p.is_file() else None
 return out
def atomic_copy(src,dst):
 tmp=dst.with_name('.'+dst.name+'.safe-tmp');owner=dst.stat();shutil.copy2(src,tmp);os.chown(tmp,owner.st_uid,owner.st_gid);tmp.replace(dst)
def route(data):
 previous=UP.read_bytes();tmp=UP.with_suffix('.safe-tmp');tmp.write_bytes(data);tmp.replace(UP)
 try:run('nginx','-t');run('systemctl','reload','nginx')
 except Exception:
  UP.write_bytes(previous);run('nginx','-t');run('systemctl','reload','nginx');raise

def acknowledge(box,hashes):
 # A changed/failed queue acknowledgement never rolls back a healthy installation.
 try:
  if not all((box/n).is_file() and not (box/n).is_symlink() and sha(box/n)==h for n,h in hashes.items()):return False
  shutil.rmtree(box);return True
 except OSError:return False

def prune_jobs():
 # Lock excludes other writers; keep at most six attempts, including failures.
 jobs=sorted(p for p in STATE.iterdir() if p.is_dir() and not p.is_symlink() and re.fullmatch(r"[0-9]{8}T[0-9]{6}\.[0-9]{6}Z",p.name))
 for p in jobs[:-5]:shutil.rmtree(p)

def apply_locked():
 box=INCOMING/SID
 if not box.exists():return 'empty'
 assert box.is_dir() and not box.is_symlink()
 assert all((box/n).is_file() and not (box/n).is_symlink() for n in NAMES+['SHA256SUMS'])
 c=json.loads(MANIFEST.read_text())['cells'][SID]
 assert (c['account'],int(c['port']),c['unit'],c.get('reload','restart'))==('lordserials1-cc',9136,UNIT,'restart')
 original=UP.read_bytes();assert original==b'server 127.0.0.1:9136;\n'
 assert subprocess.run(['systemctl','is-active','--quiet',CANDIDATE]).returncode!=0
 link=ROOT/'candidate';assert not link.exists() and not link.is_symlink()
 hashes={n:sha(box/n) for n in NAMES}
 if all((ROOT/'data'/n).is_file() and sha(ROOT/'data'/n)==h for n,h in hashes.items()):
  return 'unchanged' if acknowledge(box,hashes) else 'unchanged; queue retained'
 old=(ROOT/'current').resolve();health(9136,old);before=protected()
 STATE.mkdir(parents=True,exist_ok=True);prune_jobs();job=STATE/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');job.mkdir(mode=0o700)
 private=job/'incoming';(private/SID).mkdir(parents=True)
 for n in NAMES+['SHA256SUMS']:shutil.copy2(box/n,private/SID/n)
 assert all(sha(private/SID/n)==h for n,h in hashes.items()),'incoming mutated during snapshot'
 env={**os.environ,'K2_INCOMING':str(private),'K2_MANIFEST':str(MANIFEST)}
 run(APPLY,'--check-only',SID,env=env)
 backup=job/'before';backup.mkdir();present=[]
 for n in NAMES:
  if (ROOT/'data'/n).exists():shutil.copy2(ROOT/'data'/n,backup/n);present.append(n)
 (job/'protected-before.json').write_text(json.dumps(before,sort_keys=True))
 link.symlink_to(old)
 try:
  run('systemctl','start',CANDIDATE);health(10136,old);route(b'server 127.0.0.1:10136;\n')
  run(APPLY,SID,env=env);health(9136,old)
  assert (ROOT/'current').resolve()==old,'concurrent code release'
  assert all(sha(ROOT/'data'/n)==h for n,h in hashes.items()),'installed digest mismatch'
  after=protected();assert after==before,'protected data changed'
  route(original);run('systemctl','stop',CANDIDATE);link.unlink()

 except Exception as e:
  (job/'failure.txt').write_text(str(e))
  run('systemctl','start',CANDIDATE);health(10136,old);route(b'server 127.0.0.1:10136;\n')
  for n in NAMES:
   if n in present:atomic_copy(backup/n,ROOT/'data'/n)
   elif (ROOT/'data'/n).exists():(ROOT/'data'/n).unlink()
  run('systemctl','restart',UNIT);health(9136,old);route(original);run('systemctl','stop',CANDIDATE)
  if link.is_symlink():link.unlink()
  raise
 acknowledged=acknowledge(box,hashes)
 (job/'success.json').write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'installed':hashes,'protected_unchanged':True,'release':str(old),'queue_acknowledged':acknowledged},indent=2))
 return 'applied' if acknowledged else 'applied; queue retained'

def main():
 assert os.geteuid()==0
 LOCK.parent.mkdir(parents=True,exist_ok=True)
 with LOCK.open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:print('lords-18 catalog: busy');return
  print('lords-18 catalog:',apply_locked())
if __name__=='__main__':main()
