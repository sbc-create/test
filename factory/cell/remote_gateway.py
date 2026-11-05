"""Root CONTROL gateway. Native выполнить remains CI/queue/lock authority."""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import secrets
import pwd
import subprocess
import sys
import tempfile
from factory.cell import executor, queue, registry
from factory.cell.remote_apply import VERSION, fingerprint, exclusive
from factory.cell.remote_capsule import prepare


def packet(stream,value):
    raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode()
    if len(raw)>65536:raise ValueError('RPC header exceeds bound')
    stream.write(raw);stream.flush()


def read_packet(stream):
    line=stream.readline(1048577)
    if len(line)>1048576:raise ValueError('RPC response exceeds bound')
    if not line.endswith(b'\n'):raise ConnectionError('Lost/incomplete RPC response')
    return json.loads(line)


def immutable_request(request):
    # Native stage history changes on retry; release identity must not.
    value=asdict(request);value['stages']=[]
    return value


def activation_source(cell,request,*,check_live=True):
    """Explicit root-registry binding; never repoint the ordinary repo fields."""
    declared=((cell.runtime or {}).get('code_delivery') or {}).get('source_path')
    if not isinstance(declared,str) or not declared:
        raise ValueError('Canonical code_delivery.source_path binding is required')
    source=Path(declared)
    if not source.is_absolute() or '..' in source.parts:
        raise ValueError('Activation source must be an absolute canonical path')
    from factory.cell.remote_capsule import normalized_remote
    origin=(cell.repo or {}).get('remote') or ''
    identity={'path':str(source),'commit':request.commit,'origin':origin}
    if not check_live:return source,identity
    if source.resolve()!=source or not source.is_dir():raise ValueError('Activation source must be an existing real directory')
    owner=pwd.getpwuid(source.stat().st_uid)
    if owner.pw_uid==0:raise ValueError('Activation source must belong to a nonroot source account')
    def git(*args):
        return subprocess.run(['sudo','-u',owner.pw_name,'--','git','-C',str(source),*args],
            capture_output=True,text=True,check=True,env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GIT_OPTIONAL_LOCKS='0')).stdout.strip()
    if git('rev-parse','HEAD')!=request.commit or git('status','--porcelain'):
        raise ValueError('Bound source must be clean at the exact requested commit')
    if normalized_remote(git('remote','get-url','origin'))!=normalized_remote(origin):
        raise ValueError('Bound worktree origin differs from declared repository')
    return source,identity


class Gateway:
    def __init__(self,request_bytes,wire_out,wire_in):
        self.request_bytes=request_bytes;self.output=wire_out;self.input=wire_in
    def activate(self,request,*,файл,dry_run):
        if dry_run:return {'status':'dry-run','stage':'validated','transport':'local-ssh-bridge'}
        cell=registry.resolve(request.site_id);delivery=(cell.runtime or {}).get('code_delivery') or {}
        if delivery.get('role')!='local-ssh-bridge':raise ValueError('No canonical remote activation role')
        profile=delivery.get('profile')
        if not isinstance(profile,dict) or profile['cell']['site_id']!=request.site_id:raise ValueError('Missing exact canonical host projection')
        # One native CONTROL owner, including across different target sites.
        with exclusive(queue.БАЗА/'locks'/'local-ssh-bridge.guard',busy_error=executor.SiteBusy):
            state=queue.БАЗА/'state'/(request.request_id+'.remote.json')
            source,source_binding=activation_source(cell,request,check_live=False)
            stable={'source_binding':source_binding,'request':immutable_request(request),'profile_sha256':fingerprint(profile),'package_sha256':profile['package_sha256'],
                    'expected_old_commit':delivery['expected_current']}
            if state.exists():
                saved=json.loads(state.read_bytes())
                if saved['stable']!=stable:raise ValueError('Immutable queued request/profile changed during retry')
            else:
                saved={'stable':stable,'nonce':secrets.token_hex(32),
                       'request_sha256':hashlib.sha256(self.request_bytes).hexdigest(),
                       'original_request_utf8':self.request_bytes.decode('utf-8')}
                queue.записать_атомарно(state,saved)
            cached=queue.БАЗА/'packages'/(request.request_id+'.source.tar.gz')
            if not saved.get('capsule_sha256'):
                activation_source(cell,request,check_live=True)
                with tempfile.TemporaryDirectory(prefix='native-bridge-') as tmp:
                    generated,metadata=prepare(source,request,(cell.repo or {})['remote'],stable['expected_old_commit'],Path(tmp)/'prepared')
                    from factory.cell.rollback_state import atomic
                    atomic(cached,generated.read_bytes(),0o400)
                saved['capsule_sha256']=hashlib.sha256(cached.read_bytes()).hexdigest()
                queue.записать_атомарно(state,saved)
            if cached.is_symlink() or not cached.is_file() or cached.stat().st_uid!=0 or cached.stat().st_mode & 0o222:
                raise ValueError('Cached source capsule is not root-sealed')
            if hashlib.sha256(cached.read_bytes()).hexdigest()!=saved['capsule_sha256']:
                raise ValueError('Frozen source capsule changed during retry')
            capsule=cached
            binding=dict(schema=VERSION,nonce=saved['nonce'],request=stable['request'],request_sha256=saved['request_sha256'],
                         profile_sha256=stable['profile_sha256'],package_sha256=stable['package_sha256'],
                         expected_old_commit=stable['expected_old_commit'],capsule_sha256=saved['capsule_sha256'])
            packet(self.output,{'method':'активировать','binding':binding,'profile':profile,'bytes':capsule.stat().st_size})
            with capsule.open('rb') as stream:
                while chunk:=stream.read(1048576):self.output.write(chunk)
            self.output.flush()
            try:
                response=read_packet(self.input)
            except (ConnectionError,OSError,EOFError,ValueError) as error:
                raise executor.BridgeUncertain('Target receipt uncertain; replay same nonce: '+str(error)) from error
            if set(response)!={'nonce','binding_sha256','outcome'} or response['nonce']!=binding['nonce'] or response['binding_sha256']!=fingerprint(binding):
                raise executor.BridgeUncertain('RPC receipt identity mismatch; retain original request and reconcile')
            outcome=response['outcome']
            if not isinstance(outcome,dict):raise executor.BridgeUncertain('RPC outcome malformed; retain request for reconciliation')
            return outcome


def serve(request_id,*,dry_run=False):
    if os.geteuid()!=0:raise PermissionError('Native root gateway required')
    if not queue.ЗАПРОС_ID.fullmatch(request_id):raise ValueError('Invalid queued request ID')
    path=queue.БАЗА/'requests'/(request_id+'.json')
    raw=path.read_bytes();request=queue.разобрать(json.loads(raw))
    if request.request_id!=request_id or request.operation!='activate':raise ValueError('Only exact existing activate requests may be bridged')
    if not executor.remote_bridge_required(request.site_id):
        outcome={'request_id':request_id,'site_id':request.site_id,'commit':request.commit,
                 'status':'rejected','error':'Gateway only serves canonical local-ssh-bridge activation requests'}
        packet(sys.stdout.buffer,{'method':'result','result':outcome})
        return outcome
    gateway=Gateway(raw,sys.stdout.buffer,sys.stdin.buffer)
    with redirect_stdout(sys.stderr):
        outcome=executor.выполнить(request,база=queue.БАЗА,dry_run=dry_run,activate_handler=gateway.activate)
    if outcome.get('status') not in {'busy','waiting-bridge','reconcile'}:
        queue.записать_атомарно(queue.БАЗА/'results'/path.name,outcome)
        path.unlink(missing_ok=True)
    packet(sys.stdout.buffer,{'method':'result','result':outcome})
    return outcome


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--request',required=True);parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args();serve(args.request,dry_run=args.dry_run)
