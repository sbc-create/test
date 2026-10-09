"""Реестр покрытия редактора: где редактор РАБОТАЕТ, а где сайт только наблюдается.

Источник списка сайтов — реестр фабрики (`factory.qwen.registry.собрать`, без
опроса сети); остальное — уже собранные данные суточного прогона: проверка
доступности, проверки видимости опубликованных текстов, очередь, аналитика.
Ничего не пишет и в сеть не ходит.

Сайт считается подключённым только после публикации, видимость которой
подтверждена на публичной странице (вердикт VISIBLE проверки публикаций).
Записанная, но не видимая публикация — блокер, а не успех.

Блокеры, которые из данных не выводятся (падение моста, несовместимая схема
хранилища), перечисляются в `config/editor-coverage-blockers.json` с
доказательством; запись без доказательства не принимается.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

MSK = dt.timezone(dt.timedelta(hours=3))

WORKING = "работает"
CONNECTED_NOW = "подключён сейчас"
NO_TASKS = "нет подходящих заданий"
BLOCKED = "заблокирован"
NOT_CONNECTED = "не подключён"

#: Открытые задания очереди, которые редактор может взять.
OPEN_QUEUE = {"NEEDS_UPDATE", "NEEDS_TEXT", "DRAFT"}


def _is_test(domain: str) -> bool:
    return domain.endswith((".localhost", ".test")) or domain == "localhost"


def load_sites() -> list[dict]:
    """Сайты из реестра фабрики: домен, семейство, операции моста."""
    from factory.qwen import registry

    return [
        {
            "domain": s.domain,
            "site_id": s.site_id,
            "family": s.adapter or s.template_family,
            "operations": list(s.operations),
        }
        for s in registry.собрать(опрашивать_сеть=False)
    ]


def load_blockers(path: Path) -> dict[str, dict]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for domain, b in (raw.get("blockers") or {}).items():
        if b.get("blocker") and b.get("evidence"):
            out[domain] = b
    return out


def _queue_open(queue_items: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in queue_items:
        url = str(it.get("canonical_url") or "")
        host = url.split("/")[2] if url.count("/") >= 2 else ""
        if host and it.get("status") in OPEN_QUEUE:
            out[host] = out.get(host, 0) + 1
    return out


def build(
    sites: list[dict],
    *,
    availability: list[dict],
    published: list[dict],
    verdicts: dict[str, dict],
    queue_items: list[dict],
    candidates: list[dict],
    analytics_props: list[dict],
    blockers: dict[str, dict],
    cells: dict[str, str],
    now: dt.datetime,
) -> list[dict]:
    avail = {a.get("domain"): a for a in availability}
    monitored = {
        p.get("domain"): p
        for p in analytics_props
        if p.get("analytics_enabled") and p.get("counter_id")
    }
    open_tasks = _queue_open(queue_items)
    cand = {}
    for c in candidates:
        cand[c.get("domain")] = cand.get(c.get("domain"), 0) + 1
    today = now.astimezone(MSK).date().isoformat()

    rows = []
    for s in sorted(sites, key=lambda x: x["domain"]):
        domain = s["domain"]
        if _is_test(domain):
            continue
        ops = set(s.get("operations") or [])
        items = [p for p in published if p.get("domain") == domain]

        def verdict(p: dict) -> str | None:
            # Вердикт относится к тексту, который проверяли: после правки он не действует.
            v = verdicts.get(p["url"]) or {}
            return v.get("verdict") if v.get("digest") == p.get("digest") else None

        visible = [p for p in items if verdict(p) == "VISIBLE"]
        invisible = [p for p in items if verdict(p) not in (None, "VISIBLE")]
        unchecked = [p for p in items if verdict(p) is None]
        last = max(
            (p for p in visible if p.get("published_at")),
            key=lambda p: p["published_at"],
            default=None,
        )
        first_visible = min(
            (p["published_at"] for p in visible if p.get("published_at")), default=""
        )
        a = avail.get(domain) or {}
        issues = [i.get("code") for i in a.get("issues") or []]
        reachable = a.get("home_status") == 200 and "DNS_UNRESOLVED" not in issues

        if not a:
            status, reason = BLOCKED, "доступность не проверялась"
        elif not reachable:
            status, reason = (
                BLOCKED,
                "сайт недоступен: " + (", ".join(issues) or f"HTTP {a.get('home_status')}"),
            )
        elif domain in blockers:
            status, reason = BLOCKED, blockers[domain]["blocker"]
        elif visible:
            first_day = (
                dt.datetime.fromisoformat(first_visible.replace("Z", "+00:00"))
                .astimezone(MSK)
                .date()
                .isoformat()
                if first_visible
                else ""
            )
            status, reason = (CONNECTED_NOW if first_day == today else WORKING), ""
        elif "publish" not in ops:
            status, reason = BLOCKED, "у моста нет операции публикации для сайта"
        elif invisible:
            status, reason = BLOCKED, "публикация записана, на странице не видна"
        elif not open_tasks.get(domain) and not cand.get(domain):
            status, reason = NO_TASKS, ""
        else:
            status, reason = NOT_CONNECTED, "видимой публикации ещё не было"

        rows.append(
            {
                "domain": domain,
                "site_id": s.get("site_id"),
                "family": s.get("family"),
                "cell_status": cells.get(domain, ""),
                "reachable": reachable if a else None,
                "home_status": a.get("home_status"),
                "issues": issues,
                "monitored": domain in monitored,
                "can": {
                    "task": True,
                    "facts": "facts" in ops,
                    "save": "prepare" in ops,
                    "publish": "publish" in ops,
                    "verify_display": "publish" in ops,
                },
                "texts_in_store": len(items),
                "visible": len(visible),
                "not_visible": len(invisible),
                "unchecked": len(unchecked),
                "last_visible": (
                    {"url": last["url"], "published_at": last["published_at"]} if last else None
                ),
                "open_tasks": open_tasks.get(domain, 0),
                "candidates": cand.get(domain, 0),
                "status": status,
                "blocker": reason,
                "blocker_evidence": (blockers.get(domain) or {}).get("evidence", ""),
            }
        )
    return rows


def render(rows: list[dict]) -> list[str]:
    """Таблица для суточного отчёта."""
    lines = [
        "| домен | статус | видимых текстов | последняя видимая | блокер |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        last = r["last_visible"]
        lines.append(
            f"| {r['domain']} | {r['status']} | {r['visible']}"
            + (f" (+{r['not_visible']} не видны)" if r["not_visible"] else "")
            + f" | {(last['url'] + ' ' + last['published_at']) if last else '—'}"
            + f" | {r['blocker'] or '—'}"
            + (f" ({r['blocker_evidence']})" if r["blocker_evidence"] else "")
            + " |"
        )
    working = sum(r["status"] in (WORKING, CONNECTED_NOW) for r in rows)
    lines.append("")
    lines.append(
        f"Редактор работает на {working} из {len(rows)} доменов; наблюдаются аналитикой — "
        f"{sum(r['monitored'] for r in rows)}. «Наблюдается» не означает «редактор работает»."
    )
    return lines


def summary(rows: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for r in rows:
        out.setdefault(r["status"], []).append(r["domain"])
    return out
