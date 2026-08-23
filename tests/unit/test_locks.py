"""REQ-LOCK: параллельное изменение одного сайта исключено."""
import multiprocessing as mp
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from factory.locks import LockBusy, is_locked, site_lock  # noqa: E402


def test_lock_is_exclusive_in_process():
    with site_lock("lock-demo", "staging"):
        assert is_locked("lock-demo", "staging")
        with pytest.raises(LockBusy), site_lock("lock-demo", "staging"):
            pass
    assert not is_locked("lock-demo", "staging")


def test_different_environments_do_not_block_each_other():
    with site_lock("lock-demo", "staging"), site_lock("lock-demo", "production"):
        assert True


def _hold(ready, release):
    from factory.locks import site_lock as lock
    with lock("lock-proc", "staging"):
        ready.set()
        release.wait(10)


def test_lock_is_exclusive_across_processes():
    ctx = mp.get_context("fork")
    ready, release = ctx.Event(), ctx.Event()
    worker = ctx.Process(target=_hold, args=(ready, release))
    worker.start()
    try:
        assert ready.wait(10)
        with pytest.raises(LockBusy), site_lock("lock-proc", "staging"):
            pass
    finally:
        release.set()
        worker.join(10)
    assert not is_locked("lock-proc", "staging")


def test_lock_released_when_process_dies():
    ctx = mp.get_context("fork")
    ready, release = ctx.Event(), ctx.Event()
    worker = ctx.Process(target=_hold, args=(ready, release))
    worker.start()
    assert ready.wait(10)
    worker.terminate()
    worker.join(10)
    assert not is_locked("lock-proc", "staging"), "flock снимается ядром при падении процесса"
