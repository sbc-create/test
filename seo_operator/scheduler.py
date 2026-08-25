"""Scheduler and worker for the daily unattended run.

Primary mechanism is a Claude Code Routine (see docs/seo-operator/automation-policy.md).
This module is the fallback that runs the same job on an ordinary server, and it
is also what makes a Routine-triggered run safe to retry: the lock, the queue
and the checkpoints live here, not in the trigger.

Restart safety is the point. A worker killed mid-job must, on restart, neither
lose the job nor run its already-completed steps twice.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from . import quotas


def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class LockBusy(RuntimeError):
    """Another worker holds the lock."""


class FileLock:
    """Exclusive lock with stale detection.

    Uses O_EXCL creation, which is atomic on a local filesystem. A lock whose
    owning process is gone and which is older than ``stale_after`` is reclaimed,
    so a crashed worker does not block the schedule forever.
    """

    def __init__(self, path: Path, stale_after: float = 3600.0) -> None:
        self.path = Path(path)
        self.stale_after = stale_after
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _is_stale(self) -> bool:
        data = self._read()
        if data is None:
            return True
        age = time.time() - data.get("acquired_epoch", 0)
        if age > self.stale_after:
            return True
        pid = data.get("pid")
        return bool(pid and not _pid_alive(pid))

    def acquire(self, owner: str = "worker") -> None:
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            if not self._is_stale():
                holder = self._read() or {}
                raise LockBusy(
                    f"блокировка занята: pid={holder.get('pid')} с {holder.get('acquired_at')}"
                ) from None
            self.path.unlink(missing_ok=True)
            return self.acquire(owner)
        with os.fdopen(fd, "w") as fh:
            json.dump(
                {
                    "pid": os.getpid(),
                    "owner": owner,
                    "acquired_at": _utcnow(),
                    "acquired_epoch": time.time(),
                },
                fh,
            )

    def release(self) -> None:
        self.path.unlink(missing_ok=True)

    @contextmanager
    def held(self, owner: str = "worker"):
        self.acquire(owner)
        try:
            yield self
        finally:
            self.release()


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    kind: str
    payload: dict = field(default_factory=dict)
    state: JobState = JobState.QUEUED
    attempts: int = 0
    max_attempts: int = 3
    last_error: str = ""
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Job:
        data = dict(data)
        data["state"] = JobState(data.get("state", "queued"))
        return cls(**data)


class Queue:
    """Durable queue backed by a single JSON file, rewritten atomically."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[Job]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [Job.from_dict(j) for j in raw]

    def _save(self, jobs: list[Job]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([j.to_dict() for j in jobs], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)  # atomic within a filesystem

    def add(self, job: Job) -> None:
        jobs = self._load()
        if any(j.job_id == job.job_id for j in jobs):
            return  # idempotent: re-queuing the same id is a no-op
        jobs.append(job)
        self._save(jobs)

    def pending(self) -> list[Job]:
        return [j for j in self._load() if j.state in (JobState.QUEUED, JobState.RUNNING)]

    def update(self, job: Job) -> None:
        jobs = self._load()
        for i, existing in enumerate(jobs):
            if existing.job_id == job.job_id:
                jobs[i] = job
                break
        else:
            jobs.append(job)
        self._save(jobs)

    def all(self) -> list[Job]:
        return self._load()


class Checkpoint:
    """Records completed steps so a restart resumes rather than repeats."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def completed(self, job_id: str) -> list[str]:
        return self._load().get(job_id, [])

    def mark(self, job_id: str, step: str) -> None:
        data = self._load()
        steps = data.setdefault(job_id, [])
        if step not in steps:
            steps.append(step)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def clear(self, job_id: str) -> None:
        data = self._load()
        data.pop(job_id, None)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class Worker:
    """Runs queued jobs with retries, checkpoints and a lock."""

    def __init__(self, root: Path, *, backoff_base: float = 0.0) -> None:
        self.root = Path(root)
        self.queue = Queue(self.root / "queue.json")
        self.checkpoint = Checkpoint(self.root / "checkpoints.json")
        self.lock = FileLock(self.root / "worker.lock")
        self.backoff_base = backoff_base
        self.events: list[dict] = []

    def _log(self, **fields) -> None:
        self.events.append({"at": _utcnow(), **fields})

    def run_once(self, handlers: dict) -> list[Job]:
        """Process every pending job. Returns the jobs as they ended up."""
        processed: list[Job] = []
        with self.lock.held("worker"):
            for job in self.queue.pending():
                processed.append(self._run_job(job, handlers))
        return processed

    def _run_job(self, job: Job, handlers: dict) -> Job:
        handler = handlers.get(job.kind)
        if handler is None:
            job.state = JobState.FAILED
            job.last_error = f"нет обработчика для {job.kind!r}"
            self.queue.update(job)
            self._log(job=job.job_id, event="no_handler")
            return job

        while job.attempts < job.max_attempts:
            job.attempts += 1
            job.state = JobState.RUNNING
            self.queue.update(job)
            try:
                handler(job, self.checkpoint)
            except Exception as exc:  # noqa: BLE001 - retry any handler failure
                job.last_error = f"{exc.__class__.__name__}: {exc}"
                self._log(
                    job=job.job_id,
                    event="attempt_failed",
                    attempt=job.attempts,
                    error=job.last_error,
                )
                self.queue.update(job)
                # Классификация отказа — единственная реализация живёт в quotas.py.
                # Повторять имеет смысл не всякий отказ: истёкший токен и
                # отсутствие прав не чинятся ожиданием, сколько ни жди.
                kind = quotas.classify_exception(exc)
                if kind not in quotas.RETRIABLE:
                    job.state = JobState.FAILED
                    job.last_error = f"{kind.value}: {job.last_error}"
                    self.queue.update(job)
                    self._log(job=job.job_id, event="failed_terminal", failure_kind=kind.value)
                    return job
                if job.attempts >= job.max_attempts:
                    job.state = JobState.FAILED
                    self.queue.update(job)
                    self._log(job=job.job_id, event="failed")
                    return job
                if self.backoff_base:
                    delay = quotas.backoff_seconds(
                        job.attempts, kind, job.job_id, base=2.0, cap=900.0)
                    time.sleep(self.backoff_base * (delay or 0.0))
                continue

            job.state = JobState.DONE
            job.last_error = ""
            self.queue.update(job)
            self._log(job=job.job_id, event="done", attempts=job.attempts)
            return job

        return job
