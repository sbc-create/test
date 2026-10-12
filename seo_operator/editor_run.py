"""Проверка запуска фонового редактора — по следам, а не по его словам.

Запуск считается ПОЛНЫМ, только если для его имени владельца
(`editor/claude-auto/run-<run_id>`) найдены все пять следов:

1. получение задачи — `task_claimed` в журнале очереди;
2. чтение источника — вызов `editorial_facts` моста в окне запуска (журнал
   моста) ИЛИ перечень фактов в результате задания;
3. написание — `task_result` с исходом TEXT_WRITTEN и решением ворот;
4. публикация — запись `publish` этого автора в history.jsonl хранилища;
5. проверка публичной страницы — ответ 200 и текст опубликованной редакции в
   видимом тексте страницы (проверяется ЗДЕСЬ, независимо от исполнителя).

Отчёт исполнителя о себе — не доказательство: «опубликовал» без записи в
хранилище и без текста на странице не засчитывается.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import html
import json
import os
import re
import subprocess
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

QUEUE_EVENTS = Path("/var/lib/seo-content-operator/queue_events.jsonl")
OVERLAY_ROOTS = {
    "animedia": (Path("/srv/sites/animedia/runtime/overlays"), "/title/{slug}/"),
    "yummy": (Path("/srv/sites/yummyani-staging/runtime/overlays"), "/anime/{slug}"),
    # Lords/Zona (доставка очередью): журнал и копия опубликованного — здесь,
    # файл правок сайта — в его каталоге данных. Без этого корня запуски с
    # публикацией на этих доменах считались неполными (2026-10-09, 10:55 и 11:50).
    "lords": (Path("/srv/sites/lords/runtime/overlays"), "/title/{slug}/"),
    "animego": (Path("/srv/sites/animego/runtime/overlays"), "/title/{slug}/"),
}
BRIDGE_UNIT = "site-factory-mcp.service"


def owner_for(run_id: str) -> str:
    return f"editor/claude-auto/run-{run_id}"


def _events(path: Path, owner: str) -> list[dict]:
    out = []
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("owner") == owner:
            out.append(e)
    return out


def _store(site_dir: Path) -> dict:
    """Опубликованное хранилище: наложение или копия доставки очередью."""
    for name in ("title-overlays.json", "published.json"):
        try:
            data = json.loads((site_dir / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("items"):
            return data
    return {}


def _publications(roots: dict, owner: str) -> list[dict]:
    out = []
    for _family, (root, form) in roots.items():
        if not root.is_dir():
            continue
        for site_dir in root.iterdir():
            history = site_dir / "history.jsonl"
            if not history.is_file():
                continue
            for line in history.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("op") == "publish" and r.get("author") == owner:
                    store = _store(site_dir)
                    body = next(
                        (
                            i.get("body")
                            for i in store.get("items") or []
                            if i.get("slug") == r["slug"]
                        ),
                        None,
                    )
                    out.append(
                        {
                            "site": site_dir.name,
                            "slug": r["slug"],
                            "at": r["at"],
                            "url": f"https://{site_dir.name}" + form.format(slug=r["slug"]),
                            "body": body,
                        }
                    )
    return out


def _bridge_calls(since: str, until: str) -> list[dict]:
    """Вызовы моста в окне запуска. Нет доступа к журналу — пусто, это видно в отчёте."""
    try:
        res = subprocess.run(
            [
                "journalctl",
                "-u",
                BRIDGE_UNIT,
                "--since",
                since.replace("T", " ").rstrip("Z"),
                "--until",
                until.replace("T", " ").rstrip("Z"),
                "--no-pager",
                "-o",
                "cat",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    calls = []
    for line in res.stdout.splitlines():
        if line.startswith("{"):
            try:
                c = json.loads(line)
            except ValueError:
                continue
            if c.get("tool") and c.get("outcome") != "started":
                calls.append(c)
    return calls


def _page_has(url: str, body: str, fetch: Callable[[str], tuple[int | None, str]]) -> dict:
    status, raw = fetch(url)
    visible = re.sub(
        r"\s+",
        " ",
        html.unescape(
            re.sub(
                r"(?s)<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw or "")
            )
        ),
    )
    fragment = re.sub(r"\s+", " ", body or "").strip()[:80]
    return {"url": url, "status": status, "text_visible": bool(fragment) and fragment in visible}


def _fetch(url: str) -> tuple[int | None, str]:
    req = urllib.request.Request(
        url, headers={"User-Agent": "editor-run-verify/1", "Cache-Control": "no-cache"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read(2_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, OSError):
        return None, ""


def verify(
    run_id: str,
    started_at: str,
    finished_at: str,
    *,
    events_path: Path = QUEUE_EVENTS,
    roots: dict | None = None,
    bridge_calls: Callable[[str, str], list[dict]] = _bridge_calls,
    fetch: Callable[[str], tuple[int | None, str]] = _fetch,
) -> dict[str, Any]:
    owner = owner_for(run_id)
    events = _events(events_path, owner)
    claimed = [e for e in events if e.get("event") == "task_claimed"]
    written = [
        e for e in events if e.get("event") == "task_result" and e.get("outcome") == "TEXT_WRITTEN"
    ]
    pubs = _publications(roots if roots is not None else OVERLAY_ROOTS, owner)
    calls = bridge_calls(started_at, finished_at)
    read_source = any(
        c.get("tool") == "editorial_facts" and c.get("outcome") == "ok" for c in calls
    )
    pages = [_page_has(p["url"], p["body"], fetch) for p in pubs]
    # Итог КАЖДОГО взятого задания, а не только TEXT_WRITTEN: партия, где все
    # задания закрыты законными отказами, отличается от партии, бросившей
    # задание без итога (19:25Z 12.10 — 4 задания, 4 итога, а в отчёте пусто).
    итоги = [e for e in events if e.get("event") == "task_result"]
    с_итогом = {e.get("task_id") for e in итоги}
    без_итога = sorted({e.get("task_id") for e in claimed} - с_итогом)
    комментарии = sum(1 for c in calls if c.get("tool") == "publish_comment" and c.get("outcome") == "ok")
    steps = {
        "claimed": bool(claimed),
        "source_read": read_source,
        "written": bool(written),
        "published": bool(pubs),
        "public_page_verified": bool(pages)
        and all(p["status"] == 200 and p["text_visible"] for p in pages),
    }
    return {
        "run_id": run_id,
        "owner": owner,
        "window": [started_at, finished_at],
        "steps": steps,
        "complete": all(steps.values()),
        "tasks": sorted({e.get("task_id") for e in claimed}),
        "results": [
            {
                "task_id": e.get("task_id"),
                "outcome": e.get("outcome"),
                "gate": (e.get("gate") or {}).get("status"),
            }
            for e in written
        ],
        "outcomes": [{"task_id": e.get("task_id"), "outcome": e.get("outcome")} for e in итоги],
        "unresolved": без_итога,
        "comments_published": комментарии,
        "publications": [{k: p[k] for k in ("site", "slug", "at", "url")} for p in pubs],
        "pages": pages,
        "bridge_calls_seen": len(calls),
        "checked_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def status(state: Path | None = None) -> dict:
    """Запуски по расписанию и ручные — раздельно; подтверждает только полный по расписанию."""
    state = state or STATE
    runs = []
    log = state / "runs.jsonl"
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                runs.append(json.loads(line))
            except ValueError:
                continue
    scheduled = [r for r in runs if r.get("trigger") == "systemd-timer"]
    complete = [r for r in scheduled if r.get("verdict") == "COMPLETE"]
    timer = Path("/etc/systemd/system/editor-run.timer")
    return {
        "timer_installed": timer.is_file(),
        "enabled": Path("/etc/systemd/system/timers.target.wants/editor-run.timer").exists(),
        "scheduled_runs": len(scheduled),
        "scheduled_complete": len(complete),
        "last_scheduled": scheduled[-1] if scheduled else None,
        "manual_runs": [
            r.get("run_id") + ":" + str(r.get("trigger"))
            for r in runs
            if r.get("trigger") != "systemd-timer"
        ],
        "confirmed": bool(complete),
        "now": current_state(state),
    }


MSK = dt.timezone(dt.timedelta(hours=3))


def _lock_held(lock: Path) -> bool:
    """Держит ли кто-то замок партии (flock в editor-run.sh). Только проба."""
    try:
        fh = open(lock, "a")  # noqa: SIM115 — замок проверяется и тут же отпускается
    except OSError:
        return False
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return True
    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    fh.close()
    return False


def current_state(state: Path | None = None, now: dt.datetime | None = None) -> dict:
    """Почему редактор сейчас работает или ждёт — для editor-run-status.

    Без пересчёта кандидатов и без сети: идёт партия (замок занят) — или
    последнее решение шлюза из журнала и ближайшее допустимое время запуска.
    """
    state = state or STATE
    now = now or dt.datetime.now(dt.timezone.utc)
    conf = cadence()
    next_at, pause, why = _pause_after(_runs(state), conf)
    last_gate = None
    try:
        lines = (state / "gate.jsonl").read_text(encoding="utf-8").splitlines()
        last_gate = json.loads(lines[-1]) if lines else None
    except (OSError, ValueError):
        pass
    out = {
        "batch_running": _lock_held(state / "run.lock"),
        "pause_after_batch_min": conf["pause_after_batch_s"] // 60,
        "pause_rule": why or "партий ещё не было",
        "earliest_next_msk": (
            next_at.astimezone(MSK).strftime("%Y-%m-%d %H:%M") if next_at else None
        ),
        "last_gate": last_gate,
    }
    if out["batch_running"]:
        out["state"] = "running"
    elif next_at and now < next_at:
        out["state"] = "backoff" if why.startswith("сбоев") else "paused"
    else:
        out["state"] = (last_gate or {}).get("gate", {}).get("state") or "unknown"
    return out


REGISTRY = Path("/var/lib/seo-content-operator/registry.json")
LEASES = Path("/var/lib/seo-content-operator/editorial_leases.json")
STATE = Path(__file__).resolve().parents[1] / "var" / "editor-runs"
CANDIDATES = Path(__file__).resolve().parents[1] / "var" / "seo-regular" / "editor-candidates.json"
ANIMEDIA = ("animedia.icu", "animedia.space")
#: Где редактор публикует с подтверждённым показом (regular.EDITOR_SITES).
EDITOR_DOMAINS = (
    *ANIMEDIA,
    "zonafilm.space",
    "lordfilm47.space",
    "lordserial33.biz",
    "1lordserials1.online",
    "lordserials22.info",
    "zonafilm12.site",
    # Ночь 9→10 октября: читатель правок выпущен (bf63a60c60bd, исполнитель
    # ответил live_verified), публикация подтверждена на странице —
    # zonafilm.cc/title/ad-dzheffri/. До этого витрина не умела показывать
    # опубликованный текст вовсе.
    "zonafilm.cc",
    "an1meg0.site",
    "an1mego.site",
    "animeg0.site",
    # Yummy — только задания очереди: снимка каталога у семейства нет, кандидаты
    # не строятся. Показ подтверждён 2026-10-09 (накладка по схеме, afd5b65).
    "yummyani.site",
    # С 2026-10-09: показ yummyani.org подтверждён первой публикацией
    # (izgnannyy-reinkarnirovannyy-..., текст в видимой разметке и в meta);
    # идентификатор первой записи домена даёт поиск самого приложения.
    "yummyani.org",
    # Ночь 9→10 октября: контейнеры трёх витрин пересозданы с монтированием
    # каталога накладок, показ подтверждён публикацией на каждой —
    # yummyani7.site/anime/ya-vedma-..., yummyani7.info/anime/ya-perevoplotilsya-...,
    # yummyani.biz/anime/silneyshaya-vedma-... (HTTP 200, текст в основном блоке).
    "yummyani7.site",
    "yummyani7.info",
    "yummyani.biz",
)
#: Режим запусков (config/editor-run.json). Владелец 2026-10-10: круглосуточно,
#: пауза 20 минут ПОСЛЕ ЗАВЕРШЕНИЯ партии вместо почасового цикла; таймер,
#: flock и единственный исполнитель прежние. Значения по умолчанию — те же,
#: что в файле: без файла режим не меняется молча.
CADENCE_FILE = Path(__file__).resolve().parents[1] / "config" / "editor-run.json"
CADENCE_DEFAULTS = {
    "pause_after_batch_s": 1200,
    # Повторяющиеся сбои: пауза растёт base·factor^(n-1), не больше max.
    "error_backoff": {"factor": 2, "max_s": 14400},
    # Обоснование порогов — docs/editor/BACKGROUND_EDITOR.md («Режим запусков»):
    # служба редактора ограничена MemoryMax=2G; партия не начинается, если
    # столько памяти нет, если ядро уже стоит в ожидании памяти (PSI full) или
    # процессор перегружен.
    "resources": {
        "mem_available_min_mib": 2048,
        "memory_full_avg60_max_pct": 5.0,
        "load1_per_cpu_max": 1.0,
    },
}
#: Исходы партии, которые считаются сбоем для нарастающей паузы. Честное «задач
#: нет» и полный запуск сбоем не являются.
ERROR_VERDICTS = ("INCOMPLETE",)


def verdict(report: dict, self_report: dict, comments_visible: int) -> str:
    """Вердикт партии для runs.jsonl; сбоем (ERROR_VERDICTS) считается только INCOMPLETE.

    * COMPLETE — полный путь текста подтверждён (строгое `complete`, не меняется);
    * RESOLVED — текста нет, но у КАЖДОГО взятого задания записан итог, и каждый
      комментарий, опубликованный по журналу моста, увиден браузером
      (`comments_visible` — сколько подтвердил comment-visible-check.py). Это
      работа партии, а не сбой: 19:25Z 12.10 — 4 законных отказа и 3 видимых
      комментария засчитывались INCOMPLETE и удлиняли паузу;
    * NO_PUBLICATION — честное «работы нет» в самоотчёте и ничего не опубликовано;
    * INCOMPLETE — всё остальное: задание без итога, неподтверждённый
      комментарий, описание без видимой страницы.
    """
    if report.get("complete"):
        return "COMPLETE"
    steps = report.get("steps") or {}
    опубликовано_текстов = steps.get("published")
    комментарии = int(report.get("comments_published") or 0)
    if (not опубликовано_текстов and not report.get("unresolved")
            and (report.get("outcomes") or комментарии)
            and comments_visible >= комментарии):
        return "RESOLVED"
    if self_report.get("outcome") in ("NO_TASK", "SOURCES_MISSING") and not опубликовано_текстов:
        return "NO_PUBLICATION"
    return "INCOMPLETE"


def cadence(path: Path | None = None) -> dict:
    try:
        raw = json.loads((path or CADENCE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    out = json.loads(json.dumps(CADENCE_DEFAULTS))
    for key, value in raw.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key].update(value)
        elif key in out:
            out[key] = value
    return out


def _proc(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def resources(limits: dict, *, reader=_proc) -> dict:
    """Хватает ли ресурсов на партию. Чтение /proc, без внешних команд.

    Недоступный показатель не блокирует запуск (его нет — нечего сравнивать), но
    называется в ответе.
    """
    out: dict = {"ok": True, "problems": [], "measured": {}}
    mem = re.search(r"^MemAvailable:\s+(\d+)\s+kB", reader("/proc/meminfo"), re.M)
    if mem:
        mib = int(mem.group(1)) // 1024
        out["measured"]["mem_available_mib"] = mib
        if mib < limits["mem_available_min_mib"]:
            out["problems"].append(
                f"памяти доступно {mib} МиБ < {limits['mem_available_min_mib']} МиБ"
            )
    psi = re.search(r"^full avg10=[\d.]+ avg60=([\d.]+)", reader("/proc/pressure/memory"), re.M)
    if psi:
        full = float(psi.group(1))
        out["measured"]["memory_full_avg60_pct"] = full
        if full > limits["memory_full_avg60_max_pct"]:
            out["problems"].append(
                f"давление памяти full avg60 {full}% > {limits['memory_full_avg60_max_pct']}%"
            )
    load = reader("/proc/loadavg").split()
    if load:
        per_cpu = float(load[0]) / max(1, os.cpu_count() or 1)
        out["measured"]["load1_per_cpu"] = round(per_cpu, 2)
        if per_cpu > limits["load1_per_cpu_max"]:
            out["problems"].append(
                f"загрузка {per_cpu:.2f} на ядро > {limits['load1_per_cpu_max']}"
            )
    out["ok"] = not out["problems"]
    return out


def _runs(state: Path) -> list[dict]:
    out = []
    log = state / "runs.jsonl"
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _pause_after(runs: list[dict], conf: dict) -> tuple[dt.datetime | None, int, str]:
    """(время, раньше которого не запускать; длина паузы, с; причина)."""
    started = [r for r in runs if r.get("model_started")]
    if not started:
        return None, 0, ""
    last = started[-1]
    finished = last.get("finished_at") or last.get("started_at")
    end = dt.datetime.fromisoformat(str(finished).replace("Z", "+00:00"))
    ошибок = 0
    for r in reversed(started):
        if r.get("verdict") in ERROR_VERDICTS:
            ошибок += 1
        else:
            break
    base = int(conf["pause_after_batch_s"])
    if ошибок:
        eb = conf["error_backoff"]
        pause = min(int(base * eb["factor"] ** (ошибок - 1)), int(eb["max_s"]))
        why = f"сбоев подряд: {ошибок}, пауза увеличена до {pause // 60} мин"
    else:
        pause, why = base, f"пауза {base // 60} мин после завершения партии"
    return end + dt.timedelta(seconds=pause), pause, why


def _key(url: str) -> str:
    return url.rstrip("/").lower()


def gate(
    now: dt.datetime | None = None,
    *,
    registry: Path = REGISTRY,
    leases: Path = LEASES,
    events: Path = QUEUE_EVENTS,
    candidates: Path = CANDIDATES,
    state: Path = STATE,
    refresh: bool = False,
    recent: dict[str, int] | None = None,
    conf: dict | None = None,
    resources_fn=None,
) -> dict:
    """Нужен ли запуск модели. Файлы и /proc: ни модели, ни внешних команд.

    Порядок: (1) пауза после завершения прошлой партии (20 мин; при сбоях
    подряд — нарастающая); (2) ресурсы; (3) работа: свободное задание очереди
    на домене цикла или кандидат без результата. Пропущенные за время простоя
    партии не догоняются: следующая начинается одна, по этому же правилу.
    Каждый ответ несёт `state`: paused | backoff | resources | no_work | run.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    conf = conf or cadence()
    next_at, _pause, why = _pause_after(_runs(state), conf)
    if next_at and now < next_at:
        return {
            "run": False,
            "state": "backoff" if why.startswith("сбоев") else "paused",
            "reason": f"{why}: до {next_at.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "next_at": next_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    res = (resources_fn or (lambda: resources(conf["resources"])))()
    if not res["ok"]:
        return {
            "run": False,
            "state": "resources",
            "reason": "недостаточно ресурсов: " + "; ".join(res["problems"]),
            "resources": res["measured"],
        }
    решение = _work(
        now,
        registry=registry,
        leases=leases,
        events=events,
        candidates=candidates,
        state=state,
        refresh=refresh,
        recent=recent,
    )
    решение["state"] = "run" if решение["run"] else "no_work"
    решение["resources"] = res["measured"]
    return решение


def переданные_черновики() -> list[dict]:
    """Черновики комментариев, переданные готовящей стороной на проверку.

    Почему это считается РАБОТОЙ шлюза. Передача (`submit_comment`) появилась
    10 октября, и без этой функции она была бы передачей в пустоту: шлюз
    считал работой только свободные задания очереди и кандидатов без
    результата, поэтому при исчерпанных кандидатах он отвечал `no_work`,
    запуска не происходило вовсе — и готовый, проверенный текст лежал бы, пока
    редактора не позовёт другая причина. Промпт при этом велит разбирать
    переданное первым, то есть обещание было, а механизма не было.

    Отказ читается, а не роняет шлюз: слой фабрики может быть недоступен
    (своя установка, свой интерпретатор), и остановка цикла публикаций из-за
    этого была бы хуже отсутствия подсказки.
    """
    try:
        from factory.qwen import comments as _комм

        return list((_комм.ожидают_проверки() or {}).get("pending") or [])
    except Exception:  # noqa: BLE001 — слой недоступен: подсказки нет, цикл идёт
        return []


def _work(
    now: dt.datetime,
    *,
    registry: Path,
    leases: Path,
    events: Path,
    candidates: Path,
    state: Path,
    refresh: bool,
    recent: dict[str, int] | None,
) -> dict:
    """Есть ли работа: свободные задания очереди и кандидаты без результата."""
    # Переданные черновики — работа ПЕРВОЙ очереди: текст уже написан и ждёт
    # только решения, а задания очереди и кандидаты — работа, которую ещё надо
    # сделать. Поэтому они проверяются до всего остального и попадают в ответ
    # даже тогда, когда причиной запуска стало другое.
    передано = переданные_черновики()
    if передано:
        первый = передано[0]
        return {
            "run": True,
            "reason": (f"передано черновиков на проверку: {len(передано)} "
                       f"(первый {первый.get('url') or первый.get('slug')})"),
            "handoffs": передано,
            "next": [],
        }

    leased: set[str] = set()
    try:
        raw = json.loads(leases.read_text(encoding="utf-8"))
        rows = raw.get("leases") if isinstance(raw, dict) else raw
        if isinstance(rows, dict):
            rows = [{"task_id": k, **v} for k, v in rows.items()]
        for row in rows or []:
            exp = row.get("expires_at") or row.get("lease_until") or ""
            if exp and dt.datetime.fromisoformat(exp.replace("Z", "+00:00")) > now:
                leased.add(str(row.get("task_id")))
    except (OSError, ValueError):
        pass
    try:
        items = json.loads(registry.read_text(encoding="utf-8")).get("items") or []
    except (OSError, ValueError):
        items = []
    open_tasks = [
        i
        for i in items
        if i.get("target_site") in EDITOR_DOMAINS
        and i.get("target_site") not in PAUSED_PUBLISH
        and i.get("status") == "NEEDS_UPDATE"
        and str(i.get("content_id", "")).replace("request-", "") not in leased
    ]
    from seo_operator import regular

    # Закрытые адреса — по последнему исходу и его сроку (regular.RESULT_HOLD):
    # «источник временно недоступен» больше не закрывает адрес навсегда.
    done = {_key(u) for u in regular.result_holds(events, now)[0]}
    try:
        cands = json.loads(candidates.read_text(encoding="utf-8")).get("candidates") or []
    except (OSError, ValueError):
        cands = []
    fresh = [c for c in cands if _key(c.get("url", "")) not in done
             and _key(c.get("url", "")).split("/")[2:3] != [] and
             _key(c.get("url", "")).split("/")[2] not in PAUSED_PUBLISH]
    # Пересчёт и тогда, когда кандидаты кончились лишь у части каталожных
    # доменов: 2026-10-10 у сайтов Lords/Zona было по 2 кандидата, их закрыли
    # к утру, а список не обновлялся, пока оставались кандидаты Yummy, — за
    # день 52 из 56 публикаций пришлись на Yummy, на Lords ни одной.
    # Пересчёт не чаще раза в час (_refresh_candidates).
    starving = (set(regular.EDITOR_SITES) - set(PAUSED_PUBLISH)
                - {_key(c["url"]).split("/")[2] for c in fresh})
    if (not fresh or starving) and refresh and _refresh_candidates(candidates, now):
        # Пересчёт и при открытых заданиях очереди: 2026-10-09 после 17:35 в
        # очереди Yummy было 245 заданий, и исчерпанный список кандидатов не
        # обновлялся — запуски шли с пустым next.json по остальным доменам.
        return _work(
            now,
            registry=registry,
            leases=leases,
            events=events,
            candidates=candidates,
            state=state,
            refresh=False,
            recent=recent,
        )
    if fresh:
        fresh = rotate(fresh, recent_publications(now) if recent is None else recent)
    if open_tasks:
        # Список кандидатов отдаётся и при свободном задании очереди: запуск
        # 2026-10-09 12:50 закрыл единственное задание и встал (next.json пуст),
        # хотя кандидатов было двадцать — второго материала не было.
        return {
            "run": True,
            "reason": f"свободных заданий на текст: {len(open_tasks)}; кандидатов: {len(fresh)}",
            "next": fresh,
        }
    if fresh:
        return {
            "run": True,
            "reason": f"кандидатов без результата: {len(fresh)} (первый {fresh[0]['url']})",
            "next": fresh,
        }
    if refresh and _refresh_candidates(candidates, now):
        return _work(
            now,
            registry=registry,
            leases=leases,
            events=events,
            candidates=candidates,
            state=state,
            refresh=False,
            recent=recent,
        )
    return {"run": False, "reason": "работы нет: свободных заданий и новых кандидатов нет"}


#: Домены, где публикация ПРИОСТАНОВЛЕНА, с причиной. 2026-10-11 17:10Z
#: (Архитектор): установленный в службу MCP factory/qwen/editorial.py собирает
#: editorial-overrides.json Lords/Zona целиком из своих описаний и затирает
#: чужие поля — прогон 20261011T125537Z стёр редакционное название
#: silsila-badalte-rishton-ka на zonafilm.space (восстановлено заявкой
#: zona-01-edit-5a59f77cae43). Постоянные данные сайта публикация лишь читать
#: вправе; до установки правки «_живые_правки» (ветка Архитектора) редактор на
#: этих доменах не публикует. Снимается удалением строки — после установки.
#: 2026-10-12: правка установлена (editorial-fix-installed.py код 0, служба
#: перезапущена 17:42:04 после правки 17:41:55; editorial-overrides-audit.py код 0;
#: живой <h1> silsila-badalte-rishton-ka = «История наших отношений»). Снимается
#: по шагам: первым zonafilm.space — единственная витрина с чужим ручным полем
#: (name), где защита проверяется делом; остальные шесть — после аудита её
#: первой публикации.
PAUSED_PUBLISH = {
    d: "MCP editorial.py затирает поля editorial-overrides.json (установка правки _живые_правки)"
    for d in ("zonafilm.cc", "zonafilm12.site", "lordfilm47.space",
              "lordserial33.biz", "1lordserials1.online", "lordserials22.info")
}


def allowed_domains() -> list[str]:
    """Домены, на которых редактор публикует: шлюз (EDITOR_DOMAINS) и кандидаты
    (regular.EDITOR_SITES), без приостановленных. Единственный источник для промпта модели."""
    from seo_operator import regular

    return sorted((set(EDITOR_DOMAINS) | set(regular.EDITOR_SITES)) - set(PAUSED_PUBLISH))


def recent_publications(now: dt.datetime, *, hours: int = 24) -> dict[str, int]:
    """Сколько адресов получили публикацию за последние сутки — по доменам (файлы)."""
    from seo_operator import regular

    out: dict[str, int] = {}
    for row in regular.published_since(now - dt.timedelta(hours=hours)):
        domain = row["url"].split("/")[2]
        out[domain] = out.get(domain, 0) + 1
    return out


def rotate(cands: list[dict], recent: dict[str, int]) -> list[dict]:
    """Чередовать домены, начиная с того, где за сутки опубликовано меньше всего.

    Внутри домена порядок прежний (по трафику). Без ротации первым всегда шёл
    домен с большим трафиком, и один домен забирал весь цикл.
    """
    by_domain: dict[str, list[dict]] = {}
    for c in cands:
        by_domain.setdefault(c.get("domain") or c.get("url", "").split("/")[2], []).append(c)
    order = sorted(by_domain, key=lambda d: (recent.get(d, 0), list(by_domain).index(d)))
    out: list[dict] = []
    while any(by_domain.values()):
        for d in order:
            if by_domain[d]:
                out.append(by_domain[d].pop(0))
    return out


def _refresh_candidates(path: Path, now: dt.datetime, *, min_age_s: int = 3600) -> bool:
    """Пересчитать кандидатов, если список исчерпан и старше часа.

    Сеть — только чтение карточек Yummy с поисковым спросом (до 6 на домен):
    у семейства нет снимка каталога, и длину описания видно лишь на странице.
    """
    try:
        age = now.timestamp() - path.stat().st_mtime
    except OSError:
        age = min_age_s + 1
    if age < min_age_s:
        return False
    from seo_operator import regular

    snaps = sorted(regular.SOURCES["analytics_snapshots"].glob("analytics-????-??-??.json"))
    if not snaps:
        return False
    published = {(i["domain"], i["slug"]) for i in regular.published_items()}
    found = regular.editor_candidates(
        snaps[-1],
        regular.SOURCES["facts_snapshots"],
        published,
        blocked=regular.blocked_slugs(regular.SOURCES["queue_events"], now),
    )
    held, net_blocked = regular.result_holds(regular.SOURCES["queue_events"], now)
    # Кандидаты Yummy по спросу дорогие (чтение карточек ~1 мин): переиспользуются
    # из прежнего файла сутки, если адрес всё ещё не закрыт и не опубликован;
    # заново читаются, только когда таких не осталось.
    held_keys = {u.rstrip("/").lower() for u in held}
    taken = {slug for _, slug in published} | net_blocked
    прежние = []
    try:
        старый = json.loads(path.read_text(encoding="utf-8"))
        возраст = now - (
            regular.parse_iso(старый.get("yummy_demand_at")) or now - dt.timedelta(days=2)
        )
        if возраст < dt.timedelta(days=1):
            прежние = [
                c
                for c in старый.get("candidates") or []
                if str(c.get("reason", "")).endswith("_DEMAND")
                and c["url"].rstrip("/").lower() not in held_keys
                and c["slug"] not in taken
            ]
            yummy_at = старый.get("yummy_demand_at")
    except (OSError, ValueError):
        pass
    if not прежние:
        прежние = regular.yummy_demand_candidates(
            snaps[-1], published, blocked=net_blocked, held_urls=held
        )
        yummy_at = regular.iso(now)
    found = прежние + [c for c in found if c["slug"] not in {p["slug"] for p in прежние}]
    regular._write_json(
        path,
        {
            "snapshot": snaps[-1].name,
            "generated_at": regular.iso(now),
            "refreshed_by": "editor-gate",
            "yummy_demand_at": yummy_at,
            "candidates": found,
        },
    )
    return True


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="seo-operator editor-run-verify")
    p.add_argument("--run-id", required=True)
    p.add_argument("--started-at", required=True)
    p.add_argument("--finished-at", required=True)
    p.add_argument("--out")
    a = p.parse_args(argv)
    report = verify(a.run_id, a.started_at, a.finished_at)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if report["complete"] else 2
