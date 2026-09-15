"""Сверка карты сайта с каталогом.

Карта сайта — единственный документ, который витрина сама предъявляет поиску,
и ошибиться в нём можно двумя разными способами. Лишний адрес зовёт робота на
страницу, которой нет или которая принадлежит другому сайту. Недостающий адрес
молчит о странице, которая есть. Первое — дефект, второе — не всегда: свежую
позицию карта берёт не мгновенно.

Поэтому проверка различает три исхода, а не два. Лишние адреса и дубли —
находки всегда. Отсутствие адреса становится находкой, только если позиция
старше окна обновления: пока она моложе, отсутствие объясняется задержкой
рендера, и объявлять это дефектом значит приучать читателя отчёта пропускать
раздел.

Измерение, ради которого модуль написан (2026-09-15, три витрины Lords):

===================  =======  =======  ========  ========  =========
витрина              в карте  каталог  лишних    дублей    отсутствуют
===================  =======  =======  ========  ========  =========
lordfilm47.space       53 400   53 416         0         0          16
lordserial33.biz       52 684   52 711         0         0          27
1lordserials1.online   52 576   52 603         0         0          27
===================  =======  =======  ========  ========  =========

Все отсутствующие появились в каталоге в тот же день, старше суток нет ни
одной. То есть карты Lords чистые, а расхождение — задержка, а не утечка.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

#: Сколько позиция может отсутствовать в карте, прежде чем это станет находкой.
#: Взято не с потолка: витрины Lords перерисовываются реже часа, и суточное
#: окно оставляет запас на один затянувшийся рендер, не пряча при этом потерю.
FRESH_WINDOW = timedelta(hours=24)


@dataclass
class SitemapReconciliation:
    site_id: str
    sitemap_total: int = 0
    catalog_total: int = 0
    stray: list[str] = field(default_factory=list)
    duplicated: list[str] = field(default_factory=list)
    missing_stale: list[str] = field(default_factory=list)
    missing_fresh: list[str] = field(default_factory=list)
    foreign_host: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.stray or self.duplicated or self.missing_stale or self.foreign_host)


def _slug(url: str) -> str:
    return urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]


def reconcile(
    site_id: str,
    sitemap_urls: Iterable[str],
    catalog_first_seen: Mapping[str, str | None],
    *,
    canonical_host: str,
    now: datetime,
    path_marker: str = "/title/",
) -> SitemapReconciliation:
    """Сверить адреса карты с позициями каталога.

    ``catalog_first_seen`` — slug позиции и момент, когда она впервые появилась
    в каталоге, в ISO-8601. ``None`` означает «момент неизвестен»: такая позиция
    считается старой, потому что молодость надо доказать, а не предположить.
    """
    result = SitemapReconciliation(site_id=site_id, catalog_total=len(catalog_first_seen))

    seen: dict[str, int] = {}
    entity_urls = []
    for url in sitemap_urls:
        result.sitemap_total += 1
        host = (urlsplit(url).hostname or "").lower()
        if host and host != canonical_host.lower():
            result.foreign_host.append(url)
        if path_marker not in url:
            continue
        entity_urls.append(url)
        slug = _slug(url)
        seen[slug] = seen.get(slug, 0) + 1

    result.duplicated = sorted(s for s, count in seen.items() if count > 1)
    result.stray = sorted(s for s in seen if s not in catalog_first_seen)

    for slug, first_seen in catalog_first_seen.items():
        if slug in seen:
            continue
        if _is_fresh(first_seen, now):
            result.missing_fresh.append(slug)
        else:
            result.missing_stale.append(slug)
    result.missing_fresh.sort()
    result.missing_stale.sort()
    return result


def _is_fresh(first_seen: str | None, now: datetime) -> bool:
    if not first_seen:
        return False
    try:
        moment = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return now - moment < FRESH_WINDOW


def findings(result: SitemapReconciliation) -> list[dict]:
    """Находки в той же форме, что и остальные проверки оператора."""
    out: list[dict] = []
    if result.foreign_host:
        out.append(
            {
                "id": "SMP-001",
                "category": "sitemap",
                "severity": "критично",
                "summary": f"{len(result.foreign_host)} адресов карты ведут на чужой домен",
                "affected_urls": sorted(set(result.foreign_host))[:50],
                "recommendation": "карта обязана содержать только адреса собственного домена",
                "evidence": f"канонический хост витрины {result.site_id}",
            }
        )
    if result.stray:
        out.append(
            {
                "id": "SMP-002",
                "category": "sitemap",
                "severity": "высокая",
                "summary": f"{len(result.stray)} адресов карты отсутствуют в каталоге",
                "affected_urls": result.stray[:50],
                "recommendation": (
                    "убрать из карты адреса без соответствующей позиции каталога"
                ),
                "evidence": f"каталог: {result.catalog_total} позиций",
            }
        )
    if result.duplicated:
        out.append(
            {
                "id": "SMP-003",
                "category": "sitemap",
                "severity": "средняя",
                "summary": (
                    f"{len(result.duplicated)} адресов встречаются в карте не по одному разу"
                ),
                "affected_urls": result.duplicated[:50],
                "recommendation": "дедуплицировать карту при сборке",
                "evidence": f"в карте {result.sitemap_total} записей",
            }
        )
    if result.missing_stale:
        out.append(
            {
                "id": "SMP-004",
                "category": "sitemap",
                "severity": "средняя",
                "summary": (
                    f"{len(result.missing_stale)} позиций старше суток отсутствуют в карте"
                ),
                "affected_urls": result.missing_stale[:50],
                "recommendation": "проверить, почему рендер карты пропускает эти позиции",
                "evidence": f"окно свежести {FRESH_WINDOW}",
            }
        )
    return out
