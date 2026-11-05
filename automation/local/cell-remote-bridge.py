#!/usr/bin/env python3
"""One-shot LOCAL relay. CONTROL owns queue/CI/lock; the admin key stays LOCAL."""
import argparse
import hashlib
import ipaddress
import json
import re
from pathlib import Path
import shlex
import subprocess
import tempfile

MAX=64*1024*1024
PACKAGE_ROOT='/usr/local/lib/site-factory-cell/bridge-packages'
APPROVED={
    'lords-02':('107.189.23.212','lordserial33.biz'),
    'lords-03':('107.189.23.234','1lordserials1.online'),
    'lords-05':('107.189.23.194','lordserials22.info'),
    'zona-01':('107.189.20.242','zonafilm.space'),
    'zona-02':('107.189.25.39','zonafilm.cc'),
    'zona-03':('107.189.20.48','zonafilm12.site'),
}
NATIVE_PROPERTIES=['LoadCredential=gh-token:/etc/site-factory/gh-token','NoNewPrivileges=no',
    'ProtectHome=read-only','ProtectKernelTunables=yes','ProtectKernelModules=yes',
    'RestrictSUIDSGID=yes','RestrictRealtime=yes','LockPersonality=yes','TimeoutStartSec=0',
    'ReadWritePaths=/home/claude/wt-portable-site-cell-01/config /usr/local/lib/site-factory-cell/config']
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no',
     '-o','ForwardAgent=no','-o','IdentityAgent=none','-o','ConnectTimeout=10']


def gateway_command(package_id,request_id):
    if not re.fullmatch('[0-9a-f]{64}',package_id):raise ValueError('Exact reviewed package identity required')
    package=PACKAGE_ROOT+'/'+package_id
    command=['systemd-run','--pipe','--wait','--collect','--quiet','--working-directory='+package]
    for value in NATIVE_PROPERTIES:command.extend(['-p',value])
    return command+[package+'/bin/k2-native-gateway','--request',request_id]


def expected_target(args):
    host=str(ipaddress.ip_address(args.expected_host))
    if host=='145.63.129.86':raise ValueError('Owner explicitly forbids contacting this address')
    if args.expected_site not in APPROVED or APPROVED[args.expected_site][0]!=host:
        raise ValueError('Target is outside the six approved site/host pairs')
    if not re.fullmatch('[0-9a-f]{40}',args.expected_commit) or not re.fullmatch('sha256:[0-9a-f]{64}',args.expected_digest):
        raise ValueError('Exact expected commit and artifact digest required')
    return host


def validate_header(message,args):
    expected=expected_target(args)
    if set(message)!={'method','binding','profile','bytes'} or message['method']!='активировать':
        raise ValueError('Only closed activate RPC is permitted')
    profile=message['profile'];binding=message['binding'];request=binding['request']
    actual=str(ipaddress.ip_address(profile['target']['host']))
    if actual=='145.63.129.86' or actual!=expected:raise ValueError('CONTROL host differs from approved expected target')
    if (profile['cell']['site_id'],profile['cell']['domain'])!=(args.expected_site,APPROVED[args.expected_site][1]):
        raise ValueError('CONTROL profile differs from approved expected site')
    if any(request.get(key)!=value for key,value in [('operation','activate'),('site_id',args.expected_site),('commit',args.expected_commit),('digest',args.expected_digest)]):
        raise ValueError('CONTROL request differs from approved exact release')
    if profile.get('package_sha256')!=args.package_id or binding.get('package_sha256')!=args.package_id:
        raise ValueError('CONTROL package differs from pinned package')
    if binding.get('profile_sha256')!=hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':')).encode()).hexdigest():
        raise ValueError('CONTROL profile hash differs')
    if not re.fullmatch('[0-9a-f]{64}',binding.get('capsule_sha256','')):raise ValueError('Invalid capsule digest')
    size=message['bytes']
    if type(size) is not int or not 0<size<=MAX:raise ValueError('Capsule exceeds relay bound')
    return actual


def result_code(message,args):
    if message.get('method')!='result' or not isinstance(message.get('result'),dict):return 1
    result=message['result']
    if result.get('site_id')!=args.expected_site or result.get('commit')!=args.expected_commit:return 1
    if result.get('status') in {'busy','reconcile','waiting-bridge'}:return 75
    outcome=result.get('outcome') or {}
    return 0 if (result.get('status')=='ok' and outcome.get('status')=='activated' and
                 outcome.get('stage')=='live_verified' and outcome.get('digest')==args.expected_digest) else 1


def line(stream):
    raw=stream.readline(1048577)
    if len(raw)>1048576 or not raw.endswith(b'\n'):raise ValueError('Missing/bounded native bridge packet')
    return raw,json.loads(raw)


def finish_control(control):
    if control.stdin and not control.stdin.closed:control.stdin.close()
    try:return control.wait(timeout=30)
    except subprocess.TimeoutExpired:
        control.terminate()
        try:return control.wait(timeout=10)
        except subprocess.TimeoutExpired:control.kill();return control.wait(timeout=5)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--control',default='claude-control-01');parser.add_argument('--request',required=True)
    parser.add_argument('--admin-key',type=Path,required=True);parser.add_argument('--package-id',required=True)
    for field in ['site','host','commit','digest']:parser.add_argument('--expected-'+field,required=True)
    args=parser.parse_args();expected_target(args)
    if not args.admin_key.is_file():raise ValueError('LOCAL admin identity does not exist')
    command=gateway_command(args.package_id,args.request)
    control=subprocess.Popen(SSH+[args.control,shlex.join(command)],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
        raw,message=line(control.stdout)
        if message.get('method')=='result':
            status=result_code(message,args)
            # An early result never proves a successful remote transaction.
            if status==0:status=1
            print(json.dumps(message,ensure_ascii=False,indent=2))
            return status if finish_control(control)==0 else 1
        address=validate_header(message,args)  # Before ANY K2 SSH.
        with tempfile.TemporaryFile() as capsule:
            left=message['bytes'];digest=hashlib.sha256()
            while left:
                chunk=control.stdout.read(min(left,1048576))
                if not chunk:raise EOFError('CONTROL capsule stream truncated')
                capsule.write(chunk);digest.update(chunk);left-=len(chunk)
            if digest.hexdigest()!=message['binding']['capsule_sha256']:raise ValueError('CONTROL capsule bytes differ from binding')
            capsule.seek(0)
            target=subprocess.Popen(SSH+['-o','IdentitiesOnly=yes','-i',str(args.admin_key),'root@'+address,PACKAGE_ROOT+'/'+args.package_id+'/bin/k2-native-worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
            try:
                target.stdin.write(raw)
                while chunk:=capsule.read(1048576):target.stdin.write(chunk)
                target.stdin.close();receipt,_=line(target.stdout)
                if target.wait(timeout=30)!=0:raise RuntimeError('Trusted target worker failed')
                control.stdin.write(receipt);control.stdin.flush()
            finally:
                if target.poll() is None:target.terminate();target.wait(timeout=10)
        _,result=line(control.stdout);exit_status=result_code(result,args)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return exit_status if finish_control(control)==0 else 1
    finally:
        if control.poll() is None:finish_control(control)
        for stream in [control.stdin,control.stdout]:
            if stream and not stream.closed:stream.close()


if __name__=='__main__':raise SystemExit(main())
