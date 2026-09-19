"""Singleton flock для ratings ingestion."""

from __future__ import annotations

import errno
import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

from factory.paths import PATHS


class RatingsLockBusy(RuntimeError):
    def __init__(self, holder: dict) -> None:
        super().__init__(f"ratings ingestion already locked: {holder}")
        self.holder = holder


@contextmanager
def ratings_lock(name: str = "ratings-ingestion", *, timeout: float = 0.0):
    PATHS.locks.mkdir(parents=True, exist_ok=True)
    path = PATHS.locks / f"{name}.lock"
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EACCES):
                    raise
                if time.monotonic() >= deadline:
                    try:
                        holder = json.loads(Path(path).read_text() or "{}")
                    except (OSError, json.JSONDecodeError):
                        holder = {}
                    raise RatingsLockBusy(holder) from None
                time.sleep(0.05)
        os.ftruncate(fd, 0)
        os.write(
            fd,
            json.dumps({"pid": os.getpid(), "name": name, "acquired_at": time.time()}).encode(),
        )
        os.fsync(fd)
        yield path
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
