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


@pytest.fixture
def tmp_path():
    """Временный каталог внутри var/ (правило тестов: не писать за пределы var/ и artifacts/)."""
    путь = ROOT / "var" / "test-seo-tech" / ("tmp-" + uuid.uuid4().hex[:8])
    путь.mkdir(parents=True)
    yield путь
    shutil.rmtree(путь, ignore_errors=True)

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
    # Адрес копии спрашивается у кода, а не повторяется строкой: каталог
    # переехал 15.10 из `state/wt` в `каталог_копий(state)`, чтобы глубина
    # пути совпадала с `var/site-repos/<репо>`. Повторённая строка пережила
    # переезд и проверяла пустоту вместо копии.
    копия = tech_run.каталог_копий(s) / "B1"
    assert копия.exists()
    позже = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=tech_run.STALE_S + 60)
    убрано = tech_run.prune_worktrees(state=s, now=позже)
    assert "B1" in убрано and not копия.exists()
    assert not (s / "claims" / "T900.claim").exists()
    assert tech_run.claim(среда["задача"], "B2", state=s)["run_id"] == "B2"


def test_prune_removes_closed_run_copy(среда):
    s = среда["state"]
    tech_run.claim(среда["задача"], "C1", state=s)
    tech_run.record({"run_id": "C1", "task_id": "T900", "verdict": "INCOMPLETE"}, {}, state=s)
    assert "C1" in tech_run.prune_worktrees(state=s)
    # Тот же адрес, что у claim: по прежнему `state/wt` копии не бывает вовсе,
    # и утверждение выполнялось ВСЕГДА — проверка, которая не может
    # провалиться, ничего не стоит (решение D205).
    assert not (tech_run.каталог_копий(s) / "C1").exists()


def test_broken_check_is_unusable_not_discriminating(среда):
    _сделать(среда, "D1", проверка="import модуль_которого_нет\n")
    итог = tech_run.verify("D1", state=среда["state"])
    assert итог["steps"]["check_usable"] is False
    assert итог["steps"]["check_fails_on_base"] is False
    assert итог["verdict"] == "INCOMPLETE"


def test_exit_code_2_is_unusable(среда):
    _сделать(среда, "D2", проверка="import sys; sys.exit(2)\n")
    assert tech_run.verify("D2", state=среда["state"])["steps"]["check_usable"] is False


def test_cyrillic_check_path_found_in_branch(среда):
    среда["задача"]["check"] = "checks/проверка_h1.py"
    захват = tech_run.claim(среда["задача"], "E1", state=среда["state"])
    копия = Path(захват["worktree"])
    (копия / "checks" / "проверка_h1.py").write_text(ПРОВЕРКА_ПАДАЮЩАЯ_НА_БАЗЕ)
    (копия / "page.html").write_text("<h1>t</h1>")
    _git(копия, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    _git(копия, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "правка")
    import json as _j
    очередь = tech_run.QUEUE
    д = _j.loads(очередь.read_text()); д["tasks"][0]["check"] = "checks/проверка_h1.py"; очередь.write_text(_j.dumps(д))
    итог = tech_run.verify("E1", state=среда["state"])
    assert итог["steps"]["check_in_branch"] is True and итог["verdict"] == "VERIFIED", итог


def test_run_id_cannot_claim_twice(среда):
    s = среда["state"]
    tech_run.claim(среда["задача"], "F1", state=s)
    tech_run.release_worktree("F1", state=s)
    with pytest.raises(ValueError):
        tech_run.claim(среда["задача"], "F1", state=s)


def test_wrapper_refuses_before_claim_without_prompt():
    текст = (ROOT / "automation" / "host" / "editor" / "seo-tech-run.sh").read_text(encoding="utf-8")
    assert текст.index("test -s docs/seo-tech/SEO_TECH_RUN_PROMPT.md") < текст.index("seo-tech-next")
    assert 'RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"' in текст


def test_order_follows_allocation_lagging_direction_first(tmp_path):
    """Доли 50/50 (владелец 13.10): первыми — задачи отставшего направления,
    при равенстве — Lords; Zona и сеть — после; внутри группы порядок очереди."""
    задачи = [{"id": "T901", "status": "queued", "direction": "anime"},
              {"id": "T902", "status": "queued", "direction": "zona"},
              {"id": "T903", "status": "queued", "direction": "lords"},
              {"id": "T904", "status": "queued", "direction": "anime"}]
    s = tmp_path / "state"
    s.mkdir()
    сейчас = dt.datetime(2026, 10, 13, 12, 0, tzinfo=dt.timezone.utc)
    порядок = [з["id"] for з in tech_run.candidates(задачи, state=s, now=сейчас,
                                                    доли={"anime": 0.5, "lords": 0.5})]
    assert порядок == ["T903", "T901", "T904", "T902"]
    (s / "claims.jsonl").write_text("".join(
        json.dumps({"run_id": f"R{i}", "task_id": "T903", "at": "2026-10-13T1{}:00:00Z".format(i)}) + "\n"
        for i in range(2)), encoding="utf-8")
    порядок = [з["id"] for з in tech_run.candidates(задачи, state=s, now=сейчас,
                                                    доли={"anime": 0.5, "lords": 0.5})]
    assert порядок == ["T901", "T904", "T903", "T902"]


def test_real_queue_has_allocation_and_directions():
    очередь = json.loads((ROOT / "config" / "seo-tech-queue.json").read_text(encoding="utf-8"))
    assert очередь["allocation"]["anime"] == 0.5 and очередь["allocation"]["lords"] == 0.5
    for з in очередь["tasks"]:
        assert з.get("direction") in {"anime", "lords", "zona", "network"}, з["id"]
    вне = ("lordfilm.group", "lordfilm.spb.ru", "lordfilm.msk.ru", "lordserial.su",
           "lordserial.group", "lordserial.spb.ru", "lordserial.msk.ru", "lordserial.net.ru")
    for з in очередь["tasks"]:
        if з["direction"] == "lords":
            assert not any(д in з.get("site", "") for д in вне), з["id"]


def test_excluded_new_lords_domains_never_taken(среда):
    """Восемь новых доменов Lords — вне продвижения: ни выбор, ни захват их не берут."""
    s = среда["state"]
    по_сайту = {**среда["задача"], "id": "T901", "site": "lordfilm.group"}
    по_репо = {**среда["задача"], "id": "T902", "repo": "var/site-repos/lordserial-net-ru"}
    соседний = {**среда["задача"], "id": "T903", "site": "lordfilm47.space"}
    assert tech_run.вне_продвижения(по_сайту) == "lordfilm.group"
    assert tech_run.вне_продвижения(по_репо) == "lordserial.net.ru"
    assert tech_run.вне_продвижения(соседний) is None
    assert tech_run.вне_продвижения({"site": "lordserial.su, lordfilm47.space"}) == "lordserial.su"
    ид = [з["id"] for з in tech_run.candidates([по_сайту, по_репо, соседний], state=s)]
    assert ид == ["T903"]
    with pytest.raises(tech_run.ВнеПродвижения):
        tech_run.claim(по_сайту, "X1", state=s)
    assert not (s / "claims.jsonl").exists()


def test_real_queue_has_no_task_on_excluded_domains():
    задачи = json.loads((ROOT / "config" / "seo-tech-queue.json").read_text(encoding="utf-8"))["tasks"]
    assert [з["id"] for з in задачи if tech_run.вне_продвижения(з)] == []


def test_excluded_list_matches_editor_and_needs_no_package():
    """Один перечень на оба прогона; модуль грузится и без пакета seo_operator."""
    import importlib.util
    import sys as _sys
    from seo_operator import editor_run
    assert tech_run.ВНЕ_ПРОДВИЖЕНИЯ == editor_run.ВНЕ_ПРОДВИЖЕНИЯ
    код = ("import importlib.util,sys\n"
           f"sp=importlib.util.spec_from_file_location('m', {str(ROOT / 'seo_operator' / 'tech_run.py')!r})\n"
           "m=importlib.util.module_from_spec(sp); sp.loader.exec_module(m)\n"
           "print(m.вне_продвижения({'site': 'lordfilm.group'}))")
    r = subprocess.run([_sys.executable, "-I", "-c", код], cwd="/", capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "lordfilm.group", r.stderr[-300:]


def test_queue_schema_accepts_dependencies_and_rejects_empty():
    import jsonschema
    схема = json.loads((ROOT / "schemas" / "seo-tech-queue.schema.json").read_text(encoding="utf-8"))
    задача = {"id": "T999", "site": "an1mego.site", "problem": "p", "status": "session", "direction": "anime"}
    очередь = json.loads((ROOT / "config" / "seo-tech-queue.json").read_text(encoding="utf-8"))
    def с(доп):
        return {**очередь, "tasks": [{**задача, **доп}]}
    jsonschema.validate(с({"dependencies": "нет"}), схема)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(с({"dependencies": ""}), схема)


МИНИ_СТЕНД = """import json
from pathlib import Path
def урезать(откуда, куда, шаг=20):
    к = json.loads(next(Path(откуда).glob("*-catalog.json")).read_text())
    к["items"] = к["items"][::шаг]
    (Path(куда) / "x-catalog.json").write_text(json.dumps(к))
"""
ПРОВЕРКА_СО_СТЕНДОМ = """import json, os, sys
from pathlib import Path
д = os.environ.get("SITE_DATA_DIR")
if not д:
    print("НЕ ИЗМЕРЕНО"); sys.exit(2)
assert len(json.loads((Path(д) / "x-catalog.json").read_text())["items"]) == 2
текст = (Path(__file__).resolve().parent.parent / "page.html").read_text()
sys.exit(0 if "<h1>" in текст else 1)
"""


def test_lords_like_repo_gets_trimmed_snapshot_on_claim_and_verify(среда, monkeypatch, tmp_path):
    """Витрина с checks/mini_stand.py: захват готовит урезанный снимок, вердикт прогоняет проверки на нём."""
    репо = среда["репо"]
    (репо / "checks" / "mini_stand.py").write_text(МИНИ_СТЕНД)
    _git(репо, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    _git(репо, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "стенд")
    данные = tmp_path / "srv" / репо.name / "data"
    данные.mkdir(parents=True)
    (данные / "x-catalog.json").write_text(json.dumps({"items": list(range(40))}))
    monkeypatch.setattr(tech_run, "КОРНИ_ДАННЫХ", (tmp_path / "srv",))
    захват = _сделать(среда, "M1", проверка=ПРОВЕРКА_СО_СТЕНДОМ)
    assert Path(захват["stand_data"]).is_dir()
    итог = tech_run.verify("M1", state=среда["state"])
    assert итог["verdict"] == "VERIFIED", итог
    assert not (среда["state"] / "mini" / "M1").exists()  # снимок убран после вердикта


def test_snapshot_failure_does_not_break_claim(среда, monkeypatch, tmp_path):
    репо = среда["репо"]
    (репо / "checks" / "mini_stand.py").write_text("def урезать(*a, **k):\n    raise MemoryError\n")
    данные = tmp_path / "srv" / репо.name / "data"
    данные.mkdir(parents=True)
    (данные / "x-catalog.json").write_text("{}")
    monkeypatch.setattr(tech_run, "КОРНИ_ДАННЫХ", (tmp_path / "srv",))
    assert tech_run.снимок_стенда(репо, tmp_path / "mini") == {}
    assert not (tmp_path / "mini").exists()


def test_untracked_launch_file_linked_not_copied(tmp_path):
    """config/player.json — ссылкой в рабочую копию; нечитаемый не связывается (T083, 14.10)."""
    import os
    репо, копия = tmp_path / "repo", tmp_path / "wt"
    (репо / "config").mkdir(parents=True)
    копия.mkdir()
    (репо / "config" / "player.json").write_text("{}", encoding="utf-8")
    assert tech_run.связать_неотслеживаемые(репо, копия) == ["config/player.json"]
    цель = копия / "config" / "player.json"
    assert цель.is_symlink() and цель.resolve() == (репо / "config" / "player.json").resolve()
    # Повтор ничего не меняет; уже существующий файл копии не трогается.
    assert tech_run.связать_неотслеживаемые(репо, копия) == []
    # Нечитаемый источник не связывается: «нет файла» обходит stand_root, PermissionError — нет.
    другая = tmp_path / "wt2"
    другая.mkdir()
    os.chmod(репо / "config" / "player.json", 0)
    try:
        if not os.access(репо / "config" / "player.json", os.R_OK):
            assert tech_run.связать_неотслеживаемые(репо, другая) == []
            assert not (другая / "config" / "player.json").exists()
    finally:
        os.chmod(репо / "config" / "player.json", 0o644)
    # Источника нет — нечего связывать.
    assert tech_run.связать_неотслеживаемые(tmp_path / "нет", tmp_path / "wt3") == []
