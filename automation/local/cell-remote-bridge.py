#!/usr/bin/env python3
"""One-shot LOCAL relay. CONTROL owns queue/CI/lock; the admin key stays LOCAL."""
import argparse
import ipaddress
import json
import re
from pathlib import Path
import shlex
import subprocess
import tempfile

MAX=64*1024*1024
PACKAGE_ROOT='/usr/local/lib/site-factory-cell/bridge-packages'
NATIVE_PROPERTIES=['LoadCredential=gh-token:/etc/site-factory/gh-token','NoNewPrivileges=no',
    'ProtectHome=read-only','ProtectKernelTunables=yes','ProtectKernelModules=yes',
    'RestrictSUIDSGID=yes','RestrictRealtime=yes','LockPersonality=yes','TimeoutStartSec=0',
    'ReadWritePaths=/home/claude/wt-portable-site-cell-01/config /usr/local/lib/site-factory-cell/config']

def gateway_command(package_id,request_id):
    if not re.fullmatch('[0-9a-f]{64}',package_id):raise ValueError('Exact reviewed package identity required')
    package=PACKAGE_ROOT+'/'+package_id
    command=['systemd-run','--pipe','--wait','--collect','--quiet','--working-directory='+package]
    for value in NATIVE_PROPERTIES:command.extend(['-p',value])
    return command+[package+'/bin/k2-native-gateway','--request',request_id]
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no','-o','ForwardAgent=no','-o','ConnectTimeout=15']


def line(stream):
    raw=stream.readline(1048577)
    if len(raw)>1048576 or not raw.endswith(b'\n'):raise ValueError('Missing/bounded native bridge packet')
    return raw,json.loads(raw)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--control',default='claude-control-01');parser.add_argument('--request',required=True);parser.add_argument('--admin-key',type=Path,required=True);parser.add_argument('--package-id',required=True)
    args=parser.parse_args()
    if not args.admin_key.is_file():raise ValueError('LOCAL admin identity does not exist')
    control=subprocess.Popen(SSH+[args.control,shlex.join(gateway_command(args.package_id,args.request))],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
        raw,message=line(control.stdout)
        if message.get('method')=='result':print(json.dumps(message));return
        if message.get('method')!='активировать':raise ValueError('Unknown CONTROL RPC')
        address=str(ipaddress.ip_address(message['profile']['target']['host']))
        size=message['bytes']
        if type(size) is not int or not 0<size<=MAX:raise ValueError('Capsule exceeds relay bound')
        with tempfile.TemporaryFile() as capsule:
            left=size
            while left:
                chunk=control.stdout.read(min(left,1048576))
                if not chunk:raise EOFError('CONTROL capsule stream truncated')
                capsule.write(chunk);left-=len(chunk)
            capsule.seek(0)
            target=subprocess.Popen(SSH+['-o','IdentitiesOnly=yes','-i',str(args.admin_key),'root@'+address,PACKAGE_ROOT+'/'+args.package_id+'/bin/k2-native-worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
            try:
                target.stdin.write(raw)
                while chunk:=capsule.read(1048576):target.stdin.write(chunk)
                target.stdin.close()
                receipt,_=line(target.stdout)
                if target.wait(timeout=30)!=0:raise RuntimeError('Trusted target worker failed')
                control.stdin.write(receipt);control.stdin.flush()
            finally:
                if target.poll() is None:target.terminate();target.wait(timeout=10)
        _,result=line(control.stdout)
        if control.wait(timeout=30)!=0:raise RuntimeError('CONTROL gateway failed')
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        if control.poll() is None:
            control.stdin.close();control.terminate();control.wait(timeout=10)


if __name__=='__main__':main()
