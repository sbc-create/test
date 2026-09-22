"""Проекция единого модуля оценок для витрины.

Витрина не ходит в базу оценок: она читает подготовленный файл проекции.
Так у неё нет ни соединения с БД, ни возможности заблокировать её запись,
ни зависимости от доступности модуля — если проекции нет, страница
просто рендерится без блока оценок.

Проекция отдаёт то, что можно показать, и ровно в том виде, в каком это
разрешено показывать:

* внешние оценки — каждая отдельной строкой со своим источником;
* сводная оценка — только при двух и более источниках;
* оценка зрителей площадки — отдельно от внешних;
* редакционная оценка — отдельно от обеих.

Спорные сопоставления в проекцию не попадают вовсе: если связь ждёт
ручной проверки, показывать нечего.

Когорта канарейки задаётся списком идентификаторов. Пустой список — это
«никому», а не «всем»: раскатка по умолчанию не включается.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.unified_ratings import MODULE_VERSION
from factory.unified_ratings.composite import compute as compute_composite
from factory.unified_ratings.editorial import EditorialRatings
from factory.unified_ratings.scale import ScoreState
from factory.unified_ratings.sources import EXTERNAL_DISPLAY_ORDER, REGISTRY
from factory.unified_ratings.store import UnifiedStore

SCHEMA = "unified.ratings.projection/1.0.0"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_projection(
    store: UnifiedStore,
    *,
    space: str,
    title_ids: set[str],
    cohort: set[str] | None = None,
    include_community: bool = True,
) -> dict[str, Any]:
    """Собрать проекцию для площадки.

    ``cohort`` — подмножество произведений, которым разрешено показывать
    блок. ``None`` означает «вся выборка», пустое множество — «никому».
    """
    editorial = EditorialRatings(store)
    selected = title_ids if cohort is None else (title_ids & cohort)

    titles: dict[str, Any] = {}
    stats = {
        "titles_in_projection": 0,
        "with_external": 0,
        "with_composite": 0,
        "with_community": 0,
        "with_editorial": 0,
        "skipped_no_data": 0,
    }

    ambiguous_by_title: dict[str, set[str]] = {}
    for row in store.query(
        "SELECT title_id, source_key FROM unified_source_links"
        " WHERE status IN ('pending','conflict','rejected')"
    ):
        ambiguous_by_title.setdefault(row["title_id"], set()).add(row["source_key"])

    current: dict[str, list[Any]] = {}
    for row in store.query(
        "SELECT * FROM unified_external_current WHERE validation_state=?", (ScoreState.OK.value,)
    ):
        current.setdefault(row["title_id"], []).append(row)

    aggregates = {
        r["title_id"]: r
        for r in store.query(
            "SELECT * FROM unified_user_aggregates WHERE scope_kind='tenant' AND scope_id=?",
            (space,),
        )
    }

    for title_id in sorted(selected):
        bare = title_id.split(":", 1)[-1]
        ambiguous = ambiguous_by_title.get(title_id, set())
        external: list[dict[str, Any]] = []
        for row in current.get(title_id, []):
            source_key = row["source_key"]
            if source_key in ambiguous:
                continue
            source = REGISTRY.get(source_key)
            if source is None:
                continue
            external.append(
                {
                    "source": source_key,
                    "label": source.ui_label,
                    "score": row["normalized_score"],
                    "raw_value": row["raw_score"],
                    "native_scale": f"0–{row['source_scale_max']}",
                    "votes": row["vote_count"],
                    "users": row["user_count"],
                    "url": row["provenance_url"],
                    "fetched_at": row["fetched_at"],
                }
            )
        external.sort(key=lambda e: EXTERNAL_DISPLAY_ORDER.index(e["source"]))

        composite = compute_composite(store, title_id=title_id)
        aggregate = aggregates.get(title_id)
        editorial_rating = editorial.effective(title_id=title_id, tenant_id=space)

        native = None
        if include_community and aggregate is not None and int(aggregate["vote_count"]) > 0:
            native = {
                "average": aggregate["average_score"],
                "votes": int(aggregate["vote_count"]),
                "distribution": json.loads(aggregate["distribution_json"] or "{}"),
                "label": "Оценка зрителей",
                "scale": "1-10",
            }

        if not external and native is None and editorial_rating is None:
            stats["skipped_no_data"] += 1
            continue

        entry: dict[str, Any] = {"external": external}
        if composite.state == "OK":
            entry["composite"] = {
                "label": composite.as_dict()["display_name"],
                "value": composite.value,
                "source_count": composite.source_count,
                "sources": [c.source_key for c in composite.sources_used],
                "formula_version": composite.formula_version,
                "confidence": composite.confidence,
            }
            stats["with_composite"] += 1
        if native is not None:
            entry["native"] = native
            stats["with_community"] += 1
        if editorial_rating is not None:
            entry["editorial"] = {
                "label": "Наша оценка",
                "value": editorial_rating.score,
                "scale": "1-10",
            }
            stats["with_editorial"] += 1
        if external:
            stats["with_external"] += 1

        # Витрина знает произведение по «голому» идентификатору; кладём
        # оба написания, чтобы адаптеру не пришлось угадывать.
        titles[bare] = {space: entry}
        titles[title_id] = {space: entry}
        stats["titles_in_projection"] += 1

    return {
        "schema": SCHEMA,
        "module_version": MODULE_VERSION,
        "space": space,
        "built_at": _now(),
        "cohort_size": len(selected),
        "catalog_size": len(title_ids),
        "stats": stats,
        # Показ включается флагом, а не наличием файла: проекция может
        # существовать задолго до решения её показать.
        "public_read_enabled": False,
        "public_write_enabled": False,
        "titles": titles,
    }


def write_projection(projection: dict[str, Any], path: Path | str) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(projection, ensure_ascii=False, sort_keys=True, indent=1)
    path.write_text(blob + "\n", encoding="utf-8")
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "titles": projection["stats"]["titles_in_projection"],
    }


def build_flags(
    *,
    space: str,
    cohort: set[str],
    public_read: bool,
    public_write: bool,
    kill_switch: bool = False,
) -> dict[str, Any]:
    """Флаги показа. Запись зрителей по умолчанию выключена."""
    return {
        "schema": "unified.ratings.flags/1.0.0",
        "built_at": _now(),
        "space": space,
        f"RATINGS_PUBLIC_READ_{space.upper()}": 1 if public_read else 0,
        f"RATINGS_PUBLIC_WRITE_{space.upper()}": 1 if public_write else 0,
        "PUBLIC_WRITE_ROLLOUT_PERCENT": 0,
        "KILL_SWITCH": 1 if kill_switch else 0,
        # Пустой список — никому. Отсутствие когорты не означает «всем»:
        # раскатка включается решением, а не забытым полем.
        "allowlist": {space: sorted(cohort)},
        "owner_test_access_only": not public_write,
    }
