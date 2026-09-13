"""JSON-LD и техническое соответствие.

Разметка — утверждение, адресованное машине. Поэтому правило здесь то же,
что и для текста: разметка не может утверждать больше, чем видно человеку и
чем подтверждено фактами.

Из этого следуют три вещи, которые модуль проверяет буквально:

* `VideoObject` существует только там, где источник действительно доступен и
  разрешён. Разметка ролика без ролика — обещание машине, которого мы не
  исполняем;
* `Review` и `AggregateRating` из модельного текста не создаются никогда;
* `canonical` один и тот же в HTML, в карте сайта и во внутренних ссылках,
  а `BreadcrumbList` совпадает с тем, что показывает интерфейс.

Техническая исправность разметки не является доказательством показа rich
result. Это записано в отчёте отдельной строкой, потому что подмена одного
другим — самая частая ошибка в отчётах по SEO.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .factpack import SEOFactPack, VideoAvailability

#: Тип разметки по сущности. Соответствие однозначное: сезон не размечается
#: как сериал, серия — как сезон.
ТИП_ПО_СУЩНОСТИ = {
    "title": {"movie": "Movie", "anime_movie": "Movie",
              "documentary": "Movie", "series": "TVSeries",
              "anime": "TVSeries", "cartoon": "TVSeries", "ova": "TVSeries"},
    "season": "TVSeason",
    "episode": "TVEpisode",
}

ЗАПРЕЩЁННЫЕ_ТИПЫ = ("Review", "AggregateRating", "Rating", "UserReview")

RICH_RESULT_DISCLAIMER = (
    "Техническая валидность разметки не доказывает показ rich result: показ "
    "решает поисковая система, и наблюдать его можно только в её отчёте.")


@dataclass
class SchemaIssue:
    code: str
    severity: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail}


@dataclass
class StructuredDataReport:
    issues: list[SchemaIssue] = field(default_factory=list)
    jsonld: list[dict[str, Any]] = field(default_factory=list)
    canonical_conflicts: int = 0
    visible_mismatches: int = 0
    fake_review_markup: int = 0
    rich_result_status: str = "NOT_OBSERVED"
    rich_result_reason: str = RICH_RESULT_DISCLAIMER

    @property
    def errors(self) -> list[SchemaIssue]:
        return [i for i in self.issues if i.severity in ("CRITICAL", "ERROR")]

    def to_dict(self) -> dict[str, Any]:
        return {"issues": [i.to_dict() for i in self.issues],
                "errors": len(self.errors),
                "canonical_conflicts": self.canonical_conflicts,
                "visible_mismatches": self.visible_mismatches,
                "fake_review_markup": self.fake_review_markup,
                "rich_result_status": self.rich_result_status,
                "rich_result_reason": self.rich_result_reason,
                "jsonld": self.jsonld}


def _at_id(site_url: str, path: str) -> str:
    return f"{site_url.rstrip('/')}{path}"


def build_jsonld(pack: SEOFactPack, *, site_url: str, canonical_path: str,
                 display_number: int | None = None,
                 season_number: int | None = None,
                 breadcrumbs: Sequence[tuple[str, str]] = (),
                 video_url: str | None = None,
                 video_license_ok: bool = False,
                 title_path: str | None = None,
                 season_path: str | None = None) -> list[dict[str, Any]]:
    """Собрать разметку строго по фактам. Пустое поле не заполняется."""
    название = pack.value("/canonical_title_ru")
    тип_работы = pack.value("/work_type")
    узлы: list[dict[str, Any]] = []

    if pack.entity_type == "title":
        тип = ТИП_ПО_СУЩНОСТИ["title"].get(тип_работы or "", "CreativeWork")
    else:
        тип = ТИП_ПО_СУЩНОСТИ[pack.entity_type]

    узел: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": тип,
        "@id": _at_id(site_url, canonical_path),
        "url": _at_id(site_url, canonical_path),
    }
    if pack.entity_type == "episode":
        узел["name"] = pack.value("/episode_title") or (
            f"Серия {display_number}" if display_number is not None else None)
        if display_number is not None:
            узел["episodeNumber"] = display_number
        if season_path:
            узел["partOfSeason"] = {"@type": "TVSeason",
                                    "@id": _at_id(site_url, season_path)}
        if title_path:
            узел["partOfSeries"] = {"@type": "TVSeries",
                                    "@id": _at_id(site_url, title_path)}
    elif pack.entity_type == "season":
        узел["name"] = название and f"{название}. Сезон {season_number}" or None
        if season_number is not None:
            узел["seasonNumber"] = season_number
        if title_path:
            узел["isPartOf"] = {"@type": "TVSeries",
                                "@id": _at_id(site_url, title_path)}
        серий = pack.value("/actual_episode_count")
        if серий is not None:
            узел["numberOfEpisodes"] = int(серий)
    else:
        узел["name"] = название
        оригинал = pack.value("/original_title")
        if оригинал:
            узел["alternateName"] = оригинал
        год = pack.value("/year")
        if год is not None:
            узел["datePublished"] = str(год)
        страны = pack.value("/countries")
        if страны:
            узел["countryOfOrigin"] = [{"@type": "Country", "name": с}
                                       for с in страны]
        жанры = pack.value("/genres")
        if жанры:
            узел["genre"] = list(жанры)
        сезонов = pack.value("/season_count")
        if сезонов is not None and тип == "TVSeries":
            узел["numberOfSeasons"] = int(сезонов)
        возраст = pack.value("/age_rating")
        if возраст:
            узел["contentRating"] = str(возраст)

    синопсис = pack.value("/episode_synopsis") if pack.entity_type == "episode" \
        else (pack.value("/season_synopsis") if pack.entity_type == "season"
              else pack.value("/synopsis_short"))
    if синопсис:
        узел["description"] = синопсис

    создатели = pack.value("/creators") or []
    режиссёры = [c for c in создатели
                 if isinstance(c, dict) and c.get("role") == "director"]
    if режиссёры:
        узел["director"] = [{"@type": "Person", "name": c["name"]}
                            for c in режиссёры]
    актёры = [c for c in (pack.value("/characters") or [])
              if isinstance(c, dict) and c.get("actor")]
    if актёры:
        узел["actor"] = [{"@type": "Person", "name": c["actor"]} for c in актёры]

    узел = {k: v for k, v in узел.items() if v is not None}
    узлы.append(узел)

    # VideoObject — только при реально доступном и разрешённом источнике.
    доступность = pack.value("/video_availability")
    if доступность == VideoAvailability.AVAILABLE.value and video_url and \
            video_license_ok:
        узлы.append({
            "@context": "https://schema.org", "@type": "VideoObject",
            "@id": _at_id(site_url, canonical_path) + "#video",
            "name": узел.get("name"), "contentUrl": video_url,
            "isPartOf": {"@id": узел["@id"]},
            **({"description": синопсис} if синопсис else {}),
        })

    if breadcrumbs:
        узлы.append({
            "@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": имя,
                 "item": _at_id(site_url, путь)}
                for i, (имя, путь) in enumerate(breadcrumbs)],
        })
    return узлы


def validate(узлы: Sequence[Mapping[str, Any]], *, pack: SEOFactPack,
             canonical_html: str | None, canonical_sitemap: str | None,
             internal_links: Iterable[str] = (),
             visible_h1: str | None = None,
             visible_breadcrumbs: Sequence[str] = (),
             display_number: int | None = None,
             season_number: int | None = None,
             video_present: bool = False) -> StructuredDataReport:
    отчёт = StructuredDataReport(jsonld=[dict(у) for у in узлы])

    # 1. Разбирается ли вообще.
    for узел in узлы:
        try:
            json.loads(json.dumps(узел, ensure_ascii=False))
        except (TypeError, ValueError) as e:
            отчёт.issues.append(SchemaIssue("JSONLD_PARSE_ERROR", "CRITICAL",
                                            str(e)))
    сериализовано = json.dumps([dict(у) for у in узлы], ensure_ascii=False)

    # 2. Отзывов и рейтингов из модельного текста не бывает.
    for тип in ЗАПРЕЩЁННЫЕ_ТИПЫ:
        if re.search(rf'"@type"\s*:\s*"{тип}"', сериализовано):
            отчёт.fake_review_markup += 1
            отчёт.issues.append(SchemaIssue(
                "FAKE_REVIEW_MARKUP", "CRITICAL",
                f"{тип} из модельного текста: это утверждение о чужом мнении, "
                f"которого не существует"))

    основной = узлы[0] if узлы else {}
    тип_работы = pack.value("/work_type")

    # 3. Тип соответствует сущности.
    ожидаемый = (ТИП_ПО_СУЩНОСТИ["title"].get(тип_работы or "", "CreativeWork")
                 if pack.entity_type == "title"
                 else ТИП_ПО_СУЩНОСТИ[pack.entity_type])
    if основной.get("@type") != ожидаемый:
        отчёт.issues.append(SchemaIssue(
            "ENTITY_TYPE_MISMATCH", "ERROR",
            f"сущность {pack.entity_type}/{тип_работы} размечена как "
            f"{основной.get('@type')!r}, ожидалось {ожидаемый!r}"))

    # 4. Стабильный @id и связь с родителем.
    if not основной.get("@id"):
        отчёт.issues.append(SchemaIssue("MISSING_AT_ID", "ERROR",
                                        "у узла нет устойчивого @id"))
    if pack.entity_type in ("season", "episode"):
        связь = основной.get("isPartOf") or основной.get("partOfSeries") or \
            основной.get("partOfSeason")
        if not связь:
            отчёт.issues.append(SchemaIssue(
                "MISSING_IS_PART_OF", "ERROR",
                f"{pack.entity_type} не связан с родительской сущностью"))

    # 5. Номера.
    if pack.entity_type == "episode" and display_number is not None and \
            основной.get("episodeNumber") != display_number:
        отчёт.issues.append(SchemaIssue(
            "EPISODE_NUMBER_MISMATCH", "CRITICAL",
            f"в разметке episodeNumber={основной.get('episodeNumber')}, "
            f"а показывается {display_number}"))
    if pack.entity_type == "season" and season_number is not None and \
            основной.get("seasonNumber") != season_number:
        отчёт.issues.append(SchemaIssue(
            "SEASON_NUMBER_MISMATCH", "CRITICAL",
            f"в разметке seasonNumber={основной.get('seasonNumber')}, "
            f"а показывается {season_number}"))

    # 6. VideoObject без источника.
    видео = [у for у in узлы if у.get("@type") == "VideoObject"]
    доступность = pack.value("/video_availability")
    if видео and доступность != VideoAvailability.AVAILABLE.value:
        отчёт.issues.append(SchemaIssue(
            "VIDEOOBJECT_WITHOUT_SOURCE", "CRITICAL",
            f"разметка обещает ролик, а доступность источника — "
            f"{доступность!r}"))
    if видео and not video_present:
        отчёт.issues.append(SchemaIssue(
            "VIDEOOBJECT_NOT_ON_PAGE", "CRITICAL",
            "VideoObject размечен, а на странице ролика нет"))

    # 7. canonical един везде.
    адреса = {а for а in (canonical_html, canonical_sitemap) if а}
    адреса.update(а for а in internal_links if а)
    if len(адреса) > 1:
        отчёт.canonical_conflicts += 1
        отчёт.issues.append(SchemaIssue(
            "CANONICAL_CONFLICT", "CRITICAL",
            f"canonical различается: {sorted(адреса)}"))
    if canonical_html and основной.get("url") and \
            not основной["url"].endswith(canonical_html):
        отчёт.canonical_conflicts += 1
        отчёт.issues.append(SchemaIssue(
            "CANONICAL_CONFLICT", "CRITICAL",
            f"url разметки {основной['url']!r} не совпадает с canonical "
            f"{canonical_html!r}"))

    # 8. Видимый HTML и разметка говорят одно и то же.
    if visible_h1 and основной.get("name"):
        если_h1 = re.sub(r"\s+", " ", visible_h1).strip().lower()
        если_имя = re.sub(r"\s+", " ", str(основной["name"])).strip().lower()
        if если_имя not in если_h1 and если_h1 not in если_имя:
            отчёт.visible_mismatches += 1
            отчёт.issues.append(SchemaIssue(
                "VISIBLE_SCHEMA_MISMATCH", "ERROR",
                f"H1 «{visible_h1}» и name разметки «{основной['name']}» "
                f"описывают разное"))
    крошки = next((у for у in узлы if у.get("@type") == "BreadcrumbList"), None)
    if крошки and visible_breadcrumbs:
        из_разметки = [э.get("name") for э in крошки.get("itemListElement", [])]
        if [str(с) for с in visible_breadcrumbs] != [str(с) for с in из_разметки]:
            отчёт.visible_mismatches += 1
            отчёт.issues.append(SchemaIssue(
                "BREADCRUMBS_MISMATCH", "ERROR",
                f"крошки интерфейса {list(visible_breadcrumbs)} и разметки "
                f"{из_разметки} расходятся"))
    return отчёт
