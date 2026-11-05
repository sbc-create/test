"""Installed root entry point. No queue, credential, or arbitrary command input."""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import tempfile


def trusted_json(path):
    path=Path(path);st=path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_mode & 0o222:
        raise PermissionError('Trusted profile/package metadata must be root-owned and read-only')
    return json.loads(path.read_bytes())


def main(profile_path,package_path):
    if os.geteuid()!=0:raise PermissionError('Installed root worker required')
    # This function is entered by a root-owned isolated wrapper which clears
    # Python/Git/SITE/CELL environment BEFORE importing factory modules.
    from factory.cell import registry
    from factory.cell.remote_apply import MAX_BYTES, NativeBackend, fingerprint, transact, unpack_capsule, validate_binding
    from factory.cell.remote_capsule import validate_source
    from factory.cell.remote_gateway import packet,read_packet
    profile=trusted_json(profile_path);package=trusted_json(package_path)
    from factory.cell.remote_package import verify
    verify(Path(package_path).parent.parent,package)
    if profile['package_sha256']!=package['package_sha256']:raise ValueError('Installed package identity mismatch')
    request=read_packet(sys.stdin.buffer)
    if set(request)!={'method','binding','profile','bytes'} or request['method']!='активировать':raise ValueError('Only native activate RPC is allowed')
    binding=request['binding'];native_request=validate_binding(binding,profile)
    if request['profile']!=profile:raise ValueError('Payload cannot redefine installed scoped profile')
    size=request['bytes']
    if type(size) is not int or not 0<size<=MAX_BYTES:raise ValueError('Invalid bounded payload size')
    def interrupted(signum,frame):raise ConnectionError('Bridge session interrupted')
    for sig in [signal.SIGHUP,signal.SIGTERM]:signal.signal(sig,interrupted)
    wire=sys.stdout.buffer
    with tempfile.TemporaryDirectory(prefix='native-remote-') as tmp:
        root=Path(tmp);os.chmod(root,0o711)
        archive=root/'capsule.tar.gz';h=hashlib.sha256()
        with archive.open('wb') as stream:
            left=size
            while left:
                chunk=sys.stdin.buffer.read(min(left,1048576))
                if not chunk:raise EOFError('Truncated source capsule')
                stream.write(chunk);h.update(chunk);left-=len(chunk)
        if h.hexdigest()!=binding['capsule_sha256']:raise ValueError('Transferred capsule digest mismatch')
        source,metadata=unpack_capsule(archive,root/'payload',binding['capsule_sha256'])
        if metadata['commit']!=native_request.commit or metadata['site_id']!=native_request.site_id or metadata['artifact_digest']!=native_request.digest:
            raise ValueError('Capsule metadata differs from native request')
        validate_source(source,native_request,profile['cell']['repo']['remote'])
        # Seal executable input. The native site-account builder can READ it
        # and write only its separate native output directory.
        for p in source.rglob('*'):
            os.chmod(p,0o555 if p.is_dir() or p.stat().st_mode & 0o111 else 0o444)
        os.chmod(source,0o555);os.chmod(source.parent,0o711)
        cell=json.loads(json.dumps(profile['cell']));cell['repo']['path']=str(source)
        projection=root/'projection.json';projection.write_text(json.dumps({'schema_version':'1.0','cells':[cell]}));projection.chmod(0o400)
        backend=NativeBackend(native_request.site_id,source,profile,request_path=root/'.no-target-queue-request')
        with registry.scoped_projection(projection,native_request.site_id),redirect_stdout(sys.stderr):
            outcome=transact(binding,profile,backend)
        # Receipt is fsynced by transact BEFORE any ACK is written.
        packet(wire,{'nonce':binding['nonce'],'binding_sha256':fingerprint(binding),'outcome':outcome})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--profile',required=True);parser.add_argument('--package',required=True)
    args=parser.parse_args();main(args.profile,args.package)
