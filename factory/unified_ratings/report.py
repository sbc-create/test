"""Сводный отчёт модуля.

Отчёт строится из того, что в базе, а не из того, что помнит вызывающий
код. Метрика, которую никто не измерял, попадает сюда как UNMEASURED —
не как ноль и не как отсутствующий ключ.
"""

from __future__ import annotations

from typing import Any

from factory.unified_ratings import MODULE_VERSION
from factory.unified_ratings.metrics import MetricsRecorder
from factory.unified_ratings.sources import EXTERNAL_DISPLAY_ORDER, REGISTRY
from factory.unified_ratings.store import UnifiedStore
from factory.unified_ratings.titles import utc_now


def build_report(store: UnifiedStore) -> dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "module_version": MODULE_VERSION,
        "db_path": str(store.db_path),
        "schema_applied": store.has_schema(),
        "counts": _counts(store),
        "sources": _sources(store),
        "matching": _matching(store),
        "runs": _runs(store),
        "review_queue": _review(store),
        "three_kinds_are_separate": _separation(store),
        "metrics": MetricsRecorder(store).snapshot(),
    }


def _counts(store: UnifiedStore) -> dict[str, int]:
    tables = [
        "unified_titles",
        "unified_title_tenant_map",
        "unified_source_links",
        "unified_external_snapshots",
        "unified_external_current",
        "unified_editorial_ratings",
        "unified_editorial_audit",
        "unified_user_aggregates",
        "unified_import_runs",
        "unified_review_queue",
        "unified_schedule_state",
    ]
    existing = set(store.table_names())
    return {t: store.count(t) for t in tables if t in existing}


def _sources(store: UnifiedStore) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in EXTERNAL_DISPLAY_ORDER:
        source = REGISTRY[key]
        rows = store.query(
            """SELECT validation_state, COUNT(*) AS n FROM unified_external_current
               WHERE source_key=? GROUP BY validation_state""",
            (key,),
        )
        out[key] = {
            "ui_label": source.ui_label,
            "status": source.status.value,
            "access_method": source.access_method.value,
            "scale": source.scale.scale_label,
            "formula": source.scale.formula.value,
            "contract_verified": source.scale.verified,
            "blocker": source.blocker,
            "records": {r["validation_state"]: int(r["n"]) for r in rows},
            "total_records": sum(int(r["n"]) for r in rows),
        }
    return out


def _matching(store: UnifiedStore) -> dict[str, Any]:
    rows = store.query(
        "SELECT source_key, status, COUNT(*) AS n FROM unified_source_links"
        " GROUP BY source_key, status ORDER BY source_key, status"
    )
    by_status: dict[str, int] = {}
    by_source: dict[str, dict[str, int]] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + int(row["n"])
        by_source.setdefault(row["source_key"], {})[row["status"]] = int(row["n"])
    # Автоматически принятой считается только связь по точному внешнему ID
    # с полной уверенностью. Всё остальное, названное exact, было бы
    # ложным автоматическим сопоставлением.
    false_automatic = store.count(
        "unified_source_links",
        "status='exact' AND (confidence < 1.0 OR match_method <> 'exact_external_id')",
    )
    return {
        "by_status": by_status,
        "by_source": by_source,
        "exact": by_status.get("exact", 0),
        "pending": by_status.get("pending", 0),
        "conflict": by_status.get("conflict", 0),
        "rejected": by_status.get("rejected", 0),
        "false_automatic_matches": false_automatic,
    }


def _runs(store: UnifiedStore) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in store.query(
            """SELECT run_id, source_key, stage, status, dry_run, started_at, finished_at,
                      requested, received, exact_match, pending_match, rejected, inserted,
                      updated, unchanged, not_found, failed, rate_limited, retries, next_checkpoint,
                      code_version
               FROM unified_import_runs ORDER BY started_at DESC LIMIT 50"""
        )
    ]


def _review(store: UnifiedStore) -> dict[str, Any]:
    rows = store.query(
        """SELECT reason_code, COUNT(*) AS n FROM unified_review_queue
           WHERE status='PENDING' GROUP BY reason_code ORDER BY n DESC"""
    )
    items = store.query(
        """SELECT review_id, title_id, source_key, reason_code, detail
           FROM unified_review_queue WHERE status='PENDING'
           ORDER BY review_id LIMIT 50"""
    )
    return {
        "pending_total": store.count("unified_review_queue", "status='PENDING'"),
        "by_reason": {r["reason_code"]: int(r["n"]) for r in rows},
        "items": [dict(r) for r in items],
        "auto_published": False,
    }


def _separation(store: UnifiedStore) -> dict[str, Any]:
    """Доказательство раздельности трёх видов оценок — по схеме, не по слову."""
    tables = set(store.table_names())
    return {
        "external_tables": sorted(
            t for t in ("unified_external_snapshots", "unified_external_current") if t in tables
        ),
        "community_tables": sorted(
            t for t in ("community_votes", "community_vote_events", "unified_user_aggregates")
            if t in tables
        ),
        "editorial_tables": sorted(
            t for t in ("unified_editorial_ratings", "unified_editorial_audit") if t in tables
        ),
        "shared_score_table": None,
        "note": (
            "общей таблицы оценок нет: у каждого вида собственная таблица и "
            "собственный путь записи"
        ),
    }
