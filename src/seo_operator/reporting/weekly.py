"""Недельный обзор портфеля: перебалансировка возможностей и ревизия экспериментов."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..experiments.registry import ExperimentRegistry
from ..state import Store


def render(store: Store, registry: ExperimentRegistry, today: date | None = None) -> str:
    today = today or date.today()
    since = (today - timedelta(days=7)).isoformat()

    lines = [f"# Недельный обзор портфеля — {today.isoformat()}", ""]

    for status in ("running", "observing", "kept", "rolled_back", "inconclusive", "frozen"):
        exps = registry.by_status(status)
        if exps:
            lines.append(f"- **{status}**: {len(exps)} — {', '.join(e.id for e in exps[:6])}")
    lines.append("")

    incidents = store.open_incidents()
    lines.append(f"## Открытые инциденты: {len(incidents)}")
    for inc in incidents:
        lines.append(f"- `{inc['id']}` {inc['site_id']} / {inc['condition_id']} — {inc['detail']}")
    lines.append("")

    quarantined = store.quarantined_jobs()
    lines.append(f"## Джобы в карантине: {len(quarantined)}")
    for job in quarantined[:10]:
        lines.append(f"- `{job['job_key']}` ({job['kind']}) — {(job['last_error'] or '')[:160]}")
    lines.append("")

    blockers = store.unreported_blockers()
    lines.append(f"## Блокеры, ожидающие решения: {len(blockers)}")
    for b in blockers:
        lines.append(f"- {b['kind']}: {b['detail']}")

    return "\n".join(lines)
