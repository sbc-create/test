"""Scheduler tests: locking, retries, checkpoints and restart recovery."""

from __future__ import annotations

import json
import os

import pytest

from seo_operator.scheduler import (
    Checkpoint,
    FileLock,
    Job,
    JobState,
    LockBusy,
    Queue,
    Worker,
)


class TestLock:
    def test_exclusive(self, tmp_path):
        lock = FileLock(tmp_path / "l.lock")
        lock.acquire()
        with pytest.raises(LockBusy):
            FileLock(tmp_path / "l.lock").acquire()
        lock.release()

    def test_released_lock_is_reusable(self, tmp_path):
        lock = FileLock(tmp_path / "l.lock")
        with lock.held():
            pass
        FileLock(tmp_path / "l.lock").acquire()  # must not raise

    def test_stale_lock_from_dead_process_is_reclaimed(self, tmp_path):
        """A crashed worker must not block the schedule forever."""
        path = tmp_path / "l.lock"
        path.write_text(
            json.dumps(
                {
                    "pid": 999999,
                    "owner": "dead",
                    "acquired_at": "2026-01-01T00:00:00Z",
                    "acquired_epoch": 9e9,
                }
            )
        )  # future epoch so age is not what frees it
        FileLock(path).acquire()  # reclaimed because the pid is gone

    def test_old_lock_is_reclaimed_by_age(self, tmp_path):
        path = tmp_path / "l.lock"
        path.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "owner": "old",
                    "acquired_at": "2020-01-01T00:00:00Z",
                    "acquired_epoch": 0,
                }
            )
        )
        FileLock(path, stale_after=1.0).acquire()

    def test_corrupt_lock_file_is_reclaimed(self, tmp_path):
        path = tmp_path / "l.lock"
        path.write_text("не json")
        FileLock(path).acquire()

    def test_lock_released_even_when_body_raises(self, tmp_path):
        lock = FileLock(tmp_path / "l.lock")
        with pytest.raises(ValueError), lock.held():
            raise ValueError("boom")
        assert not (tmp_path / "l.lock").exists()


class TestQueue:
    def test_add_and_pending(self, tmp_path):
        q = Queue(tmp_path / "q.json")
        q.add(Job("j1", "daily_run"))
        assert [j.job_id for j in q.pending()] == ["j1"]

    def test_add_is_idempotent(self, tmp_path):
        q = Queue(tmp_path / "q.json")
        q.add(Job("j1", "daily_run"))
        q.add(Job("j1", "daily_run"))
        assert len(q.all()) == 1

    def test_queue_survives_restart(self, tmp_path):
        Queue(tmp_path / "q.json").add(Job("j1", "daily_run"))
        assert [j.job_id for j in Queue(tmp_path / "q.json").pending()] == ["j1"]

    def test_done_job_is_not_pending(self, tmp_path):
        q = Queue(tmp_path / "q.json")
        job = Job("j1", "daily_run")
        q.add(job)
        job.state = JobState.DONE
        q.update(job)
        assert q.pending() == []


class TestCheckpoint:
    def test_marks_and_reads(self, tmp_path):
        cp = Checkpoint(tmp_path / "cp.json")
        cp.mark("j1", "collect")
        cp.mark("j1", "analyse")
        assert cp.completed("j1") == ["collect", "analyse"]

    def test_mark_is_idempotent(self, tmp_path):
        cp = Checkpoint(tmp_path / "cp.json")
        cp.mark("j1", "collect")
        cp.mark("j1", "collect")
        assert cp.completed("j1") == ["collect"]

    def test_survives_restart(self, tmp_path):
        Checkpoint(tmp_path / "cp.json").mark("j1", "collect")
        assert Checkpoint(tmp_path / "cp.json").completed("j1") == ["collect"]

    def test_corrupt_file_reads_as_empty(self, tmp_path):
        (tmp_path / "cp.json").write_text("не json")
        assert Checkpoint(tmp_path / "cp.json").completed("j1") == []


class TestWorker:
    def test_successful_job_marked_done(self, tmp_path):
        w = Worker(tmp_path)
        w.queue.add(Job("j1", "daily_run"))
        done = w.run_once({"daily_run": lambda job, cp: cp.mark(job.job_id, "ran")})
        assert done[0].state is JobState.DONE
        assert done[0].attempts == 1

    def test_retries_then_succeeds(self, tmp_path):
        w = Worker(tmp_path)
        w.queue.add(Job("j1", "flaky"))
        calls = {"n": 0}

        def handler(job, cp):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("временный сбой")

        result = w.run_once({"flaky": handler})[0]
        assert result.state is JobState.DONE
        assert result.attempts == 3

    def test_gives_up_after_max_attempts(self, tmp_path):
        w = Worker(tmp_path)
        w.queue.add(Job("j1", "broken", max_attempts=2))

        def handler(job, cp):
            raise RuntimeError("постоянный сбой")

        result = w.run_once({"broken": handler})[0]
        assert result.state is JobState.FAILED
        assert result.attempts == 2
        assert "постоянный сбой" in result.last_error

    def test_missing_handler_fails_cleanly(self, tmp_path):
        w = Worker(tmp_path)
        w.queue.add(Job("j1", "unknown_kind"))
        result = w.run_once({})[0]
        assert result.state is JobState.FAILED
        assert "нет обработчика" in result.last_error

    def test_restart_resumes_from_checkpoint(self, tmp_path):
        """The core restart-safety property: completed steps do not re-run."""
        w = Worker(tmp_path)
        w.queue.add(Job("j1", "multi"))
        executed = []

        def handler(job, cp):
            for step in ("collect", "analyse", "report"):
                if step in cp.completed(job.job_id):
                    continue
                executed.append(step)
                if step == "report" and len(executed) < 4:
                    cp.mark(job.job_id, "collect")
                    cp.mark(job.job_id, "analyse")
                    raise RuntimeError("процесс убит перед отчётом")
                cp.mark(job.job_id, step)

        result = w.run_once({"multi": handler})[0]
        assert result.state is JobState.DONE
        # collect and analyse ran once each; only 'report' was retried.
        assert executed.count("collect") == 1
        assert executed.count("analyse") == 1

    def test_second_worker_blocked_while_first_holds_lock(self, tmp_path):
        w1 = Worker(tmp_path)
        w1.lock.acquire("first")
        w2 = Worker(tmp_path)
        with pytest.raises(LockBusy):
            w2.run_once({})
        w1.lock.release()

    def test_lock_free_after_run(self, tmp_path):
        w = Worker(tmp_path)
        w.queue.add(Job("j1", "daily_run"))
        w.run_once({"daily_run": lambda job, cp: None})
        assert not w.lock.path.exists()
