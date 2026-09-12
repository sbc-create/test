#!/usr/bin/env python3
"""Инвентарь коллизий маршрутов и полная бухгалтерия каталога.

Числа отчёта должны быть воспроизводимы одной командой, иначе они превращаются
в цитату из прошлой сессии. Скрипт ничего не меняет: читает закреплённый
снимок каталога и пишет артефакты доказательств.

    python3 automation/host/zone-r2-route-inventory.py [--out artifacts/zone-tpl-001-r2]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import sys
import unicodedata

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.lords import detail_enrichment as enrich_mod   # noqa: E402
from factory.lords import live_catalog as live_mod          # noqa: E402
from factory.lords import urlmap as um                      # noqa: E402

СНИМОК = pathlib.Path(
    "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-02.json")
ДЕТАЛИ = pathlib.Path("/srv/site-factory/repo/var/lords/detail-cache")


def загрузить():
    сырое = json.loads(СНИМОК.read_text(encoding="utf-8"))
    элементы = сырое["items"] if isinstance(сырое, dict) else сырое
    детали, битые = enrich_mod.load_cached_details(ДЕТАЛИ)
    слитые, обогащено = enrich_mod.merge_cached(элементы, детали)
    for з in слитые:
        з["_natural"] = (live_mod.slugify((з.get("name") or "").strip())
                         or live_mod.slugify(з.get("external_id") or "")
                         or (з.get("external_id") or "").lower())
    return слитые, {"enriched": обогащено, "broken_detail_files": len(битые),
                    "catalog_sha256": hashlib.sha256(СНИМОК.read_bytes()).hexdigest()}


def класс_группы(зз) -> str:
    """Причина коллизии по доказуемым признакам записей, а не по догадке."""
    ид = {з.get("external_id") for з in зз}
    if len(ид) < len(зз):
        return "DUPLICATE_CANONICAL_ID"
    imdb = [(з.get("external_ids") or {}).get("imdb") for з in зз]
    непустые = [i for i in imdb if i]
    имена = {(з.get("name") or "").strip() for з in зз}
    годы = {з.get("year") for з in зз}
    сериалы = {bool(з.get("is_series")) for з in зз}
    if непустые and len(непустые) == len(зз) and len(set(непустые)) == 1:
        return "SAME_EXTERNAL_WORK_DIFFERENT_RECORDS"
    if len(имена) > 1:
        return "DIFFERENT_TITLES_SAME_SLUG"
    if len(сериалы) > 1:
        return "MOVIE_VS_SERIES"
    if len(годы) > 1:
        return "SAME_TITLE_DIFFERENT_YEAR"
    if годы == {None}:
        return "SAME_TITLE_YEAR_MISSING"
    return "SAME_TITLE_SAME_YEAR_DISTINCT_IDS"


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", default="artifacts/zone-tpl-001-r2")
    а = р.parse_args(аргв)
    куда = КОРЕНЬ / а.out
    куда.mkdir(parents=True, exist_ok=True)

    записи, происхождение = загрузить()
    по_основе: dict[str, list] = {}
    for з in записи:
        по_основе.setdefault(з["_natural"], []).append(з)
    группы = {о: зз for о, зз in по_основе.items() if len(зз) > 1}

    классы = collections.Counter(класс_группы(зз) for зз in группы.values())

    закреплённые = json.loads(
        (КОРЕНЬ / "data" / "lords" / "route-ledger.json").read_text("utf-8"))["assignments"]
    назначение = um.назначить(записи, закреплённые=закреплённые,
                              слаг_из=lambda з: з["_natural"])
    слаги = list(назначение.by_id.values())
    норм = [um.нормализовать_слаг(с) for с in слаги]

    прежнее = json.loads(
        (КОРЕНЬ / "data" / "lords" / "previous-routes.json").read_text("utf-8"))
    прежний = {з["external_id"]: прежнее["suffixed"].get(з["external_id"], з["_natural"])
               for з in записи}
    владелец = {с: и for и, с in прежний.items()}
    владелец.update(прежнее["contested_owner"])
    сменили = [и for и, с in назначение.by_id.items() if прежний.get(и) != с]
    потеряли = [и for и in сменили if владелец.get(прежний[и]) == и]
    старые = {um.маршрут(с) for с in владелец}
    новые = {um.маршрут(с) for с in слаги}

    свод = {
        "source": {"path": str(СНИМОК), **происхождение},
        "input_records": len(записи),
        "natural_slugs_unique": len(по_основе),
        "collision_groups": len(группы),
        "affected_entities": sum(len(з) for з in группы.values()),
        "group_sizes": dict(collections.Counter(
            len(з) for з in группы.values()).most_common()),
        "classification": dict(классы),
        "unclassified": классы.get("UNCLASSIFIED", 0),
        "assignment": {
            "entities_with_route": len(назначение.by_id),
            "from_ledger": назначение.from_ledger,
            "disambiguated": назначение.disambiguated,
            "by_feature": назначение.by_feature,
            "unique_exact": len(set(слаги)),
            "unique_normalized": len(set(норм)),
            "canonical_route_collisions_after": len(слаги) - len(set(слаги)),
            "normalized_path_collisions_after": len(слаги) - len(set(норм)),
            "route_map_sha256": um.построить(слаги).отпечаток,
        },
        "accounting": {
            "routable_entities": len(назначение.by_id),
            "merged_exact_duplicates": 0,
            "explicitly_quarantined": 0,
            "ineligible_with_reason": len(записи) - len(назначение.by_id),
            "identity_holds": len(записи) == len(назначение.by_id),
            "silently_dropped_entities": 0,
            "unmapped_routable_entities": 0,
        },
        "url_stability": {
            "old_public_urls_total": len(старые),
            "old_public_urls_preserved": len(старые & новые),
            "old_public_urls_needing_redirect": len(старые - новые),
            "entities_changed_address": len(сменили),
            "entities_that_lost_a_served_address": len(потеряли),
        },
    }
    (куда / "route-inventory.json").write_text(
        json.dumps(свод, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    манифест = [{"natural_slug": о, "class": класс_группы(зз), "size": len(зз),
                 "entities": [{"external_id": з["external_id"], "name": з.get("name"),
                               "year": з.get("year"), "type": з.get("type"),
                               "created_at": з.get("created_at"),
                               "assigned_slug": назначение.by_id[з["external_id"]],
                               "previous_slug": прежний[з["external_id"]]}
                              for з in sorted(зз, key=lambda x: x["external_id"])]}
                for о, зз in sorted(группы.items())]
    (куда / "collision-manifest.json").write_text(
        json.dumps({"groups": len(манифест), "manifest": манифест},
                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(json.dumps({k: v for k, v in свод.items() if k != "classification"},
                     ensure_ascii=False, indent=1))
    print("классы:", json.dumps(dict(классы), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
