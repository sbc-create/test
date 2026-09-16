#!/usr/bin/env python3
"""Применение ContentIdentity в ИЗОЛИРОВАННОЙ базе.

Ни production-БД, ни Redis, ни CMS здесь не участвуют. База создаётся заново
по указанному пути; если файл уже есть, он используется как есть — это нужно
для проверки повторного прогона, а не для дозаписи в чужое хранилище.

Сценарий делает то, что задача называет этапом 7: пересчитывает идентичность,
сравнивает тип до и после, собирает SeoDescriptor и проверяет инварианты
потребителя — UNKNOWN не выпускает разметку, у фильма нет сезонов, сериал не
размечается как фильм, OVA/ONA/Special не становятся фильмом.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from factory.site_engine.content_kind import (  # noqa: E402
    ALIASES,
    ContentKind,
    contract_for,
    normalise_alias,
)

sys.argv_backup = list(sys.argv)
реестр_путь = REPO / "automation/host/content-identity-registry.py"
spec = importlib.util.spec_from_file_location("registry", реестр_путь)
registry = importlib.util.module_from_spec(spec)
sys.argv = ["registry"]
spec.loader.exec_module(registry)
sys.argv = sys.argv_backup

миграция_путь = REPO / "migrations/0001_content_identity.py"
spec_m = importlib.util.spec_from_file_location("m0001", миграция_путь)
migration = importlib.util.module_from_spec(spec_m)
spec_m.loader.exec_module(migration)


def seo_descriptor(identity) -> dict:
    """То, что уходит потребителю. Неизвестное поле не сериализуется.

    Пустое поле разметки — это утверждение «мы знаем, и там ничего», тогда как
    известно обратное. Поэтому ключ отсутствует, а не равен пустой строке.
    """
    к = contract_for(identity.content_kind)
    d: dict = {
        "internalEntityId": identity.internal_entity_id,
        "contentKind": identity.content_kind.value,
        "allowsSeasons": к.allows_seasons,
        "allowsEpisodes": к.allows_episodes,
    }
    if к.schema_type:
        d["schemaType"] = к.schema_type
    if к.og_type:
        d["ogType"] = к.og_type
    if к.visible_type:
        d["visibleType"] = к.visible_type
    if к.about_heading:
        d["aboutHeading"] = к.about_heading
    if identity.displayed_title:
        d["name"] = identity.displayed_title
    if identity.release_year is not None:
        d["releaseYear"] = identity.release_year
    if identity.duration is not None:
        d["duration"] = f"PT{identity.duration}M"
    if identity.is_animation is not None:
        d["isAnimation"] = identity.is_animation
    return d


ИНВАРИАНТЫ = (
    (
        "UNKNOWN не выпускает разметку",
        lambda i, d: not (i.content_kind is ContentKind.UNKNOWN and "schemaType" in d),
    ),
    (
        "у фильма нет сезонов и серий",
        lambda i, d: not (
            i.content_kind is ContentKind.MOVIE and (d["allowsSeasons"] or d["allowsEpisodes"])
        ),
    ),
    (
        "сериал не размечается как Movie",
        lambda i, d: not (i.content_kind is ContentKind.SERIES and d.get("schemaType") == "Movie"),
    ),
    (
        "OVA, ONA и Special не становятся фильмом",
        lambda i, d: not (
            i.content_kind in (ContentKind.OVA, ContentKind.ONA, ContentKind.SPECIAL)
            and d.get("schemaType") == "Movie"
        ),
    ),
    ("длительность не выпускается нулевой", lambda i, d: d.get("duration") not in ("PT0M", "PT0S")),
    ("пустых полей разметки нет", lambda i, d: all(v != "" for v in d.values())),
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default=str(REPO / "var/lords/lords/catalog-cache"))
    p.add_argument("--db", required=True, help="ИЗОЛИРОВАННАЯ база; production запрещён")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--out", default="")
    a = p.parse_args()

    путь = Path(a.db)
    if any(часть in str(путь) for часть in ("/srv/sites/", "/var/lib/postgresql")):
        print("ОТКАЗ: путь ведёт в боевое хранилище", file=sys.stderr)
        return 2
    путь.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(путь)
    migration.upgrade(conn)

    записи = list(registry.читать_каталог(Path(a.catalog)))
    if a.limit:
        записи = записи[: a.limit]

    до = collections.Counter()
    после = collections.Counter()
    переходы = collections.Counter()
    нарушения: list[str] = []
    дескрипторы = 0

    for site, запись, снят in записи:
        # «До» — единственное, что умел выдать каталог: двоичный тип
        # поставщика. Своего contentKind ядро не отдавало вовсе.
        прежний = ALIASES.get(normalise_alias(str(запись.get("type") or "")), ContentKind.UNKNOWN)
        identity, _ = registry.построить(запись, site, снят)
        до[прежний.value] += 1
        после[identity.content_kind.value] += 1
        if прежний is not identity.content_kind:
            переходы[f"{прежний.value} → {identity.content_kind.value}"] += 1

        migration.upsert_identity(conn, identity)
        d = seo_descriptor(identity)
        дескрипторы += 1
        for имя, проверка in ИНВАРИАНТЫ:
            if not проверка(identity, d):
                нарушения.append(f"{identity.internal_entity_id}: {имя}")
    conn.commit()

    строк = conn.execute("SELECT COUNT(*) FROM content_identity").fetchone()[0]
    итог = {
        "records": len(записи),
        "rowsInIsolatedDb": строк,
        "kindBefore": dict(до),
        "kindAfter": dict(после),
        "transitions": dict(переходы),
        "descriptorsGenerated": дескрипторы,
        "invariantViolations": нарушения[:20],
        "invariantViolationCount": len(нарушения),
    }
    print(json.dumps(итог, ensure_ascii=False, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    conn.close()
    return 1 if нарушения else 0


if __name__ == "__main__":
    raise SystemExit(main())
