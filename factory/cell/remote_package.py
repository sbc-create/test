"""Integrity of a separately installed, immutable native bridge package."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import stat

VERSION='k2.native-bridge/1'


def identity(files):
    return hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify(root,metadata):
    root=Path(root)
    if metadata.get('schema')!=VERSION or not isinstance(metadata.get('files'),dict):
        raise ValueError('Invalid trusted native package manifest')
    files=metadata['files']
    if not files or len(files)>20000 or identity(files)!=metadata.get('package_sha256'):
        raise ValueError('Trusted package identity differs')
    for name,digest in files.items():
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts:
            raise ValueError('Unsafe package file path')
        path=root/relative
        for parent in [root,*list(path.parents)[:len(relative.parts)-1]]:
            mode=parent.lstat()
            if not stat.S_ISDIR(mode.st_mode) or mode.st_uid!=0 or mode.st_mode & 0o022:
                raise PermissionError('Native package directories must be root-owned and not writable by others')
        mode=path.lstat()
        if not stat.S_ISREG(mode.st_mode) or mode.st_uid!=0 or mode.st_mode & 0o222:
            raise PermissionError('Native package files must be root-owned and read-only')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Installed native package file changed: '+name)
    # An extra importable module must not silently supplement the pinned source.
    for path in (root/'factory').rglob('*.py'):
        if str(path.relative_to(root)) not in files:raise ValueError('Unpinned native package module')
    return metadata['package_sha256']
