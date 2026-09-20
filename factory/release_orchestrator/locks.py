"""Global release batch lock — concurrency=1 across releases."""

from __future__ import annotations

import errno
import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from factory.paths import PATHS


class ReleaseLockBusy(RuntimeError):
    def __init__(self, holder: dict):
        super().__init__(f"another release batch holds the global lock: {holder}")
        self.holder = holder


def global_lock_path() -> Path:
    PATHS.locks.mkdir(parents=True, exist_ok=True)
    return PATHS.locks / "release-orchestrator.global.lock"


@contextmanager
def global_release_lock(release_id: str, *, timeout: float = 0.0) -> Iterator[Path]:
    path = global_lock_path()
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
                        holder = json.loads(Path(path).read_text(encoding="utf-8") or "{}")
                    except (OSError, json.JSONDecodeError):
                        holder = {}
                    raise ReleaseLockBusy(holder) from None
                time.sleep(0.05)
        payload = json.dumps(
            {"release_id": release_id, "pid": os.getpid(), "acquired_at": time.time()},
            sort_keys=True,
        )
        os.ftruncate(fd, 0)
        os.write(fd, payload.encode("utf-8"))
        os.fsync(fd)
        yield path
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
