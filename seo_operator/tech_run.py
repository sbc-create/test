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
import os
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


class ЗанятоДругимПрогоном(RuntimeError):
    """Задачу уже держит живой захват другого прогона."""


def _замок(state: Path, task_id: str) -> Path:
    return state / "claims" / f"{task_id}.claim"


def _замок_свеж(замок: Path, now: dt.datetime) -> bool:
    try:
        возраст = now.timestamp() - замок.stat().st_mtime
    except FileNotFoundError:
        return False
    return возраст < STALE_S


def task_state(state: Path = STATE, now: dt.datetime | None = None) -> dict[str, dict[str, Any]]:
    """Сводка по задачам из следов: последний вердикт, число неудач, живой захват.

    «Занято» — ТОЛЬКО файл-замок claims/<id>.claim (один источник правды);
    claims.jsonl — журнал захватов, на занятость не влияет.
    """
    now = now or _сейчас()
    итог: dict[str, dict[str, Any]] = {}
    for р in _runs(state):
        з = итог.setdefault(р["task_id"], {"failures": 0})
        з["last"] = р
        if р.get("verdict") == "VERIFIED":
            з["status"] = "verified"
        elif р.get("verdict") != "NO_TASK":
            з["failures"] += 1
    for замок in sorted((state / "claims").glob("*.claim")) if (state / "claims").is_dir() else []:
        if _замок_свеж(замок, now):
            итог.setdefault(замок.stem, {"failures": 0})["open_claim"] = замок.read_text(encoding="utf-8").strip()
    return итог


def candidates(задачи: list[dict], state: Path = STATE, now: dt.datetime | None = None) -> list[dict]:
    """Задачи queued без вердикта, без живого замка и с запасом попыток — по порядку очереди."""
    сводка = task_state(state, now)
    итог = []
    for з in задачи:
        if з.get("status") != "queued":
            continue
        с = сводка.get(з["id"], {})
        if с.get("status") in ГОТОВО or с.get("failures", 0) >= MAX_ATTEMPTS or с.get("open_claim"):
            continue
        итог.append(з)
    return итог


def next_task(задачи: list[dict], state: Path = STATE, now: dt.datetime | None = None) -> dict | None:
    """Первая доступная задача (без захвата; атомарный захват делает claim)."""
    к = candidates(задачи, state, now)
    return к[0] if к else None


def claim(задача: dict, run_id: str, state: Path = STATE, now: dt.datetime | None = None) -> dict[str, Any]:
    """АТОМАРНЫЙ захват (O_EXCL на файл-замок задачи) + отдельная рабочая копия на новой ветке.

    Из двух одновременных прогонов файл создаст ровно один; второй получает
    ЗанятоДругимПрогоном и берёт следующую задачу. Просроченный замок (mtime
    старше STALE_S) снимается и захватывается заново — один раз.
    """
    now = now or _сейчас()
    замок = _замок(state, задача["id"])
    замок.parent.mkdir(parents=True, exist_ok=True)
    for попытка in (1, 2):
        try:
            дескр = os.open(замок, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            break
        except FileExistsError:
            if попытка == 1 and not _замок_свеж(замок, now):
                замок.unlink(missing_ok=True)
                continue
            raise ЗанятоДругимПрогоном(задача["id"]) from None
    with os.fdopen(дескр, "w", encoding="utf-8") as fh:
        fh.write(f"{run_id} {now.strftime('%Y-%m-%dT%H:%M:%SZ')}\n")
    try:
        репо = REPO / задача["repo"]
        база = _git(репо, "rev-parse", "HEAD")
        ветка = f"claude/seo-tech-{задача['id'].lower()}-{run_id.lower()}"
        копия = state / "wt" / run_id
        копия.parent.mkdir(parents=True, exist_ok=True)
        _git(репо, "worktree", "add", "-q", "-b", ветка, str(копия), база)
    except Exception:
        замок.unlink(missing_ok=True)
        raise
    запись = {"run_id": run_id, "task_id": задача["id"], "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "repo": задача["repo"], "base_sha": база, "branch": ветка, "worktree": str(копия)}
    with open(state / "claims.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(запись, ensure_ascii=False) + "\n")
    (state / "next.json").write_text(json.dumps({**запись, "task": задача}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    return запись


def claim_next(задачи: list[dict], run_id: str, state: Path = STATE) -> dict[str, Any] | None:
    """Взять первую задачу, которую удалось захватить атомарно; занятые пропускаются."""
    for з in candidates(задачи, state):
        try:
            return claim(з, run_id, state)
        except ЗанятоДругимПрогоном:
            continue
    return None


def prune_worktrees(state: Path = STATE, now: dt.datetime | None = None) -> list[str]:
    """Убрать брошенные рабочие копии — В НАЧАЛЕ каждого прогона, до захвата.

    Копия брошена, если её прогон закрыт (есть в runs.jsonl) или замок её задачи
    отсутствует, просрочен либо принадлежит другому прогону. Замок, принадлежащий
    брошенной копии и просроченный, снимается. Ветка остаётся (её смотрит человек).
    Восстановление после прерывания — свойство следующего прогона, а не человека.
    """
    now = now or _сейчас()
    убрано: list[str] = []
    корень = state / "wt"
    if not корень.is_dir():
        return убрано
    закрытые = {р["run_id"] for р in _runs(state)}
    захваты = {к["run_id"]: к for к in _claims(state)}
    репозитории: set[Path] = set()
    for копия in sorted(корень.iterdir()):
        run_id = копия.name.split("-verify-")[0]
        к = захваты.get(run_id)
        замок = _замок(state, к["task_id"]) if к else None
        владелец = замок.read_text(encoding="utf-8").split()[0] if замок and замок.exists() else ""
        живой = замок is not None and _замок_свеж(замок, now) and владелец == run_id
        if run_id in закрытые or not живой:
            репо = REPO / к["repo"] if к else None
            if репо:
                _git(репо, "worktree", "remove", "--force", str(копия), check=False)
                репозитории.add(репо)
            if копия.exists():
                shutil.rmtree(копия, ignore_errors=True)
            if замок and владелец == run_id and not живой:
                замок.unlink(missing_ok=True)
            убрано.append(копия.name)
    for репо in репозитории:
        _git(репо, "worktree", "prune", check=False)
    return убрано


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
                # Коды проверок: 1 — дефект на месте, 2 — проверка не смогла
                # выполниться. Необработанное исключение Python тоже даёт 1,
                # поэтому трассировка в выводе — признак непригодности, а не дефекта.
                непригодна = any(rc not in (0, 1) or "Traceback (most recent call last)" in out
                                 for rc, out in ((rc_база, вывод_база), (rc_голова, вывод_голова)))
                шаги["check_usable"] = not непригодна
                if непригодна:
                    заметки.append(f"проверка непригодна: база rc={rc_база} {вывод_база[-200:]!r}; "
                                   f"ветка rc={rc_голова} {вывод_голова[-200:]!r}")
                шаги["check_fails_on_base"] = rc_база == 1 and not непригодна
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
             "check_usable", "check_fails_on_base", "check_passes_on_branch"] + (["run_all_passes"] if run_all else [])
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
        замок = _замок(state, захват["task_id"])
        if замок.exists() and замок.read_text(encoding="utf-8").split()[:1] == [run_id]:
            замок.unlink(missing_ok=True)
