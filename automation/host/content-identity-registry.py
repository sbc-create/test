#!/usr/bin/env python3
"""Реестр проблемных записей и разрешение их идентичности.

Числа берутся из каталога и артефактов аудита, а не переписываются из
задания. Каталог читается из файлов кэша — это данные Core, не production-сайт;
ни одного обращения на запись здесь нет и быть не может.

Выдаёт полный набор отчётов задачи: реестр без типа, конфликты типов, итоги
разрешения идентичности и состояние рейтингов.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from factory.site_engine import catalog_identity, rating_discovery  # noqa: E402
from factory.site_engine.content_identity import (  # noqa: E402
    ContentIdentity,
    IdentityStatus,
    MappingMethod,
    SourceRef,
    stamp,
)
from factory.site_engine.content_kind import ContentKind  # noqa: E402
from factory.site_engine.identity_resolver import RESOLVER_VERSION  # noqa: E402
from factory.site_engine.title_normalize import варианты  # noqa: E402

#: Источники рейтинга: настроенных нет. Перечень «технически подходящих»
#: приведён, чтобы блокер называл конкретную недостачу, а не «нет данных».
POLICY = rating_discovery.SourcePolicy(
    configured=(),
    known_unlicensed=("tmdb", "imdb", "mal", "anilist", "kinopoisk"),
    license_policy_version="none-configured/2026-09-05",
)

СЕЙЧАС = dt.datetime.now(dt.timezone.utc)


def читать_каталог(каталог: Path):
    """Записи по витринам. Один и тот же тайтл на трёх витринах — три строки."""
    for файл in sorted(glob.glob(str(каталог / "*.json"))):
        site = Path(файл).stem
        данные = json.loads(Path(файл).read_text(encoding="utf-8"))
        снят = dt.datetime.utcfromtimestamp(os.path.getmtime(файл)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for запись in данные.get("items") or []:
            if isinstance(запись, dict):
                yield site, запись, снят


def построить(запись: dict, site: str, снят: str):
    """ContentIdentity по одной записи каталога плюс решение о виде."""
    решение = catalog_identity.decide(
        provider_type=запись.get("type"), tags=запись.get("tags") or ()
    )
    название = запись.get("name") or ""
    внешние = {k: str(v) for k, v in (запись.get("external_ids") or {}).items() if v}

    # Длительность каталог не отдаёт. None, а не ноль: ноль ушёл бы в разметку
    # как PT0M, то есть утверждением «идёт нисколько».
    длительность = запись.get("duration")
    длительность = int(длительность) if isinstance(длительность, int) and длительность > 0 else None

    identity = ContentIdentity(
        internal_entity_id=f"{site}:{запись.get('external_id')}",
        provider_asset_id=str(запись.get("external_id") or ""),
        content_kind=решение.kind,
        is_animation=решение.is_animation,
        displayed_title=название,
        original_title="",
        alternative_titles=(),
        release_year=запись.get("year") if isinstance(запись.get("year"), int) else None,
        release_date="",
        country="",
        language="",
        duration=длительность,
        episode_count=None,
        season_number=None,
        external_ids=внешние,
        source_refs=(
            SourceRef(
                source="cdnvideohub-catalog-cache",
                source_entity_id=str(запись.get("external_id") or ""),
                requested_at=снят,
                source_updated_at=str(запись.get("updated_at") or ""),
                cache_status="cached",
                license_policy_version=POLICY.license_policy_version,
                attribution="CDNVideoHub Content API",
            ),
        ),
    )

    # Статус идентичности. Внешний идентификатор поставщика — точный и
    # подтверждённый: он и есть ключ записи у источника.
    if решение.conflicted:
        identity.identity_status = IdentityStatus.CONFLICTED
        identity.mapping_method = MappingMethod.NONE
        identity.conflict_state = решение.conflicts
        identity.mapping_confidence = 0.0
    elif решение.kind is ContentKind.UNKNOWN:
        identity.identity_status = IdentityStatus.NEEDS_SOURCE
        identity.mapping_method = MappingMethod.NONE
    else:
        identity.identity_status = IdentityStatus.RESOLVED_EXACT_ID
        identity.mapping_method = MappingMethod.CATALOG_INTRINSIC
        identity.mapping_confidence = решение.confidence
    stamp(identity, resolver_version=RESOLVER_VERSION, now=СЕЙЧАС)
    return identity, решение


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default=str(REPO / "var/lords/lords/catalog-cache"))
    p.add_argument("--audit", default="", help="AUDIT.json контура SEO")
    p.add_argument("--drafts", default="", help="DRAFTS.json контура SEO")
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--full-out", default="", help="куда положить полную выгрузку (вне репозитория)")
    a = p.parse_args()

    выход = Path(a.out)
    выход.mkdir(parents=True, exist_ok=True)

    записи = list(читать_каталог(Path(a.catalog)))
    if a.limit:
        записи = записи[: a.limit]
    print(f"записей каталога: {len(записи)}")

    без_типа, конфликты, идентичности, рейтинги = [], [], [], []
    свод = {
        "total": 0,
        "byKind": {},
        "byStatus": {},
        "conflicts": {},
        "animation": 0,
        "durationNotMeasured": 0,
        "missingYear": 0,
    }

    for site, запись, снят in записи:
        identity, решение = построить(запись, site, снят)
        свод["total"] += 1
        свод["byKind"][identity.content_kind.value] = (
            свод["byKind"].get(identity.content_kind.value, 0) + 1
        )
        свод["byStatus"][identity.identity_status.value] = (
            свод["byStatus"].get(identity.identity_status.value, 0) + 1
        )
        if identity.is_animation:
            свод["animation"] += 1
        if identity.duration is None:
            свод["durationNotMeasured"] += 1
        if identity.release_year is None:
            свод["missingYear"] += 1

        строка = {
            "internalEntityId": identity.internal_entity_id,
            "siteId": site,
            "domainId": site,
            "providerAssetId": identity.provider_asset_id,
            "displayedTitle": identity.displayed_title,
            "originalTitle": identity.original_title,
            "alternativeTitles": "|".join(identity.alternative_titles),
            "normalizedTitles": варианты(identity.displayed_title)["searchKey"],
            "year": identity.release_year if identity.release_year is not None else "",
            "releaseDate": identity.release_date,
            "country": identity.country,
            "language": identity.language,
            "genres": "|".join(str(t) for t in (запись.get("tags") or [])),
            "studio": "",
            "creators": "",
            "cast": "",
            "duration": identity.duration if identity.duration is not None else "",
            "episodeCount": "",
            "seasonNumber": "",
            "providerContentType": запись.get("type") or "",
            "currentContentKind": identity.content_kind.value,
            "currentSchemaType": "",
            "currentOgType": "",
            "sourceRefs": "cdnvideohub-catalog-cache",
            "existingExternalIds": "|".join(
                f"{k}:{v}" for k, v in sorted(identity.external_ids.items())
            ),
            "conflictReasons": "|".join(identity.conflict_state),
            "resolutionStatus": identity.identity_status.value,
        }

        if identity.content_kind is ContentKind.UNKNOWN:
            без_типа.append(строка)
        if решение.conflicted:
            конфликты.append(
                {
                    **строка,
                    "providerKind": решение.provider_kind.value,
                    "tagKinds": "|".join(k.value for k in решение.tag_kinds),
                    "reason": решение.reason,
                }
            )
            for c in решение.conflicts:
                свод["conflicts"][c] = свод["conflicts"].get(c, 0) + 1

        идентичности.append(identity.as_dict())
        рейтинги.append(
            rating_discovery.discover(
                identity,
                policy=POLICY,
                feed_ratings={
                    "kinopoisk": запись.get("kinopoisk_rating"),
                    "imdb": запись.get("imdb_rating"),
                },
                today=СЕЙЧАС.date(),
                now=СЕЙЧАС,
            )
        )

    свод["ratingCoverage"] = rating_discovery.coverage(рейтинги)

    def csv_записать(имя: str, строки: list[dict]) -> None:
        путь = выход / имя
        if not строки:
            путь.write_text("", encoding="utf-8")
            return
        with open(путь, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(строки[0]))
            w.writeheader()
            w.writerows(строки)

    csv_записать("UNKNOWN-TITLES.csv", без_типа)
    csv_записать("TYPE-CONFLICTS.csv", конфликты)
    # Полная выгрузка — 280 МБ на 159 687 записей, и в репозитории ей не место:
    # артефакт такого размера не читается человеком и не сравнивается в diff.
    # Здесь остаются все ПРОБЛЕМНЫЕ записи целиком плюс сводка и ограниченная
    # выборка разрешённых — по ней видно форму записи. Полная выгрузка пишется
    # отдельным ключом за пределы репозитория.
    проблемные = [
        i
        for i in идентичности
        if i["identityStatus"] not in ("RESOLVED_EXACT_ID", "RESOLVED_HIGH_CONFIDENCE")
    ]
    образец = [i for i in идентичности if i["identityStatus"] == "RESOLVED_EXACT_ID"][:25]
    (выход / "IDENTITY-RESULTS.json").write_text(
        json.dumps(
            {
                "resolverVersion": RESOLVER_VERSION,
                "identityContractVersion": идентичности[0]["schemaVersion"] if идентичности else "",
                "summary": свод,
                "note": (
                    "здесь все нерешённые записи целиком и выборка решённых; "
                    "полная выгрузка — ключ --full-out, вне репозитория"
                ),
                "unresolved": проблемные,
                "resolvedSample": образец,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    состояния_рейтинга = {}
    for r in рейтинги:
        состояния_рейтинга.setdefault(r.rating_state.value, []).append(r)
    (выход / "RATING-DISCOVERY.json").write_text(
        json.dumps(
            {
                "coverage": свод["ratingCoverage"],
                "note": (
                    "выборка до 25 записей на состояние; полная выгрузка — " "ключ --full-out"
                ),
                "samplesByState": {
                    состояние: [x.as_dict() for x in строки[:25]]
                    for состояние, строки in sorted(состояния_рейтинга.items())
                },
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    if a.full_out:
        полный = Path(a.full_out)
        полный.mkdir(parents=True, exist_ok=True)
        (полный / "IDENTITY-RESULTS.full.json").write_text(
            json.dumps(
                {"resolverVersion": RESOLVER_VERSION, "summary": свод, "identities": идентичности},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (полный / "RATING-DISCOVERY.full.json").write_text(
            json.dumps(
                {"coverage": свод["ratingCoverage"], "results": [r.as_dict() for r in рейтинги]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print("полная выгрузка:", полный)

    print(
        json.dumps(
            {k: v for k, v in свод.items() if k != "ratingCoverage"}, ensure_ascii=False, indent=1
        )
    )
    print("рейтинги:", json.dumps(свод["ratingCoverage"], ensure_ascii=False))
    print("без типа:", len(без_типа), "| конфликтов типа:", len(конфликты))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
