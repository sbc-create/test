"""Фоновое техническое SEO: выбор задачи и проверка ПО СЛЕДАМ, а не по самоотчёту.

Образец — фоновый редактор (seo_operator.editor_run), перенесённый на технику
(разбор Архитектора, docs/verification/autocontinue-technical-seo-20261012.md):

* очередь — `config/seo-tech-queue.json` (определения задач, только чтение);
  состояние — `var/seo-tech/` (единственное, что прогон пишет вне рабочих копий);
* прогон ГОТОВИТ ветку в отдельной git-рабочей копии (`git worktree`) репозитория
  витрины и НЕ делает push и выпуск: это свойство юнита (InaccessiblePaths на
  учётные данные git), а здесь — ещё и проверяемый след;
* вердикт `verify()`: ветка есть, в ней есть коммит поверх базы, регрессионная
  проверка задачи ПАДАЕТ на базе и ПРОХОДИТ на ветке (D203), полный
  `checks/run.sh` ветки проходит, у ветки нет удалённого двойника;
* повторы ограничены (`MAX_ATTEMPTS`), зависший захват (старше `STALE_S` без
  итога) освобождается, а не держит задачу вечно.

Статусы задачи различаются строго: queued → prepared (ветка есть) → verified
(вердикт по следам) → released / live_verified (только сессией или человеком,
после просмотра: выпуск фоновому прогону не принадлежит).
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
QUEUE = REPO / "config" / "seo-tech-queue.json"
STATE = REPO / "var" / "seo-tech"
MAX_ATTEMPTS = 3
STALE_S = 2 * 3600
ГОТОВО = {"verified", "released", "live_verified", "done"}


def _сейчас() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _git(репо: Path, *арг: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(репо), *арг], capture_output=True, text=True, timeout=300)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(арг)}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def load_queue(путь: Path = QUEUE) -> list[dict[str, Any]]:
    данные = json.loads(путь.read_text(encoding="utf-8"))
    задачи = данные["tasks"]
    ид = [з["id"] for з in задачи]
    if len(ид) != len(set(ид)):
        raise ValueError("в очереди повторяются id задач")
    return задачи


def _runs(state: Path) -> list[dict[str, Any]]:
    f = state / "runs.jsonl"
    if not f.exists():
        return []
    return [json.loads(с) for с in f.read_text(encoding="utf-8").splitlines() if с.strip()]


def _claims(state: Path) -> list[dict[str, Any]]:
    f = state / "claims.jsonl"
    if not f.exists():
        return []
    return [json.loads(с) for с in f.read_text(encoding="utf-8").splitlines() if с.strip()]


def task_state(state: Path = STATE) -> dict[str, dict[str, Any]]:
    """Сводка по задачам из следов: последний вердикт, число неудач, открытый захват."""
    итог: dict[str, dict[str, Any]] = {}
    for р in _runs(state):
        з = итог.setdefault(р["task_id"], {"failures": 0})
        з["last"] = р
        if р.get("verdict") == "VERIFIED":
            з["status"] = "verified"
        elif р.get("verdict") != "NO_TASK":
            з["failures"] += 1
    закрытые = {р["run_id"] for р in _runs(state)}
    for к in _claims(state):
        if к["run_id"] not in закрытые:
            итог.setdefault(к["task_id"], {"failures": 0})["open_claim"] = к
    return итог


def next_task(задачи: list[dict], state: Path = STATE, now: dt.datetime | None = None) -> dict | None:
    """Первая задача queued без вердикта, без живого захвата и с запасом попыток."""
    now = now or _сейчас()
    сводка = task_state(state)
    for з in задачи:
        if з.get("status") != "queued":
            continue
        с = сводка.get(з["id"], {})
        if с.get("status") in ГОТОВО or с.get("failures", 0) >= MAX_ATTEMPTS:
            continue
        захват = с.get("open_claim")
        if захват:
            возраст = (now - dt.datetime.fromisoformat(захват["at"].replace("Z", "+00:00"))).total_seconds()
            if возраст < STALE_S:
                continue  # чужой живой захват
        return з
    return None


def claim(задача: dict, run_id: str, state: Path = STATE) -> dict[str, Any]:
    """Захват + отдельная рабочая копия на новой ветке от текущей ветки репозитория."""
    репо = REPO / задача["repo"]
    база = _git(репо, "rev-parse", "HEAD")
    ветка = f"claude/seo-tech-{задача['id'].lower()}-{run_id.lower()}"
    копия = state / "wt" / run_id
    копия.parent.mkdir(parents=True, exist_ok=True)
    _git(репо, "worktree", "add", "-q", "-b", ветка, str(копия), база)
    запись = {"run_id": run_id, "task_id": задача["id"], "at": _сейчас().strftime("%Y-%m-%dT%H:%M:%SZ"),
              "repo": задача["repo"], "base_sha": база, "branch": ветка, "worktree": str(копия)}
    state.mkdir(parents=True, exist_ok=True)
    with open(state / "claims.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(запись, ensure_ascii=False) + "\n")
    (state / "next.json").write_text(json.dumps({**запись, "task": задача}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    return запись


def _прогнать(каталог: Path, команда: list[str], предел: int) -> tuple[int, str]:
    try:
        r = subprocess.run(команда, cwd=каталог, capture_output=True, text=True, timeout=предел)
        return r.returncode, (r.stdout + r.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        return 124, f"предел {предел} с исчерпан"


def verify(run_id: str, state: Path = STATE, run_all: bool = True) -> dict[str, Any]:
    """Вердикт по следам. Каждый шаг — отдельный признак; VERIFIED только при всех."""
    захват = next((к for к in _claims(state) if к["run_id"] == run_id), None)
    if захват is None:
        return {"run_id": run_id, "verdict": "NO_TASK", "steps": {}, "notes": ["захвата с таким run_id нет"]}
    задачи = {з["id"]: з for з in load_queue()}
    задача = задачи.get(захват["task_id"], {})
    репо = REPO / захват["repo"]
    шаги: dict[str, bool] = {}
    заметки: list[str] = []

    голова = _git(репо, "rev-parse", "--verify", "-q", захват["branch"], check=False)
    шаги["branch_exists"] = bool(голова)
    # Коммит поверх базы: голова не равна базе, и база — её предок.
    шаги["has_commit"] = bool(голова) and голова != захват["base_sha"] and subprocess.run(
        ["git", "-C", str(репо), "merge-base", "--is-ancestor", захват["base_sha"], голова],
        capture_output=True).returncode == 0
    удалённые = _git(репо, "for-each-ref", "--format=%(refname)", f"refs/remotes/*/{захват['branch']}",
                     check=False)
    вверх = _git(репо, "config", "--get", f"branch.{захват['branch']}.remote", check=False)
    шаги["not_pushed"] = not удалённые and not вверх
    проверка = задача.get("check")
    шаги["check_declared"] = bool(проверка)

    if шаги["has_commit"] and проверка:
        файлы = _git(репо, "ls-tree", "-r", "--name-only", голова)
        шаги["check_in_branch"] = проверка in файлы.splitlines()
        if шаги["check_in_branch"]:
            база_wt = state / "wt" / f"{run_id}-verify-base"
            голова_wt = state / "wt" / f"{run_id}-verify-head"
            for wt, sha in ((база_wt, захват["base_sha"]), (голова_wt, голова)):
                if wt.exists():
                    _git(репо, "worktree", "remove", "--force", str(wt), check=False)
                _git(репо, "worktree", "add", "-q", "--detach", str(wt), sha)
            try:
                # Проверка ветки — на коде базы: обязана упасть (D203).
                (база_wt / проверка).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(голова_wt / проверка, база_wt / проверка)
                rc_база, вывод_база = _прогнать(база_wt, ["python3", проверка], 600)
                rc_голова, вывод_голова = _прогнать(голова_wt, ["python3", проверка], 600)
                шаги["check_fails_on_base"] = rc_база != 0
                шаги["check_passes_on_branch"] = rc_голова == 0
                if not шаги["check_fails_on_base"]:
                    заметки.append("проверка проходит и на базе — она не различает (D203)")
                if not шаги["check_passes_on_branch"]:
                    заметки.append(f"проверка на ветке: {вывод_голова[-300:]}")
                if run_all:
                    rc_все, вывод_все = _прогнать(голова_wt, ["bash", "checks/run.sh"], 1800)
                    шаги["run_all_passes"] = rc_все == 0
                    if rc_все:
                        заметки.append(f"checks/run.sh: {вывод_все[-400:]}")
            finally:
                for wt in (база_wt, голова_wt):
                    _git(репо, "worktree", "remove", "--force", str(wt), check=False)

    нужно = ["branch_exists", "has_commit", "not_pushed", "check_declared", "check_in_branch",
             "check_fails_on_base", "check_passes_on_branch"] + (["run_all_passes"] if run_all else [])
    полный = all(шаги.get(к) for к in нужно)
    return {"run_id": run_id, "task_id": захват["task_id"], "branch": захват["branch"],
            "head": голова or None, "base_sha": захват["base_sha"],
            "verdict": "VERIFIED" if полный else "INCOMPLETE", "steps": шаги, "notes": заметки}


def record(результат: dict[str, Any], extra: dict[str, Any], state: Path = STATE) -> dict[str, Any]:
    запись = {**результат, **extra}
    state.mkdir(parents=True, exist_ok=True)
    with open(state / "runs.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(запись, ensure_ascii=False) + "\n")
    return запись


def release_worktree(run_id: str, state: Path = STATE) -> None:
    """Рабочая копия прогона убирается; ВЕТКА остаётся для просмотра человеком."""
    захват = next((к for к in _claims(state) if к["run_id"] == run_id), None)
    if захват:
        _git(REPO / захват["repo"], "worktree", "remove", "--force", захват["worktree"], check=False)
