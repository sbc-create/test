"""REQ-QUEUE: один job — ровно один раз, даже после restart."""
import json
import time

import pytest

from factory import queue


@pytest.fixture(autouse=True)
def clean_queue():
    yield
    for stage in queue.STAGES:
        for path in queue.stage_dir(stage).glob("qtest-*.json"):
            path.unlink()


def test_enqueue_and_claim_moves_atomically():
    item = queue.enqueue("pilot-local", job_id="qtest-1")
    assert queue.counts()["inbox"] >= 1
    claimed = queue.claim()
    assert claimed.job_id == "qtest-1"
    assert not (queue.stage_dir("inbox") / "qtest-1.json").exists()
    assert (queue.stage_dir("processing") / "qtest-1.json").exists()
    queue.finish(claimed, "done")
    assert (queue.stage_dir("done") / "qtest-1.json").exists()


def test_duplicate_enqueue_is_refused():
    queue.enqueue("pilot-local", job_id="qtest-2")
    with pytest.raises(FileExistsError):
        queue.enqueue("pilot-local", job_id="qtest-2")


def test_claim_returns_each_job_once():
    for n in (3, 4, 5):
        queue.enqueue("pilot-local", job_id=f"qtest-{n}")
    claimed = []
    while True:
        item = queue.claim()
        if not item:
            break
        claimed.append(item.job_id)
        queue.finish(item, "done")
    assert len(claimed) == len(set(claimed)), "ни одно задание не выдаётся дважды"


def test_stale_processing_is_requeued():
    queue.enqueue("pilot-local", job_id="qtest-6")
    item = queue.claim()
    old = time.time() - 7200
    import os
    os.utime(item.path, (old, old))
    moved = queue.requeue_stale(max_age_seconds=3600)
    assert "qtest-6.json" in moved
    assert (queue.stage_dir("inbox") / "qtest-6.json").exists()
    again = queue.claim()
    queue.finish(again, "done")


def test_quarantine_records_reason():
    queue.enqueue("pilot-local", job_id="qtest-7")
    item = queue.claim()
    path = queue.finish(item, "quarantine", detail="BLOCKED_RIGHTS: нет rights manifest")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["result_stage"] == "quarantine"
    assert "BLOCKED_RIGHTS" in payload["detail"]


def test_invalid_finish_stage_rejected():
    queue.enqueue("pilot-local", job_id="qtest-8")
    item = queue.claim()
    with pytest.raises(ValueError):
        queue.finish(item, "somewhere")
    queue.finish(item, "failed")
