"""Durable native code rollback; user data is never copied or restored."""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import tempfile
import time

STATE_ROOT = Path('/var/lib/site-factory-cell/rollback')


def atomic(path: Path, payload: bytes, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.'+path.name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def snapshot_file(path: Path):
    if path.is_symlink(): return {'kind':'symlink','target':os.readlink(path)}
    if not path.exists(): return {'kind':'absent'}
    if not path.is_file(): raise ValueError('Rollback input is not a file')
    return {'kind':'file','mode':path.stat().st_mode & 0o777,
            'data':base64.b64encode(path.read_bytes()).decode('ascii')}


def restore_file(path: Path, record):
    if record['kind']=='absent': path.unlink(missing_ok=True)
    elif record['kind']=='file': atomic(path,base64.b64decode(record['data']),record['mode'])
    elif record['kind']=='symlink':
        temp=path.with_name('.'+path.name+'.restore')
        temp.unlink(missing_ok=True);temp.symlink_to(record['target']);os.replace(temp,path)
    else: raise ValueError('Unknown rollback record')


def snapshot_dropins(directory):
    if not directory.exists():return {'kind':'absent'}
    if directory.is_symlink() or not directory.is_dir():raise ValueError('Unsafe unit drop-in directory')
    files=list(directory.iterdir())
    if len(files)>100:raise ValueError('Too many unit drop-ins')
    if any(p.is_dir() or (p.is_file() and p.stat().st_size>65536) for p in files):
        raise ValueError('Unsupported unit drop-in structure')
    return {'kind':'directory','mode':directory.stat().st_mode & 0o777,
            'files':{p.name:snapshot_file(p) for p in files}}


def restore_dropins(directory,record):
    if directory.is_symlink():raise ValueError('Unit drop-in directory changed to symlink')
    if directory.exists():
        for p in directory.iterdir():
            if p.is_dir():raise ValueError('Unexpected nested unit drop-in directory')
            p.unlink()
    if record['kind']=='absent':
        if directory.exists():directory.rmdir()
        return
    directory.mkdir(parents=True,exist_ok=True);directory.chmod(record['mode'])
    for name,value in record['files'].items():
        if Path(name).name!=name:raise ValueError('Unsafe drop-in name')
        restore_file(directory/name,value)


def enable_links(unit_dir,name):
    links={}
    for pattern in ['*.wants/'+name,'*.requires/'+name]:
        for path in unit_dir.glob(pattern):
            if path.parent.is_symlink() or not path.is_symlink():raise ValueError('Unsupported unit enable link')
            links[str(path.relative_to(unit_dir))]=snapshot_file(path)
    return links


def restore_enable_links(unit_dir,name,saved):
    for relative in enable_links(unit_dir,name):
        (unit_dir/relative).unlink()
    for relative,record in saved.items():
        parts=Path(relative).parts
        if len(parts)!=2 or parts[1]!=name or not parts[0].endswith(('.wants','.requires')):
            raise ValueError('Unsafe saved unit enable link')
        path=unit_dir/relative;path.parent.mkdir(exist_ok=True)
        restore_file(path,record)


def capture(platform, unit_dir: Path, upstream_dir: Path, updater, systemctl,
            *, old_build_id: str, new_build_id: str='', state_root: Path=STATE_ROOT):
    if not old_build_id:raise ValueError('Previous HTTP build identity required')
    old=platform.current.resolve(strict=True);new=platform.candidate.resolve(strict=True)
    if old==new: raise ValueError('Candidate is already current; reconcile receipt instead')
    old.relative_to(platform.releases.resolve());new.relative_to(platform.releases.resolve())
    units={platform.unit}
    if platform.previous_unit:units.add(platform.previous_unit)
    if updater:units.update([updater.service,updater.timer])
    records={}
    for name in sorted(units):
        if Path(name).name!=name:raise ValueError('Unsafe unit name')
        records[name]={'file':snapshot_file(unit_dir/name),
                       'dropins':snapshot_dropins(unit_dir/(name+'.d')),
                       'enable_links':enable_links(unit_dir,name),
                       'active':systemctl('is-active','--quiet',name,проверять=False).returncode==0,
                       'enabled':systemctl('is-enabled','--quiet',name,проверять=False).returncode==0}
    state={'schema':'native-rollback/1','site_id':platform.site_id,
           'old_current':str(old),'new_current':str(new),'units':records,
           'old_build_id':old_build_id,'new_build_id':new_build_id,'phase':'captured',
           'upstream':snapshot_file(upstream_dir/(platform.site_id+'.upstream'))}
    path=state_root/(platform.site_id+'.json')
    atomic(path,(json.dumps(state,sort_keys=True)+'\n').encode())
    return {'checkpoint':str(path),'old_current':str(old),'new_current':str(new)}


def restore(platform, unit_dir: Path, upstream_dir: Path, systemctl,
            *, wait_ready, state_root: Path=STATE_ROOT):
    path=state_root/(platform.site_id+'.json')
    if not path.is_file():return None
    state=json.loads(path.read_bytes())
    if state.get('schema')!='native-rollback/1' or state.get('site_id')!=platform.site_id:
        raise ValueError('Invalid rollback identity')
    # An older checkpoint must not roll back an unrelated fresh candidate.
    if str(platform.candidate.resolve())!=state['new_current']:return None
    if str(platform.current.resolve()) not in (state['new_current'],state['old_current']):
        raise ValueError('Current changed outside this transaction')
    old=Path(state['old_current']);old.relative_to(platform.releases.resolve())
    if not old.is_dir():raise ValueError('Previous release is missing')
    state['phase']='restoring_units';atomic(path,(json.dumps(state)+'\n').encode())
    # Stop newly introduced inactive/absent units before their files disappear.
    for name,record in state['units'].items():
        if not record['active']:
            systemctl('disable',name,проверять=False)
            systemctl('stop',name,проверять=False)
            status=systemctl('is-active','--quiet',name,проверять=False).returncode
            if status not in (3,4):raise ValueError('Cannot prove inactive unit stopped before removal')
    link=platform.root/'.current.restore';link.unlink(missing_ok=True)
    link.symlink_to(old);os.replace(link,platform.current)
    for name,record in state['units'].items():
        if Path(name).name!=name:raise ValueError('Unsafe rollback unit')
        restore_file(unit_dir/name,record['file'])
        restore_dropins(unit_dir/(name+'.d'),record['dropins'])
    systemctl('daemon-reload')
    for name,record in state['units'].items():
        if record['file']['kind']!='absent' and record['file'].get('target')!='/dev/null':
            systemctl('enable' if record['enabled'] else 'disable',name,проверять=False)
        restore_enable_links(unit_dir,name,record['enable_links'])
    systemctl('daemon-reload')
    for name,record in state['units'].items():
        if record['active']:systemctl('restart',name)
    state['phase']='waiting_old_http';atomic(path,(json.dumps(state)+'\n').encode())
    verdict=wait_ready(state['old_build_id'])
    if not verdict.get('ok') or verdict.get('build_id')!=state['old_build_id']:
        raise ValueError('Previous main HTTP build not ready; keep candidate route')
    restore_file(upstream_dir/(platform.site_id+'.upstream'),state['upstream'])
    state['phase']='old_http_ready_route_restored';atomic(path,(json.dumps(state)+'\n').encode())
    return {'checkpoint':str(path),'restored_current':str(old),'restored_units':sorted(state['units']),'old_build_id':state['old_build_id'],'http_verify':verdict}


def wait_for_build(probe,expected,*,timeout=600,interval=3,clock=time.monotonic,sleep=time.sleep):
    deadline=clock()+timeout
    while True:
        verdict=probe()
        if verdict.get('ok') and verdict.get('build_id')==expected:return verdict
        if clock()>=deadline:raise TimeoutError('Previous main has not returned the recorded HTTP build')
        sleep(interval)
