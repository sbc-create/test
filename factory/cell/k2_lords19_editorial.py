"""Dedicated native editorial queue for lords-19; fixed target, no arbitrary commands."""
import datetime,fcntl,hashlib,json,os,pathlib,subprocess,time,urllib.request
from factory.cell import editorial_store,queue
SITE='lords-19';DOMAIN='lordserials1.info'
BASE=pathlib.Path('/var/lib/site-cells-k2-lords19');CACHE=BASE/'cache'
SSH=['ssh','-i','/home/claude/.ssh/k2deploy-zomro-01','-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=/home/claude/wt-nova-publish-memory-02/inventory/known_hosts.d/k2-zomro-01','-o','ConnectTimeout=10','-o','ControlMaster=auto','-o','ControlPersist=120','-o','ControlPath=/home/claude/.ssh/k2-%r-%h-%p','k2deploy@145.63.129.86']
class Refused(RuntimeError):pass
def need(v,msg):
 if not v:raise Refused(msg)
def canonical(d):return editorial_store.текст(d).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,d):queue.записать_атомарно(p,d)
def remote(command,body=None,timeout=30):
 p=subprocess.run(SSH+[command],input=body,capture_output=True,timeout=timeout)
 need(p.returncode==0,'fixed target operation refused: '+p.stderr.decode(errors='replace')[-1000:]);return p.stdout

def refresh(force=False):
 path=CACHE/'status.json'
 if not force and path.is_file() and time.time()-path.stat().st_mtime<60:return json.loads(path.read_text())
 CACHE.mkdir(parents=True,exist_ok=True)
 info=json.loads(remote('/usr/local/sbin/k2-lords19-editorial-receiver --inspect'))
 need(info['site_id']==SITE and info['domain']==DOMAIN and info['contract_verified'] is True,'target identity/consumer mismatch')
 with urllib.request.urlopen('https://'+DOMAIN+'/healthz',timeout=15) as r:
  health=json.loads(r.read());need(r.status==200,'public runtime unavailable')
 need(health.get('ok') is True and info.get('runtime_digest_match') is True,'authenticated running code digest mismatch')
 # Target metadata comes over pinned authenticated SSH, public liveness over TLS.
 overlay=CACHE/'editorial-overrides.json';doc=info.pop('overlay')
 if doc is None:
  if overlay.exists():overlay.unlink()
 else:
  body=canonical(doc);need(sha(body)==info['overlay_sha256'],'remote overlay canonical hash mismatch')
 # queue.save uses pretty JSON; mirror must preserve the native byte digest.
 if doc is not None:
  tmp=overlay.with_suffix('.tmp');tmp.write_bytes(body);os.replace(tmp,overlay)
 facts=CACHE/'lords-19-details.json'
 if not facts.exists() or sha(facts.read_bytes())!=info['details_sha256']:
  body=remote('cat /srv/lordserials1-info/data/lords-19-details.json',timeout=90)
  need(len(body)<180*1024*1024 and sha(body)==info['details_sha256'],'fact snapshot mismatch')
  d=json.loads(body);need(d.get('site')==SITE,'fact snapshot site mismatch');tmp=facts.with_suffix('.tmp');tmp.write_bytes(body);os.replace(tmp,facts)
 info['verified_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save(path,info);return info

SOURCE=pathlib.Path('/home/claude/wt-nova-publish-memory-02/var/new-sites/lords-19')
def source_identity(info):
 cfg=json.loads((SOURCE/'config/site.json').read_text());need(cfg['site_id']==SITE and cfg['domain']==DOMAIN and str(cfg['publisher_id_expected'])=='10620','own source identity mismatch')
 need((SOURCE/'.git').exists(),'own site git repository missing')
 head=subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip()
 dirty=subprocess.check_output(['git','-C',str(SOURCE),'status','--porcelain'],text=True).strip()
 need(not dirty and head==info['runtime_commit'],'own source must be clean and match installed full commit')
 return head

def ready():
 try:return refresh()['contract_verified'] is True
 except (OSError,ValueError,Refused,subprocess.SubprocessError):return False

def make_envelope(document,before):
 prior=before or {'overrides':{}};changed=[k for k in set(prior['overrides'])|set(document['overrides']) if prior['overrides'].get(k)!=document['overrides'].get(k)]
 need(len(changed)<=1,'remote publication may change only one title')
 return {'site_id':SITE,'expected_before_sha256':sha(canonical(before)) if before is not None else None,'changed_title_id':changed[0] if changed else None,'content':document}

def submit(site,document,commit):
 need(site==SITE and document['site_id']==SITE,'exact site required')
 baseline=json.loads((CACHE/'status.json').read_text())['overlay_sha256']
 info=refresh(True);need(info['overlay_sha256']==baseline,'remote state changed since native merge')
 need(commit==source_identity(info),'requested release differs from verified own source')
 before=json.loads((CACHE/'editorial-overrides.json').read_text()) if info['overlay_sha256'] else None
 env=make_envelope(document,before);digest=editorial_store.отпечаток(document)
 if env['changed_title_id'] is None:
  return {'backend':'k2-editorial-queue','entries':len(document['overrides']),'content_digest':digest,'status':'unchanged','request_id':None}
 request=queue.собрать(SITE,commit,digest,operation='editorial',snapshot=digest.split(':')[1],note='Native exact-domain editorial delivery')
 save(BASE/'envelopes'/(request.request_id+'.json'),env);queue.подать(request,база=BASE)
 end=time.monotonic()+240
 while time.monotonic()<end:
  status=queue.состояние(request.request_id,база=BASE,не_раньше=request.submitted_at)
  if status.get('status')=='finished':
   result=status.get('result',status);need(result.get('status')=='ok',result.get('error','remote editorial executor failed'));after=refresh(True);need(after['overlay_sha256']==digest.split(':')[1],'remote delivered hash mismatch')
   return {'backend':'k2-editorial-queue','request_id':request.request_id,'content_digest':digest,'entries':len(document['overrides']),'store':str(CACHE/'editorial-overrides.json')}
  time.sleep(2)
 raise Refused('Exact-domain editorial queue timed out; request remains inspectable')

STAGE_SCRIPT="""import os,pathlib,sys
p=pathlib.Path('/home/k2deploy/stage/editorial-lords19');p.mkdir(mode=0o700,exist_ok=True)
assert not p.is_symlink()
b=sys.stdin.buffer.read(2097153);assert len(b)<=2097152
f=os.open(str(p/'pending.tmp'),os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
with os.fdopen(f,'wb') as out:out.write(b);out.flush();os.fsync(out.fileno())
os.replace(p/'pending.tmp',p/'pending.json')
"""

def deliver(request,envelope):
 need(request.site_id==SITE and request.operation=='editorial','executor exact site and operation required')
 doc=envelope['content'];need(editorial_store.отпечаток(doc)==request.digest,'request digest mismatch');info=refresh(True);need(request.commit==source_identity(info),'live release or own source changed')
 # Byte-for-byte canonical envelope makes success and refusal receipts correlate.
 body=canonical(envelope);request_sha=sha(body)
 import shlex
 remote('python3 -c '+shlex.quote(STAGE_SCRIPT),body)
 until=time.monotonic()+100
 while time.monotonic()<until:
  try:r=json.loads(remote('cat /var/lib/k2-lords19-editorial/latest.json'))
  except (Refused,ValueError):r={}
  if r.get('request_sha256')==request_sha:
   need(r.get('status') in ['applied','already_applied'],r.get('error','receiver refused'));need(r['after_sha256']==request.digest.split(':')[1],'receipt digest mismatch');refresh(True);return r
  time.sleep(2)
 raise Refused('Receiver did not return this request receipt within100s')

def worker():
 BASE.mkdir(exist_ok=True)
 with (BASE/'worker.lock').open('w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  for path in sorted((BASE/'requests').glob('*.json'))[:1]:
   r=queue.разобрать(json.loads(path.read_text()));started=datetime.datetime.now(datetime.timezone.utc).isoformat()
   result={'request_id':r.request_id,'site_id':r.site_id,'operation':r.operation,'started_at':started}
   try:
    envelope=json.loads((BASE/'envelopes'/(r.request_id+'.json')).read_text());receipt=deliver(r,envelope);result.update(status='ok',outcome={'status':'edited','receipt':receipt})
   except Exception as e:result.update(status='failed',error=str(e))
   result['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save(BASE/'results'/(r.request_id+'.json'),result);path.unlink();print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':worker()
