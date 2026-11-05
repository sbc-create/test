"""Durable native code rollback; user data is never copied or restored."""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import tempfile

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


def capture(platform, unit_dir: Path, upstream_dir: Path, updater, systemctl,
            *, state_root: Path=STATE_ROOT):
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
                       'active':systemctl('is-active','--quiet',name,проверять=False).returncode==0,
                       'enabled':systemctl('is-enabled','--quiet',name,проверять=False).returncode==0}
    state={'schema':'native-rollback/1','site_id':platform.site_id,
           'old_current':str(old),'new_current':str(new),'units':records,
           'upstream':snapshot_file(upstream_dir/(platform.site_id+'.upstream'))}
    path=state_root/(platform.site_id+'.json')
    atomic(path,(json.dumps(state,sort_keys=True)+'\n').encode())
    return {'checkpoint':str(path),'old_current':str(old),'new_current':str(new)}


def restore(platform, unit_dir: Path, upstream_dir: Path, systemctl,
            *, state_root: Path=STATE_ROOT):
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
    link=platform.root/'.current.restore';link.unlink(missing_ok=True)
    link.symlink_to(old);os.replace(link,platform.current)
    for name,record in state['units'].items():
        if Path(name).name!=name:raise ValueError('Unsafe rollback unit')
        restore_file(unit_dir/name,record['file'])
        restore_dropins(unit_dir/(name+'.d'),record['dropins'])
    systemctl('daemon-reload')
    for name,record in state['units'].items():
        systemctl('enable' if record['enabled'] else 'disable',name,проверять=False)
        systemctl('restart' if record['active'] else 'stop',name)
    restore_file(upstream_dir/(platform.site_id+'.upstream'),state['upstream'])
    return {'checkpoint':str(path),'restored_current':str(old),'restored_units':sorted(state['units'])}
