"""Transaction-owned candidate copy. Never promoted, linked, or copied to live data."""
from __future__ import annotations
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
from factory.cell.rollback_state import atomic

ROOT=Path('/var/cache/site-factory-cell/candidates')
MAX_BYTES=512*1024*1024
MAX_FILES=20000


def location(site_id,nonce,root=ROOT):
    if not re.fullmatch('[a-z][a-z0-9-]{1,62}',site_id) or not re.fullmatch('[0-9a-f]{64}',nonce):
        raise ValueError('Invalid candidate copy identity')
    return Path(root)/site_id/nonce


def trusted_parent(path):
    # Existing private parent permissions are never widened.
    if path.exists() or path.is_symlink():
        mode=path.lstat()
        if not stat.S_ISDIR(mode.st_mode) or mode.st_uid!=0 or mode.st_mode & 0o022:
            raise ValueError('Candidate parent is not root controlled')
        if not mode.st_mode & 0o001:raise ValueError('Candidate parent does not permit account traversal')
        return
    trusted_parent(path.parent);path.mkdir(mode=0o711)


def open_relative(root_fd,parts,flags):
    fd=os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
        return os.open(parts[-1],flags|os.O_NOFOLLOW,dir_fd=fd)
    finally:os.close(fd)


def mount_id(fd):
    for line in Path('/proc/self/fdinfo/'+str(fd)).read_text().splitlines():
        if line.startswith('mnt_id:'):return line.split()[1]
    raise ValueError('Mount identity unavailable; candidate copy fails closed')


def inventory(fd,device,parts=(),entries=None,source_mount=None):
    source_mount=mount_id(fd) if source_mount is None else source_mount
    if mount_id(fd)!=source_mount:raise ValueError("Nested candidate input mount forbidden")
    entries=[] if entries is None else entries
    for name in sorted(os.listdir(fd)):
        st=os.stat(name,dir_fd=fd,follow_symlinks=False);relative=parts+(name,)
        if st.st_dev!=device or not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)):
            raise ValueError('Links, special files and nested mounts are not candidate inputs')
        if stat.S_ISREG(st.st_mode) and st.st_nlink!=1:raise ValueError('Hardlinked candidate input forbidden')
        entries.append((relative,st))
        if len(entries)>MAX_FILES:raise ValueError('Candidate data file count exceeds bound')
        if stat.S_ISDIR(st.st_mode):
            child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            try:inventory(child,device,relative,entries,source_mount)
            finally:os.close(child)
    return entries


def prepare(source,site_id,nonce,account,*,root=ROOT,disk_free=None):
    source=Path(source).absolute()
    if source.resolve()!=source or any(p.is_symlink() for p in [source,*source.parents]):
        raise ValueError('Live source path contains a symlink')
    parent=location(site_id,nonce,root);trusted_parent(parent.parent)
    if parent.exists() or parent.is_symlink():raise ValueError('Candidate copy already exists; reconcile transaction instead of overwrite')
    fd=os.open(source,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        entries=inventory(fd,os.fstat(fd).st_dev)
        total=sum(st.st_size for _,st in entries if stat.S_ISREG(st.st_mode))
        if total>MAX_BYTES:raise ValueError('Candidate data exceeds bounded copy size')
        available=disk_free(parent.parent) if disk_free else shutil.disk_usage(parent.parent).free
        if available<total+256*1024*1024:raise ValueError('Insufficient free space for private candidate copy and reserve')
        parent.mkdir(mode=0o711);data=parent/'data';data.mkdir(mode=0o700)
        owner=pwd.getpwnam(account)
        for parts,before in entries:
            target=data.joinpath(*parts)
            if stat.S_ISDIR(before.st_mode):target.mkdir(mode=0o700)
            else:
                incoming=open_relative(fd,parts,os.O_RDONLY)
                with os.fdopen(incoming,'rb') as stream,target.open('xb') as out:
                    if mount_id(stream.fileno())!=mount_id(fd):raise ValueError('Mounted candidate input file forbidden')
                    actual=os.fstat(stream.fileno())
                    if (actual.st_dev,actual.st_ino,actual.st_size)!=(before.st_dev,before.st_ino,before.st_size):
                        raise ValueError('Live data changed before copy; candidate not started')
                    copied=0
                    while chunk:=stream.read(1048576):
                        copied+=len(chunk)
                        if copied>before.st_size:raise ValueError('Live data grew during copy')
                        out.write(chunk)
                    after=os.fstat(stream.fileno())
                    if copied!=before.st_size or (after.st_size,after.st_mtime_ns)!=(actual.st_size,actual.st_mtime_ns):
                        raise ValueError('Live data changed during copy; candidate not started')
                    out.flush();os.fsync(out.fileno())
                target.chmod(0o600)
        # Root-owned marker lives outside the account-writable copy.
        marker=parent/'copy.json';atomic(marker,(json.dumps({'site_id':site_id,'nonce':nonce,'source':str(source),'bytes':total})+'\n').encode(),0o400)
        # Keep the entire tree inaccessible to the web account until complete.
        for parts,_ in entries:os.chown(data.joinpath(*parts),owner.pw_uid,owner.pw_gid)
        os.chown(data,owner.pw_uid,owner.pw_gid)
        return data
    finally:os.close(fd)


def cleanup(site_id,nonce,*,stopped,root=ROOT):
    parent=location(site_id,nonce,root)
    if not parent.exists():return {'copy_absent':True}
    if not stopped():return {'copy_retained':str(parent),'reason':'candidate termination not proven'}
    trusted_parent(parent)
    marker=parent/'copy.json'
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_uid!=0:
        return {'copy_retained':str(parent),'reason':'incomplete or untrusted copy; manual reconciliation required'}
    record=json.loads(marker.read_text())
    if record['site_id']!=site_id or record['nonce']!=nonce:raise ValueError('Candidate copy marker identity differs')
    if set(p.name for p in parent.iterdir())!={'data','copy.json'}:raise ValueError('Unexpected transaction copy contents')
    if not shutil.rmtree.avoids_symlink_attacks:raise ValueError('Safe descriptor-based cleanup unavailable')
    data=parent/'data'
    if data.is_symlink():raise ValueError('Candidate copy root replaced by symlink')
    shutil.rmtree(data);marker.unlink();parent.rmdir()
    return {'copy_removed_after_candidate_stopped':True}
