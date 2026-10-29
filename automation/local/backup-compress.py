#!/usr/bin/env python3
"""Losslessly compress old daily publish backups; never expire restore points.

Keep the seven newest run dates and two complete pairs per site uncompressed.
Unknown names, symlinks, incomplete pairs and existing archives are untouched.
Default is a plan; --apply verifies gzip CRC and SHA-256 before unlinking JSON.
"""
import argparse
import datetime as dt
import fcntl
import gzip
import hashlib
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import tempfile

DEFAULT = Path('/srv/site-factory/repo/var/lords/publish-backups')
NAME = re.compile(r'(.+)-(catalog|details)\.json\.before\.daily-(\d{8}T\d{6}Z)(\.gz)?')
CHUNK = 1024 * 1024


def fingerprint(s):
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def digest(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(CHUNK), b''):
        h.update(chunk)
    return h.digest()


def plan(root):
    records, pairs = [], {}
    for p in root.iterdir():
        m = NAME.fullmatch(p.name)
        if not m or not stat.S_ISREG(p.lstat().st_mode):
            continue
        site, kind, run, zipped = m.groups()
        try:
            dt.datetime.strptime(run, '%Y%m%dT%H%M%SZ')
        except ValueError:
            continue
        records.append((p, site, kind, run, zipped))
        pairs.setdefault((site, run), set()).add(kind)
    recent = set(sorted({r[3][:8] for r in records})[-7:])
    full = {k for k, kinds in pairs.items() if kinds == {'catalog', 'details'}}
    protected = set()
    for site in {r[1] for r in records}:
        protected.update(sorted(k for k in full if k[0] == site)[-2:])
    return sorted(p for p, site, kind, run, zipped in records
                  if not zipped and run[:8] not in recent
                  and (site, run) in full and (site, run) not in protected
                  and not os.path.lexists(str(p) + '.gz'))


def compress_one(source):
    dest = Path(str(source) + '.gz')
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    temporary = None
    try:
        with os.fdopen(fd, 'rb') as src:
            before = os.fstat(src.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise RuntimeError('not a regular file')
            if shutil.disk_usage(source.parent).free < before.st_size + 1024 ** 3:
                raise RuntimeError('less than one GiB reserve after temporary archive')
            out_fd, name = tempfile.mkstemp(prefix='.compress-', dir=source.parent)
            temporary = Path(name)
            with os.fdopen(out_fd, 'wb') as raw:
                with gzip.GzipFile(filename=source.name, mode='wb', fileobj=raw,
                                   compresslevel=1, mtime=int(before.st_mtime)) as gz:
                    shutil.copyfileobj(src, gz, CHUNK)
                raw.flush()
                os.fchmod(raw.fileno(), stat.S_IMODE(before.st_mode))
                os.fsync(raw.fileno())
            src.seek(0)
            original = digest(src)
            with gzip.open(temporary, 'rb') as check:
                if digest(check) != original:
                    raise RuntimeError('archive content mismatch')
            if fingerprint(before) != fingerprint(os.fstat(src.fileno())):
                raise RuntimeError('source changed while compressing')
            if fingerprint(before) != fingerprint(source.lstat()):
                raise RuntimeError('source replaced while compressing')
            os.link(temporary, dest, follow_symlinks=False)
            dfd = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dfd)
                # A concurrent publisher must never lose an updated source.
                if fingerprint(before) != fingerprint(source.lstat()):
                    raise RuntimeError('source changed before removal; both copies kept')
                source.unlink()
                os.fsync(dfd)
            finally:
                os.close(dfd)
            print('verified', source.name, before.st_size, dest.stat().st_size, flush=True)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dir', type=Path, default=DEFAULT)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = args.dir.resolve(strict=True)
    lock_fd = os.open(root / '.backup-compress.lock',
                      os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        candidates = plan(root)
        print('apply' if args.apply else 'plan', 'files=', len(candidates),
              'bytes=', sum(p.stat().st_size for p in candidates), flush=True)
        if args.apply:
            for source in candidates:
                compress_one(source)
        else:
            for source in candidates:
                print(source.name)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda signum, frame: exit(143))
    main()
