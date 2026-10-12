"""seo_operator.tech_run: захват задачи и вердикт по следам — на временном git-репозитории в var/."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from seo_operator import tech_run

ROOT = Path(__file__).resolve().parents[2]

ПРОВЕРКА_ПАДАЮЩАЯ_НА_БАЗЕ = '''import sys
from pathlib import Path
текст = (Path(__file__).resolve().parent.parent / "page.html").read_text()
sys.exit(0 if "<h1>" in текст else 1)
'''


def _git(репо: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(репо), *a], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def среда(monkeypatch):
    корень = ROOT / "var" / "test-seo-tech" / uuid.uuid4().hex[:8]
    репо = корень / "repo"
    (репо / "checks").mkdir(parents=True)
    (репо / "page.html").write_text("<title>t</title>")
    (репо / "checks" / "run.sh").write_text("exit 0\n")
    _git(репо, "init", "-q", "-b", "main")
    _git(репо, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    _git(репо, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "база")
    очередь = корень / "queue.json"
    задача = {"id": "T900", "repo": str(репо.relative_to(ROOT)), "status": "queued",
              "check": "checks/home_h1.py"}
    очередь.write_text(json.dumps({"tasks": [задача, {"id": "B900", "status": "blocked"}]}))
    monkeypatch.setattr(tech_run, "QUEUE", очередь)
    monkeypatch.setattr(tech_run, "load_queue", lambda путь=очередь: json.loads(очередь.read_text())["tasks"])
    state = корень / "state"
    yield {"репо": репо, "state": state, "задача": задача}
    shutil.rmtree(корень, ignore_errors=True)


def _сделать(среда, run_id: str, *, правка: bool = True, проверка: str = ПРОВЕРКА_ПАДАЮЩАЯ_НА_БАЗЕ):
    захват = tech_run.claim(среда["задача"], run_id, state=среда["state"])
    копия = Path(захват["worktree"])
    (копия / "checks" / "home_h1.py").write_text(проверка)
    if правка:
        (копия / "page.html").write_text("<title>t</title><h1>t</h1>")
    _git(копия, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    _git(копия, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "правка")
    return захват


def test_complete_run_is_verified(среда):
    _сделать(среда, "R1")
    итог = tech_run.verify("R1", state=среда["state"])
    assert итог["verdict"] == "VERIFIED", итог
    assert all(итог["steps"].values())


def test_check_that_passes_on_base_is_not_verified(среда):
    _сделать(среда, "R2", проверка="import sys; sys.exit(0)\n")
    итог = tech_run.verify("R2", state=среда["state"])
    assert итог["verdict"] == "INCOMPLETE" and итог["steps"]["check_fails_on_base"] is False


def test_check_failing_on_branch_is_not_verified(среда):
    _сделать(среда, "R3", правка=False)
    итог = tech_run.verify("R3", state=среда["state"])
    assert итог["verdict"] == "INCOMPLETE" and итог["steps"]["check_passes_on_branch"] is False


def test_no_commit_is_not_verified(среда):
    tech_run.claim(среда["задача"], "R4", state=среда["state"])
    итог = tech_run.verify("R4", state=среда["state"])
    assert итог["verdict"] == "INCOMPLETE" and итог["steps"]["has_commit"] is False


def test_pushed_branch_is_not_verified(среда):
    захват = _сделать(среда, "R5")
    _git(среда["репо"], "config", f"branch.{захват['branch']}.remote", "origin")
    итог = tech_run.verify("R5", state=среда["state"])
    assert итог["steps"]["not_pushed"] is False and итог["verdict"] == "INCOMPLETE"


def test_unknown_run_is_no_task(среда):
    assert tech_run.verify("нет-такого", state=среда["state"])["verdict"] == "NO_TASK"


def test_next_task_skips_live_claim_retries_and_done(среда):
    задачи = tech_run.load_queue()
    s = среда["state"]
    assert tech_run.next_task(задачи, state=s)["id"] == "T900"
    tech_run.claim(среда["задача"], "R6", state=s)
    assert tech_run.next_task(задачи, state=s) is None  # живой захват
    позже = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=tech_run.STALE_S + 60)
    assert tech_run.next_task(задачи, state=s, now=позже)["id"] == "T900"  # зависший освобождён
    for i in range(tech_run.MAX_ATTEMPTS):
        tech_run.record({"run_id": f"F{i}", "task_id": "T900", "verdict": "INCOMPLETE"}, {}, state=s)
    assert tech_run.next_task(задачи, state=s, now=позже) is None  # попытки исчерпаны


def test_verified_task_not_taken_again(среда):
    s = среда["state"]
    tech_run.record({"run_id": "V1", "task_id": "T900", "verdict": "VERIFIED"}, {}, state=s)
    assert tech_run.next_task(tech_run.load_queue(), state=s) is None


def test_real_queue_parses_and_has_owner_actions():
    задачи = json.loads((ROOT / "config" / "seo-tech-queue.json").read_text(encoding="utf-8"))["tasks"]
    ид = [з["id"] for з in задачи]
    assert len(ид) == len(set(ид))
    for з in задачи:
        assert з["status"] in {"queued", "session", "blocked", "verified", "released", "live_verified", "done"}
        if з["status"] == "blocked":
            assert з.get("owner_action"), з["id"]
        if з["status"] == "queued":
            assert з.get("check") and з.get("repo"), з["id"]


def test_claim_is_atomic_second_claim_refused(среда):
    s = среда["state"]
    tech_run.claim(среда["задача"], "A1", state=s)
    with pytest.raises(tech_run.ЗанятоДругимПрогоном):
        tech_run.claim(среда["задача"], "A2", state=s)
    # claim_next пропускает занятую задачу, а не берёт её второй раз
    assert tech_run.claim_next(tech_run.load_queue(), "A3", state=s) is None


def test_stale_lock_is_reclaimed_once(среда):
    s = среда["state"]
    tech_run.claim(среда["задача"], "B1", state=s)
    tech_run.prune_worktrees(state=s)  # живой захват не трогается
    assert (s / "wt" / "B1").exists()
    позже = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=tech_run.STALE_S + 60)
    убрано = tech_run.prune_worktrees(state=s, now=позже)
    assert "B1" in убрано and not (s / "wt" / "B1").exists()
    assert not (s / "claims" / "T900.claim").exists()
    assert tech_run.claim(среда["задача"], "B2", state=s)["run_id"] == "B2"


def test_prune_removes_closed_run_copy(среда):
    s = среда["state"]
    tech_run.claim(среда["задача"], "C1", state=s)
    tech_run.record({"run_id": "C1", "task_id": "T900", "verdict": "INCOMPLETE"}, {}, state=s)
    assert "C1" in tech_run.prune_worktrees(state=s)
    assert not (s / "wt" / "C1").exists()


def test_broken_check_is_unusable_not_discriminating(среда):
    _сделать(среда, "D1", проверка="import модуль_которого_нет\n")
    итог = tech_run.verify("D1", state=среда["state"])
    assert итог["steps"]["check_usable"] is False
    assert итог["steps"]["check_fails_on_base"] is False
    assert итог["verdict"] == "INCOMPLETE"


def test_exit_code_2_is_unusable(среда):
    _сделать(среда, "D2", проверка="import sys; sys.exit(2)\n")
    assert tech_run.verify("D2", state=среда["state"])["steps"]["check_usable"] is False
