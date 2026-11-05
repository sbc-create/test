"""Closed, durable native activation transaction. No queue or CI credentials here."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import hashlib
import gzip
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile

from factory.cell import executor, privileged, queue, registry
from factory.cell.rollback_state import atomic

VERSION='k2.native-bridge/1'
MAX_BYTES=64*1024*1024
RECEIPTS=Path('/var/lib/site-factory-cell/receipts')
HEX40=re.compile(r'^[0-9a-f]{40}$')
HEX64=re.compile(r'^[0-9a-f]{64}$')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def validate_binding(binding, profile):
    fields={'schema','nonce','request','request_sha256','profile_sha256','package_sha256','capsule_sha256','expected_old_commit'}
    if set(binding)!=fields or binding['schema']!=VERSION:raise ValueError('Closed bridge schema required')
    for key in ['nonce','request_sha256','profile_sha256','package_sha256','capsule_sha256']:
        if not HEX64.fullmatch(binding[key]):raise ValueError('Invalid '+key)
    request=queue.разобрать(binding['request'])
    if request.operation!='activate' or not HEX40.fullmatch(binding['expected_old_commit']):raise ValueError('Activate identity required')
    cell=profile['cell']
    if request.site_id!=cell['site_id']:raise ValueError('Wrong site')
    if fingerprint(profile)!=binding['profile_sha256']:raise ValueError('Wrong scoped profile')
    if binding['package_sha256']!=profile['package_sha256']:raise ValueError('Wrong trusted package')
    if ((cell.get('runtime') or {}).get('code_delivery') or {}).get('role')!='local-ssh-bridge':
        raise ValueError('Canonical runtime has no local SSH code-delivery role')
    return request


@contextmanager
def exclusive(path):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:os.close(fd)


def unpack_capsule(archive: Path, destination: Path, expected_sha: str):
    if archive.stat().st_size>MAX_BYTES:raise ValueError('Capsule exceeds compressed bound')
    h=hashlib.sha256()
    with archive.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    if h.hexdigest()!=expected_sha:raise ValueError('Capsule digest mismatch')
    destination.mkdir(mode=0o700)
    # Bound the entire decoded tar, including headers/PAX metadata, before
    # tarfile allocates member records. Data-size sums alone miss header bombs.
    with archive.open('rb') as probe:
        compressed=probe.read(2)==b'\x1f\x8b'
    with tempfile.TemporaryFile() as decoded:
        opener=gzip.open if compressed else open
        with opener(archive,'rb') as stream:
            total=0
            while chunk:=stream.read(1048576):
                total+=len(chunk)
                if total>MAX_BYTES:raise ValueError('Capsule exceeds decoded bound')
                decoded.write(chunk)
        decoded.seek(0)
        return _extract(decoded,destination)


def _extract(decoded,destination):
    with tarfile.open(fileobj=decoded,mode='r:') as tar:
        members=tar.getmembers()
        if len(members)>20000 or sum(x.size for x in members)>MAX_BYTES:
            raise ValueError('Capsule exceeds expanded bound')
        seen=set()
        for m in members:
            if len(m.name)>1024:raise ValueError('Capsule path exceeds bound')
            p=Path(m.name)
            if str(p) in seen:raise ValueError('Duplicate capsule member')
            seen.add(str(p))
            m.mode &= 0o777
            m.uid=m.gid=0;m.uname=m.gname=''
            if p.is_absolute() or '..' in p.parts or not (m.isfile() or m.isdir()):
                raise ValueError('Unsafe capsule member')
            if not p.parts or p.parts[0] not in {'source','capsule.json'}:raise ValueError('Unexpected capsule member')
        tar.extractall(destination,members=members)
    metadata=json.loads((destination/'capsule.json').read_bytes())
    if metadata.get('schema')!=VERSION:raise ValueError('Wrong capsule version')
    return destination/'source',metadata


def transact(binding,profile,backend,*,state_root=RECEIPTS):
    """The production backend calls native активировать, never replaces it.

    Receipt lookup precedes old-current checks. A successful lost-ACK replay
    verifies actual runtime and returns the full stored outcome without install.
    """
    request=validate_binding(binding,profile)
    state_root.mkdir(parents=True,exist_ok=True,mode=0o700)
    with exclusive(state_root/'.candidate.lock'):
        path=state_root/(binding['nonce']+'.json')
        if path.exists():
            saved=json.loads(path.read_bytes())
            if saved['binding']!=binding:raise ValueError('Nonce reused for different immutable request')
            if saved.get('outcome') is not None:
                outcome=saved['outcome']
                if outcome.get('status')=='activated':backend.verify_replay(request,outcome)
                return outcome
            # Never reinstall an already-active release after interrupted ACK.
            if backend.is_current(request):
                outcome=backend.reconcile(request)
                atomic(path,(json.dumps({'binding':binding,'outcome':outcome})+'\n').encode())
                return outcome
            raise ValueError('Interrupted transaction requires reconciliation; no automatic reinstall')
        if backend.is_current(request):
            # Missing receipt is not permission to overwrite the running tree.
            raise ValueError('Requested release already active without matching receipt')
        backend.preflight(request,binding['expected_old_commit'],profile)
        atomic(path,(json.dumps({'binding':binding,'outcome':None})+'\n').encode())
        try:
            outcome=backend.activate(request)
        except Exception as error:
            recovery=backend.recover(request)
            outcome={'status':'failed','stage':'failed','error':type(error).__name__+': '+str(error),
                     'steps':{'recovery':recovery}}
        atomic(path,(json.dumps({'binding':binding,'outcome':outcome},ensure_ascii=False)+'\n').encode())
        return outcome


class NativeBackend:
    """Only trusted native functions; registry projection is root-sealed."""
    def __init__(self,site_id,source,profile,*,systemctl=privileged._systemctl,request_path=RECEIPTS/'never-request.json'):
        self.site_id=site_id;self.source=Path(source);self.profile=profile;self.systemctl=systemctl;self.request_path=Path(request_path)
    def platform(self):return privileged.Площадка.из_реестра(self.site_id)
    def current_record(self):
        p=self.platform()
        for name in ['release-installed.json','release-manifest.json']:
            f=p.current/name
            if f.is_file():
                d=json.loads(f.read_bytes())
                if d.get('source_commit') or d.get('commit'):
                    d['source_commit']=d.get('source_commit') or d['commit'];return d
        f=p.current/'config/template-manifest.json'
        d=json.loads(f.read_bytes())
        return {'source_commit':d.get('site_repo_commit'),'live_build_id':d.get('build_id')}
    def is_current(self,request):
        return self.current_record().get('source_commit')==request.commit
    def verify_replay(self,request,outcome):
        if not self.is_current(request):raise ValueError('Receipt no longer matches current runtime')
        record=self.current_record()
        if record.get('digest',record.get('artifact_digest'))!=request.digest:
            raise ValueError('Current installed digest differs from receipt')
        verdict=privileged.verify(self.site_id,ожидаемый_build=outcome['build_id'])
        updater=privileged.сверить_обработчик(self.site_id)
        if not verdict.get('ok') or (updater.get('declared') and not updater.get('согласован')):
            raise ValueError('Runtime/updater replay verification failed')
    def reconcile(self,request):
        record=self.current_record();build=record.get('live_build_id') or record.get('build_id')
        if not build:raise ValueError('Cannot prove active build identity')
        out={'status':'activated','stage':'live_verified','build_id':build,'digest':request.digest,
             'steps':{'reconciled':True}}
        self.verify_replay(request,out);return out
    def preflight(self,request,expected_old,profile):
        p=self.platform();runtime=profile['cell']['runtime']
        import ipaddress,subprocess
        expected_host=str(ipaddress.ip_address(profile['target']['host']))
        interfaces=json.loads(subprocess.run(['/usr/sbin/ip','-j','address','show'],capture_output=True,text=True,check=True).stdout)
        if expected_host not in {a['local'] for interface in interfaces for a in interface.get('addr_info',[])}:
            raise ValueError('Target host identity differs from scoped profile')
        if self.current_record().get('source_commit')!=expected_old:raise ValueError('Expected old commit changed')
        p.current.resolve().relative_to(p.releases.resolve())
        for key in ['unit','account','port']:
            if getattr(p,key)!=runtime[key]:raise ValueError('Native platform differs from scoped profile')
        unit=self.systemctl('show',p.unit,'-p','ExecStart','-p','User','-p','WorkingDirectory').stdout
        if str(p.current/'run.py') not in unit or '--port '+str(p.port) not in unit or p.account not in unit:
            raise ValueError('Observed native unit differs from profile')
        route=privileged.UPSTREAM_КАТАЛОГ/(self.site_id+'.upstream')
        if route.read_text().strip()!='server 127.0.0.1:'+str(p.port)+';':raise ValueError('Observed upstream differs from profile')
        if not privileged._upstream_включён(route):raise ValueError('Native upstream is not included')
        if self.systemctl('is-active','--quiet',p.candidate_unit,проверять=False).returncode==0:
            raise ValueError('Another candidate is active')
        # Bound concurrent live + candidate memory without adding swap/config.
        mem={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemAvailable:','SwapFree:'))}
        pid=int(self.systemctl('show',p.unit,'-p','MainPID','--value').stdout.strip())
        actual_env=dict(part.split(b'=',1) for part in Path('/proc/'+str(pid)+'/environ').read_bytes().split(b'\0') if b'=' in part)
        if actual_env.get(b'LORDS_CATALOG',b'').decode()!=profile['target'].get('catalog'):
            raise ValueError('Observed process catalog differs from canonical scoped profile')
        rss=next(int(l.split()[1])*1024 for l in Path('/proc/'+str(pid)+'/status').read_text().splitlines() if l.startswith('VmRSS:'))
        if mem['MemAvailable']+mem['SwapFree']<rss+512*1024**2:raise ValueError('Insufficient RAM plus free swap for one candidate')
        if profile['target'].get('catalog')!=str(p.data/(self.site_id+'-catalog.json')):
            raise ValueError('Profile does not bind catalog identity')
    def activate(self,request):
        if self.request_path.exists():raise ValueError('Remote native request path must not exist')
        return executor.активировать(request,файл=self.request_path,dry_run=False)
    def recover(self,request):
        p=self.platform()
        if p.candidate.exists() and p.candidate.resolve().name==request.commit[:12]:
            return privileged.rollback(self.site_id,dry_run=False)
        return {'no_live_mutation_detected':True}
