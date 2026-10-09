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
import html
import json
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
                    store = json.loads(
                        (site_dir / "title-overlays.json").read_text(encoding="utf-8")
                    )
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
    }


REGISTRY = Path("/var/lib/seo-content-operator/registry.json")
LEASES = Path("/var/lib/seo-content-operator/editorial_leases.json")
STATE = Path(__file__).resolve().parents[1] / "var" / "editor-runs"
CANDIDATES = Path(__file__).resolve().parents[1] / "var" / "seo-regular" / "editor-candidates.json"
ANIMEDIA = ("animedia.icu", "animedia.space")
#: Где редактор публикует с подтверждённым показом (regular.EDITOR_SITES).
EDITOR_DOMAINS = (*ANIMEDIA, "zonafilm.space", "lordfilm47.space", "lordserial33.biz")
#: Модель запускается не чаще раза в этот интервал (почасовой цикл).
MIN_INTERVAL_S = 55 * 60


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
) -> dict:
    """Нужен ли запуск модели. Только чтение файлов: ни модели, ни сети.

    Запуск нужен, если (1) с начала прошлого запуска модели прошло не меньше
    55 минут и (2) есть работа: свободное задание Animedia на текст в очереди
    или кандидат, по адресу которого ещё не было результата.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    last = None
    log = state / "runs.jsonl"
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("model_started"):
                last = r.get("started_at")
    if last:
        started = dt.datetime.fromisoformat(last.replace("Z", "+00:00"))
        wait = MIN_INTERVAL_S - (now - started).total_seconds()
        if wait > 0:
            return {
                "run": False,
                "reason": f"почасовой цикл: до следующего запуска {int(wait // 60)} мин",
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
        and i.get("status") == "NEEDS_UPDATE"
        and str(i.get("content_id", "")).replace("request-", "") not in leased
    ]
    if open_tasks:
        return {"run": True, "reason": f"свободных заданий на текст: {len(open_tasks)}"}
    done: set[str] = set()
    task_url: dict[str, str] = {}
    if events.is_file():
        for line in events.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("canonical_url") and e.get("task_id"):
                task_url[e["task_id"]] = _key(e["canonical_url"])
            if e.get("event") == "task_result" and e.get("task_id") in task_url:
                done.add(task_url[e["task_id"]])
    try:
        cands = json.loads(candidates.read_text(encoding="utf-8")).get("candidates") or []
    except (OSError, ValueError):
        cands = []
    fresh = [c for c in cands if _key(c.get("url", "")) not in done]
    if fresh:
        fresh = rotate(fresh, recent_publications(now) if recent is None else recent)
    if fresh:
        return {
            "run": True,
            "reason": f"кандидатов без результата: {len(fresh)} (первый {fresh[0]['url']})",
            "next": fresh,
        }
    if refresh and _refresh_candidates(candidates, now):
        return gate(
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
    """Пересчитать кандидатов, если список исчерпан и старше часа. Без сети."""
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
    found = regular.editor_candidates(snaps[-1], regular.SOURCES["facts_snapshots"], published)
    regular._write_json(
        path,
        {
            "snapshot": snaps[-1].name,
            "generated_at": regular.iso(now),
            "refreshed_by": "editor-gate",
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
