"""Exact shallow Git capsule, prepared as repository owner; never root build."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tarfile
from factory.cell import privileged
from factory.cell.remote_apply import VERSION, MAX_BYTES


def normalized_remote(value):return value.rstrip('/').removesuffix('.git')


def git(repo,*args):
    r=subprocess.run(['git','--no-replace-objects','-c','safe.directory='+str(repo),'-C',str(repo),*args],capture_output=True,text=True,check=True,
                     env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GIT_OPTIONAL_LOCKS='0'))
    return r.stdout.strip()


def validate_source(source,request,remote):
    import configparser
    config=configparser.ConfigParser(interpolation=None)
    config.read(source/'.git/config')
    allowed={'core':{'repositoryformatversion','filemode','bare','logallrefupdates'}, 'remote "origin"':{'url','fetch'}}
    if set(config.sections())-set(allowed):raise ValueError('Forbidden Git configuration section')
    for section in config.sections():
        if set(config[section])-allowed[section]:raise ValueError('Forbidden Git configuration key')
    for name in ['commondir','info/grafts','refs/replace','objects/info/alternates']:
        if (source/'.git'/name).exists():raise ValueError('Git indirection forbidden: '+name)
    packed=source/'.git/packed-refs'
    if packed.exists() and 'refs/replace/' in packed.read_text():raise ValueError('Packed replacement refs forbidden')
    git(source,'fsck','--full','--strict','--no-reflogs')
    # Do not trust index stat flags, assume-unchanged, skip-worktree, or excludes.
    tree=subprocess.run(['git','--no-replace-objects','-c','safe.directory='+str(source),'-C',str(source),
                         'ls-tree','-rz','--full-tree',request.commit],capture_output=True,check=True).stdout
    tracked=set()
    for entry in tree.split(b'\0'):
        if not entry:continue
        header,name=entry.split(b'\t',1);mode,kind,oid=header.split()
        relative=Path(os.fsdecode(name))
        if relative.is_absolute() or '..' in relative.parts or '.git' in relative.parts:
            raise ValueError('Unsafe committed path')
        if mode not in [b'100644',b'100755'] or kind!=b'blob':raise ValueError('Only regular committed source files accepted')
        path=source/relative
        if path.is_symlink() or not path.is_file():raise ValueError('Tracked file missing or replaced')
        if bool(path.stat().st_mode & 0o111)!=(mode==b'100755'):raise ValueError('Tracked executable mode differs')
        if git(source,'hash-object','--no-filters','--',str(path))!=oid.decode():raise ValueError('Tracked source bytes differ from commit')
        tracked.add(str(relative))
    actual={str(p.relative_to(source)) for p in source.rglob('*') if p.relative_to(source).parts[0]!='.git' and (p.is_file() or p.is_symlink())}
    if actual!=tracked:raise ValueError('Extra or missing source files, including ignored files')
    if git(source,'ls-files','--others'):raise ValueError('Untracked source files forbidden, including ignored files')
    if git(source,'rev-parse','HEAD')!=request.commit:raise ValueError('Capsule commit mismatch')
    if git(source,'status','--porcelain','--untracked-files=all'):raise ValueError('Capsule is not clean')
    if normalized_remote(git(source,'remote','get-url','origin'))!=normalized_remote(remote):raise ValueError('Capsule remote mismatch')
    if (source/'.git/shallow').read_text().splitlines()!=[request.commit]:raise ValueError('Capsule must be shallow at exact commit')
    config=git(source,'config','--local','--list')
    if any(x in config.lower() for x in ['include.','includeif.','credential.','sshcommand','hookspath','fsmonitor','gitproxy']):
        raise ValueError('Executable/credential Git configuration is forbidden')
    if (source/'.git/objects/info/alternates').exists():raise ValueError('External Git objects forbidden')
    for p in (source/'.git/hooks').glob('*'):
        if not p.name.endswith('.sample'):raise ValueError('Executable Git hooks forbidden')


def prepare(repo,request,remote,expected_old,destination):
    repo=Path(repo);destination=Path(destination)
    owner=pwd.getpwuid(repo.stat().st_uid)
    if owner.pw_uid==0:raise ValueError('Source preparation must not run as root')
    os.chmod(destination.parent,0o711)
    destination.mkdir(mode=0o700)
    shutil.chown(destination,owner.pw_name,owner.pw_name)
    def run(*args):
        r=subprocess.run(['sudo','-u',owner.pw_name,*args],capture_output=True,text=True,check=True,
                         env=dict(os.environ,GIT_TERMINAL_PROMPT='0',PYTHONDONTWRITEBYTECODE='1'))
        return r.stdout.strip()
    if normalized_remote(run('git','-C',str(repo),'remote','get-url','origin'))!=normalized_remote(remote):raise ValueError('Registered repository remote mismatch')
    run('git','-C',str(repo),'merge-base','--is-ancestor',expected_old,request.commit)
    source=destination/'source'
    run('git','init','-q',str(source))
    run('git','-C',str(source),'fetch','--quiet','--no-tags','--depth=1','file://'+str(repo.resolve()),request.commit)
    run('git','-C',str(source),'checkout','--quiet','--detach',request.commit)
    run('git','-C',str(source),'remote','add','origin',remote)
    # Root's later Git reader is explicitly scoped, as in the native builder.
    env_args=['git','--no-replace-objects','-c','safe.directory='+str(source),'-C',str(source)]
    actual=subprocess.run(env_args+['rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    if actual!=request.commit:raise ValueError('Prepared source differs from requested commit')
    validate_source(source,request,remote)
    artifact,manifest=privileged.собрать_без_прав(source,destination/'build',owner.pw_name)
    artifact=Path(artifact)
    artifact.resolve().relative_to((destination/'build').resolve())
    if artifact.is_symlink() or artifact.stat().st_uid!=owner.pw_uid:raise ValueError('Unsafe build output')
    if manifest.get('site_id')!=request.site_id or manifest.get('source_commit')!=request.commit or manifest.get('source_dirty'):
        raise ValueError('Native builder did not produce a clean exact commit')
    digest='sha256:'+hashlib.sha256(artifact.read_bytes()).hexdigest()
    if manifest.get('digest')!=digest or digest!=request.digest:raise ValueError('Native build does not reproduce accepted artifact digest')
    # Build output is not included: target rebuilds the same exact source.
    metadata={'schema':VERSION,'site_id':request.site_id,'commit':request.commit,'remote':remote,
              'artifact_digest':digest,'live_build_id':manifest.get('live_build_id')}
    (destination/'capsule.json').write_text(json.dumps(metadata,sort_keys=True)+'\n')
    capsule=destination/'capsule.tar.gz'
    with tarfile.open(capsule,'w:gz') as tar:
        tar.add(destination/'capsule.json',arcname='capsule.json')
        for path in sorted(source.rglob('*')):
            if path.is_symlink():raise ValueError('Source symlinks require separate review')
            if '__pycache__' in path.parts:continue
            tar.add(path,arcname='source/'+str(path.relative_to(source)),recursive=False)
    if capsule.stat().st_size>MAX_BYTES:raise ValueError('Capsule exceeds bound')
    return capsule,metadata
