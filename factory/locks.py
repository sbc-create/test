"""Блокировки site+environment.

Один сайт в одном окружении изменяется ровно одним процессом. Lock переживает
падение процесса (flock снимается ядром) и содержит диагностическую информацию.
"""
from __future__ import annotations

import errno
import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

from factory.paths import PATHS


class LockBusy(RuntimeError):
    def __init__(self, key: str, holder: dict) -> None:
        super().__init__(f"Ресурс {key} уже заблокирован: {holder}")
        self.key = key
        self.holder = holder


def lock_path(site_id: str, environment: str) -> Path:
    PATHS.locks.mkdir(parents=True, exist_ok=True)
    return PATHS.locks / f"{site_id}.{environment}.lock"


@contextmanager
def site_lock(site_id: str, environment: str, *, timeout: float = 0.0, poll: float = 0.25):
    """Эксклюзивная блокировка. timeout=0 → немедленный отказ, если занято."""
    path = lock_path(site_id, environment)
    key = f"{site_id}/{environment}"
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
                    holder = _read_holder(path)
                    raise LockBusy(key, holder) from None
                time.sleep(poll)
        os.ftruncate(fd, 0)
        os.write(fd, json.dumps({"pid": os.getpid(), "site_id": site_id, "environment": environment, "acquired_at": time.time()}).encode())
        os.fsync(fd)
        yield path
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _read_holder(path: Path) -> dict:
    try:
        return json.loads(path.read_text() or "{}")
    except (OSError, json.JSONDecodeError):
        return {}


def is_locked(site_id: str, environment: str) -> bool:
    path = lock_path(site_id, environment)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        os.close(fd)
