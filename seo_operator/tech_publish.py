"""Выпуск проверенных веток технического SEO штатным путём (B006, 14.10).

Подготовка (seo-tech-run) и выпуск разделены: прогон с моделью готовит ветку и не
имеет учётных данных git; этот шаг моделью не пользуется и выпускает только то,
что уже получило вердикт VERIFIED, тем же путём, что сессия:

  fast-forward ветки выпуска → CI на ветке выпуска → `factory cell trigger
  --confirm-activation` → итог исполнителя → проверка работающего сайта.

VERIFIED — проверенная ПОДГОТОВКА. Опубликованным считается только изменение,
которое исполнитель установил (stage live_verified) и которое подтверждено на
работающем сайте: здоровье витрины и, если задано, `live_check` задачи. Без
`live_check` итог — `released`, а не `live_verified`.

Ограничители (решение — «ждать», а не «выпускать»):
* на ветке выпуска есть невыпущенный чужой коммит (пример 14.10 — publisher_id
  Архитектора на Zona) — выпуск унёс бы чужую правку;
* общий клон репозитория грязный или не на живом коммите — в нём работает
  другая сессия;
* ветка задачи не стоит на живом коммите — задача уходит на повторную подготовку
  (SUPERSEDED), а не перебазируется вслепую;
* выпуск удержан в реестре (release.hold) — триггер сам отвечает «удержан».
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from seo_operator import tech_backlog, tech_run

REPO = tech_run.REPO
RESULTS = Path("/var/lib/site-cells/results")
ОПУБЛИКОВАНО = {"live_verified", "released"}

#: Как часто одна и та же причина ожидания попадает в журнал повторно.
#:
#: Нужна золотая середина. Без повторов журнал молчит, и «жив, но ждёт»
#: становится неотличимо от «не запускался» — это ровно та ошибка, за которую
#: платит отчёт. С повтором на каждом такте получается то, что измерено 18.10:
#: 587 записей «ожидание» по одной задаче, 356 подряд с одной причиной. Шесть
#: часов — это 1–2 записи в рабочий день на задачу: достаточно, чтобы увидеть
#: живое ожидание, и мало, чтобы утопить журнал.
БИЕНИЕ_ОЖИДАНИЯ_Ч = 6


def _сейчас() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(m: dt.datetime | None = None) -> str:
    return (m or _сейчас()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _publish_log(state: Path) -> list[dict]:
    f = state / "publish.jsonl"
    if not f.exists():
        return []
    out = []
    for с in f.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(с))
        except ValueError:
            continue
    return out


def _записать(state: Path, запись: dict) -> dict:
    запись = {"at": _iso(), **запись}
    with open(state / "publish.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(запись, ensure_ascii=False) + "\n")
    return запись


def _повтор_ожидания(state: Path, task_id: str, head: str, причина: str,
                     *, сейчас: dt.datetime | None = None) -> dict:
    """Писать ли ещё одну запись «ожидание» с ТОЙ ЖЕ причиной.

    Счёт ведётся ПО ЖУРНАЛУ, а не по памяти прогона: публикатор запускается
    таймером, каждый раз это новый процесс, и в памяти счётчик всегда был бы
    единицей. Поэтому читается хвост журнала.

    Серией считаются подряд идущие записи ОДНОЙ задачи с тем же `head`, тем же
    исходом `waiting` и ПОЛНОСТЬЮ совпадающей причиной. Сравнение именно
    полное: причины отличаются хвостом («…живой d1627b4b7eaa» против
    «…живой 321bd7e»), и сравнение по префиксу склеило бы разные ситуации в
    одну, то есть скрыло бы смену обстановки.

    Запись возобновляется в трёх случаях: причина изменилась, сменился `head`,
    или с последней записи серии прошло больше `БИЕНИЕ_ОЖИДАНИЯ_Ч` часов.
    """
    серия = []
    for з in reversed(_publish_log(state)):
        if з.get("task_id") != task_id:
            continue
        if (з.get("outcome") == "waiting" and з.get("head") == head
                and str(з.get("reason") or "") == причина):
            серия.append(з)
            continue
        break
    if not серия:
        return {"повтор": False, "сколько": 0, "с": "", "почему": "серии нет"}
    # Биение считается от ПОСЛЕДНЕЙ написанной записи серии, а не от первой.
    # От первой получалось бы так: как только серия стала старше шести часов,
    # писать начинает КАЖДЫЙ такт — то есть шум возвращается целиком, только с
    # задержкой. Проверено проигрыванием живого журнала: от первой правило
    # убирало 22 % записей, от последней — 95 %.
    первая, последняя = серия[-1], серия[0]
    когда_серии = str(первая.get("at") or "")
    когда = str(последняя.get("at") or "")
    try:
        начало = dt.datetime.strptime(когда, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc)
    except ValueError:
        # Нечитаемое время — не повод молчать: пишем запись.
        return {"повтор": False, "сколько": len(серия), "с": когда_серии,
                "почему": "время последней записи серии не разобрано"}
    прошло = (сейчас or _сейчас()) - начало
    if прошло >= dt.timedelta(hours=БИЕНИЕ_ОЖИДАНИЯ_Ч):
        return {"повтор": False, "сколько": len(серия), "с": когда_серии,
                "почему": f"с прошлой записи {прошло.total_seconds() / 3600:.1f} ч"
                          f" — биение журнала"}
    return {"повтор": True, "сколько": len(серия), "с": когда_серии,
            "почему": "причина ожидания не менялась"}


def кандидаты(state: Path) -> list[dict]:
    """Задачи с последним вердиктом VERIFIED, чья голова ещё не опубликована."""
    сводка = tech_run.task_state(state)
    опубликованные = {(р.get("task_id"), р.get("head")) for р in _publish_log(state) if р.get("outcome") in ОПУБЛИКОВАНО}
    задачи = {з["id"]: з for з in tech_run.load_queue(state=state)}
    итог = []
    for tid, с in сводка.items():
        last = с.get("last") or {}
        if с.get("status") != "verified" or last.get("verdict") != "VERIFIED" or not last.get("head"):
            continue
        з = задачи.get(tid)
        if not з or tech_run.вне_продвижения(з):
            continue
        # Выпуск берёт только то, что готовил механизм (queued/verified). Статусы
        # released/live_verified/done — уже опубликовано (в том числе сессией с совмещением
        # веток, когда голова другая); session/blocked — работа сессии или владельца.
        if з.get("status") not in ("queued", "verified"):
            continue
        if (tid, last["head"]) in опубликованные:
            continue
        захват = next((к for к in tech_run._claims(state) if к["run_id"] == last.get("run_id")), {})
        итог.append({"task": з, "run_id": last.get("run_id"), "head": last["head"],
                     "branch": last.get("branch"), "repo": захват.get("repo") or з.get("repo")})
    return итог


def _git(репо: Path, *a: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(репо), *a], capture_output=True, text=True, timeout=600)


def _предок(репо: Path, a: str, b: str) -> bool:
    return _git(репо, "merge-base", "--is-ancestor", a, b).returncode == 0


def решение(сведения: dict) -> tuple[str, str]:
    """Чистое решение по собранным сведениям → (действие, причина).

    Действия: publish | already_live | superseded | wait | hold.
    """
    if сведения.get("hold"):
        return "hold", f"выпуск удержан: {сведения['hold']}"
    live, ci, remote, head = (сведения.get(k) or "" for k in ("live", "ci_commit", "remote_head", "head"))
    if not live:
        return "wait", "живой коммит не определён"
    if сведения.get("head_in_live"):
        return "already_live", "голова задачи уже в живом выпуске (выпущена этим или чужим выпуском)"
    if ci and not ci.startswith(live[:12]) and not live.startswith(ci[:12]):
        return "wait", f"на ветке выпуска невыпущенный коммит {ci[:12]} (живой {live[:12]}) — выпуск унёс бы его"
    if remote and not remote.startswith(live[:12]) and not live.startswith(remote[:12]):
        return "wait", f"голова ветки выпуска {remote[:12]} не равна живому {live[:12]} (идёт CI или чужой push)"
    if сведения.get("clone_dirty"):
        return "wait", "общий клон репозитория грязный — в нём работает другая сессия"
    if not сведения.get("clone_on_live"):
        return "wait", "общий клон не на живом коммите — в нём работает другая сессия"
    if not сведения.get("live_in_head"):
        return "superseded", f"ветка задачи не стоит на живом коммите {live[:12]} — нужна повторная подготовка"
    return "publish", "fast-forward ветки выпуска на голову задачи"


def _ячейка_по_репо(repo: str) -> dict | None:
    for домен, c in tech_backlog.promoted_cells().items():
        if c["repo"] == repo:
            return {"domain": домен, **c}
    return None


def _trigger(site_id: str, confirm: bool) -> dict:
    cmd = ["python3", "-m", "factory", "cell", "trigger", "--site", site_id] + (["--confirm-activation"] if confirm else [])
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=900)
    try:
        return json.loads(r.stdout)["sites"][0]
    except Exception:  # noqa: BLE001
        return {"action": "ошибка", "blocked": (r.stdout + r.stderr)[-400:]}


def _живой_по_странице(site_id: str) -> str:
    """Живой коммит ячейки по публичному build-id (как у factory.cell.trigger). Только чтение."""
    try:
        from factory.cell import registry as реестр, trigger as триггер
        return триггер.живой_коммит(реестр.resolve(site_id)) or ""
    except Exception:  # noqa: BLE001 — нет ответа — решение «ждать», как и прежде
        return ""


def _ci(gh_repo: str, ветка: str, sha: str, ждать_с: int) -> str:
    конец = time.time() + ждать_с
    while True:
        r = subprocess.run(["gh", "run", "list", "-R", gh_repo, "-b", ветка, "-c", sha, "--json", "status,conclusion"],
                           capture_output=True, text=True, timeout=120)
        try:
            j = json.loads(r.stdout or "[]")
        except ValueError:
            j = []
        if j and all(x.get("status") == "completed" for x in j):
            return "success" if all(x.get("conclusion") == "success" for x in j) else j[0].get("conclusion") or "failure"
        if time.time() > конец:
            return "timeout"
        time.sleep(30)


def _http(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "seo-tech-publish"}), timeout=60) as о:
            return о.status, о.read(2_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def проверить_живой(домен: str, live_check: list[dict] | None, http: Callable[[str], tuple[int, str]] = _http) -> dict:
    """Здоровье витрины + live_check задачи. Возвращает {"health": bool, "task": bool|None, "notes": [...]}."""
    notes: list[str] = []
    ok = True
    for путь in ("/", "/robots.txt", "/sitemap.xml"):
        код, _ = http(f"https://{домен}{путь}")
        if код != 200:
            ok = False
            notes.append(f"{путь}: {код}")
    задача: bool | None = None
    if live_check:
        задача = True
        for п in live_check:
            код, тело = http(п["url"])
            if п.get("status", 200) != код:
                задача = False
                notes.append(f"{п['url']}: код {код}, ждали {п.get('status', 200)}")
            for с in п.get("contains") or []:
                if с not in тело:
                    задача = False
                    notes.append(f"{п['url']}: нет «{с[:60]}»")
            for с in п.get("absent") or []:
                if с in тело:
                    задача = False
                    notes.append(f"{п['url']}: есть «{с[:60]}»")
    return {"health": ok, "task": задача, "notes": notes}


def _результат_исполнителя(site_id: str, sha: str, ждать_с: int = 1200) -> dict:
    f = RESULTS / f"{site_id}-code-{sha[:12]}.json"
    конец = time.time() + ждать_с
    while time.time() < конец:
        if f.exists():
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                j = {}
            if j.get("status"):
                return {"status": j["status"], "stage": (j.get("outcome") or {}).get("stage"), "file": str(f)}
        time.sleep(10)
    return {"status": "timeout", "file": str(f)}


def опубликовать_одну(к: dict, state: Path, *, dry_run: bool = False) -> dict:
    """Одна задача: сведения → решение → (выпуск) → проверка → запись."""
    з, head = к["task"], к["head"]
    c = _ячейка_по_репо(к["repo"])
    if not c:
        return _записать(state, {"task_id": з["id"], "head": head, "outcome": "skipped",
                                 "reason": f"репозиторий {к['repo']} не продвигаемая ячейка"}) if not dry_run else {"skip": к["repo"]}
    репо = REPO / к["repo"]
    t = _trigger(c["site_id"], confirm=False)
    if t.get("action") == "удержан":
        сведения = {"hold": t.get("reason") or "удержан"}
    else:
        ветка = t.get("branch") or ""
        live = t.get("live_commit") or ""
        if not live:
            # Триггер мог отказать до ответа о живом коммите: «кандидат старше
            # работающего», когда последний успешный CI — плановый прогон на другой
            # разрешённой ветке (lordserial33.biz 15.10: schedule на 761ae97 при
            # живом 321bd7e). Тогда живой коммит читается тем же способом, что у
            # триггера — по публичному build-id, только чтение; ветка выпуска —
            # та, на которой стоит клон. После отправки головы задачи CI на ветке
            # выпуска даст свежий прогон, и триггер возьмёт его.
            live = _живой_по_странице(c["site_id"])
        if not ветка:
            ветка = _git(репо, "branch", "--show-current").stdout.strip()
        _git(репо, "fetch", "-q", "origin", ветка)
        remote = _git(репо, "rev-parse", "FETCH_HEAD").stdout.strip()
        live_full = _git(репо, "rev-parse", "--verify", "-q", f"{live}^{{commit}}").stdout.strip() if live else ""
        сведения = {
            "live": live_full or live, "ci_commit": t.get("commit") or "", "remote_head": remote, "head": head,
            "head_in_live": bool(live_full) and _предок(репо, head, live_full),
            "live_in_head": bool(live_full) and _предок(репо, live_full, head),
            "clone_dirty": bool(_git(репо, "status", "--porcelain").stdout.strip()),
            "clone_on_live": bool(live_full) and _git(репо, "rev-parse", "HEAD").stdout.strip() == live_full,
            "branch": ветка,
        }
    действие, причина = решение(сведения)
    база = {"task_id": з["id"], "head": head, "site_id": c["site_id"], "domain": c["domain"],
            "decision": действие, "reason": причина}
    if dry_run:
        return {**база, "facts": {k: v for k, v in сведения.items() if k != "hold"}}
    if действие in ("wait", "hold"):
        # Задача ждёт по той же причине, что и в прошлый такт — новая запись
        # ничего не добавляет. Запись пропускается, но ИСХОД возвращается:
        # прогон о задаче отчитывается, задача остаётся кандидатом, а журнал не
        # растёт на 356 одинаковых строк (T175, измерено 18.10).
        повтор = _повтор_ожидания(state, з["id"], head, причина)
        if повтор["повтор"]:
            return {**база, "outcome": "waiting_skipped",
                    "waiting_since": повтор["с"], "repeats": повтор["сколько"],
                    "skip_reason": повтор["почему"]}
        return _записать(state, {**база, "outcome": "waiting"})
    if действие == "superseded":
        tech_run.record({"run_id": f"{к['run_id']}-superseded", "task_id": з["id"], "verdict": "SUPERSEDED",
                         "steps": {}, "notes": [причина]}, {"trigger": "publish", "finished_at": _iso()}, state)
        return _записать(state, {**база, "outcome": "superseded"})
    if действие == "publish":
        gh_repo = re.sub(r"\.git$", "", (_git(репо, "remote", "get-url", "origin").stdout.strip()).split("github.com/")[-1])
        ветка = сведения["branch"]
        push = _git(репо, "push", "-q", "origin", f"{head}:refs/heads/{ветка}")
        if push.returncode:
            return _записать(state, {**база, "outcome": "push_failed", "reason": push.stderr.strip()[-300:]})
        ci = _ci(gh_repo, ветка, head, 40 * 60)
        if ci != "success":
            # cancelled — обычно чужой push в ту же ветку: следующий проход решит заново.
            return _записать(state, {**база, "outcome": f"ci_{ci}"})
        # Общий клон: если он стоит на ветке выпуска (так держит его Архитектор), ветка
        # продвигается fast-forward и клон остаётся на ней; иначе — отделённый HEAD на голове.
        if _git(репо, "branch", "--show-current").stdout.strip() == ветка:
            co = _git(репо, "merge", "-q", "--ff-only", head)
        else:
            co = _git(репо, "checkout", "-q", "--detach", head)
        if co.returncode:
            return _записать(state, {**база, "outcome": "checkout_failed", "reason": co.stderr.strip()[-300:]})
        t2 = _trigger(c["site_id"], confirm=True)
        if "проверка доступа" in str(t2.get("blocked") or ""):
            subprocess.run(["python3", "-m", "factory", "cell", "submit", "--site", c["site_id"],
                            "--cell-operation", "access-check"], cwd=REPO, capture_output=True, text=True, timeout=600)
            time.sleep(60)
            t2 = _trigger(c["site_id"], confirm=True)
        if t2.get("action") != "заявка подана":
            return _записать(state, {**база, "outcome": "not_submitted", "reason": str(t2.get("blocked") or t2.get("action"))[:300]})
        итог_исп = _результат_исполнителя(c["site_id"], head)
        if итог_исп.get("status") != "ok":
            return _записать(state, {**база, "outcome": "executor_" + str(итог_исп.get("status")), "executor": итог_исп})
        база["executor"] = итог_исп
    # publish (после ok исполнителя) и already_live — одинаковая проверка работающего сайта
    живой = проверить_живой(c["domain"], з.get("live_check"))
    if not живой["health"] or живой["task"] is False:
        исход = "live_check_failed"
    elif живой["task"] is True:
        исход = "live_verified"
    else:
        исход = "released"
    return _записать(state, {**база, "outcome": исход, "live": живой})


def run(state: Path | None = None, *, dry_run: bool = False, limit: int = 5) -> list[dict]:
    state = state or tech_run.STATE
    state.mkdir(parents=True, exist_ok=True)
    итог = []
    for к in кандидаты(state)[:limit]:
        try:
            итог.append(опубликовать_одну(к, state, dry_run=dry_run))
        except Exception as ош:  # noqa: BLE001 — одна задача не держит остальные
            итог.append(_записать(state, {"task_id": к["task"]["id"], "head": к["head"], "outcome": "error",
                                          "reason": f"{type(ош).__name__}: {str(ош)[:300]}"}) if not dry_run
                        else {"task_id": к["task"]["id"], "error": str(ош)[:300]})
    return итог


def status(state: Path | None = None) -> list[dict]:
    """Состояние публикации по задачам: последний итог выпуска для последней проверенной головы."""
    state = state or tech_run.STATE
    сводка = tech_run.task_state(state)
    журнал = _publish_log(state)
    out = []
    for з in tech_run.load_queue(state=state):
        с = сводка.get(з["id"], {})
        last = с.get("last") or {}
        if not last:
            continue
        публ = [р for р in журнал if р.get("task_id") == з["id"]]
        out.append({"id": з["id"], "site": з.get("site"), "prepared": last.get("verdict"),
                    "head": (last.get("head") or "")[:12],
                    "publish": (публ[-1].get("outcome") if публ else None),
                    "publish_reason": (публ[-1].get("reason") if публ else None)})
    return out
