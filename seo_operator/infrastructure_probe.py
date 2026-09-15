"""Проверка адресов, которые не являются страницами для читателя.

Обход страниц и эта проверка разделены намеренно. Постраничные правила —
про title, H1, описание и разметку — к `robots.txt` и карте сайта неприменимы, и
первая версия суточного цикла это доказала: запросив их вместе со страницами,
она выдала 46 находок вместо семи, по три ложных на витрину («нет title», «нет
H1», «код 404»).

Но не проверять их нельзя: именно здесь живут отказы, которых посетитель не
видит, а поисковый робот видит первым. У каждого адреса тут своё ожидание, и
описаны они отдельно от страниц, а не подогнаны под общий список правил.

Отдельный случай — объявленный endpoint. `config/SITE-MATRIX.json` объявляет у
каждой витрины `coverage_endpoint`, и на 2026-09-15 все три витрины Lords
отдавали по нему HTML-страницу «Страница не найдена» с кодом 404. Объявление,
которому ничего не соответствует, хуже отсутствующего: на него ссылаются как на
существующее.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

#: Адрес, которого заведомо нет. Запрашивается, чтобы увидеть, как витрина
#: обрабатывает отсутствие: код 200 на несуществующем адресе — это soft-404,
#: и поиск считает такую страницу настоящей.
ABSENT_PATH = "/__seo-probe-absent__/"


@dataclass(frozen=True)
class Probe:
    url: str
    status_code: int | None
    content_type: str | None
    body: str


Fetcher = Callable[[str], Probe]


@dataclass(frozen=True)
class ProbeFinding:
    id: str
    severity: str
    url: str
    summary: str


def _finding(fid: str, severity: str, url: str, summary: str) -> ProbeFinding:
    return ProbeFinding(id=fid, severity=severity, url=url, summary=summary)


def check_robots(probe: Probe) -> list[ProbeFinding]:
    out = []
    if probe.status_code != 200:
        out.append(
            _finding("INF-001", "критично", probe.url, f"robots.txt отдаёт {probe.status_code}")
        )
        return out
    if not probe.body.strip():
        out.append(_finding("INF-002", "высокая", probe.url, "robots.txt пуст"))
    return out


def check_sitemap(probe: Probe, *, expect_entries: bool) -> list[ProbeFinding]:
    """Карта сайта. ``expect_entries`` отражает решение витрины, а не догадку.

    Пустая карта не всегда дефект: витрина, чьи страницы дублируют соседнюю,
    сознательно не предъявляет их поиску. Поэтому ожидание передаётся снаружи.
    """
    out = []
    if probe.status_code != 200:
        out.append(
            _finding("INF-003", "критично", probe.url, f"карта сайта отдаёт {probe.status_code}")
        )
        return out
    ctype = (probe.content_type or "").lower()
    if "xml" not in ctype:
        out.append(
            _finding("INF-004", "высокая", probe.url, f"карта сайта отдана как {ctype or '?'}")
        )
    has_entries = "<loc>" in probe.body
    if expect_entries and not has_entries:
        out.append(
            _finding(
                "INF-005", "высокая", probe.url, "карта сайта не содержит ни одного адреса"
            )
        )
    if not expect_entries and has_entries:
        out.append(
            _finding(
                "INF-006",
                "средняя",
                probe.url,
                "карта содержит адреса, хотя витрина их не предъявляет",
            )
        )
    return out


def check_absent_path(probe: Probe) -> list[ProbeFinding]:
    if probe.status_code == 404:
        return []
    if probe.status_code == 200:
        return [
            _finding(
                "INF-007",
                "критично",
                probe.url,
                "несуществующий адрес отдаёт 200 — поиск примет страницу за настоящую",
            )
        ]
    return [
        _finding(
            "INF-008",
            "средняя",
            probe.url,
            f"несуществующий адрес отдаёт {probe.status_code} вместо 404",
        )
    ]


def check_declared_endpoint(
    probe: Probe, *, expected_content_type: str = "json"
) -> list[ProbeFinding]:
    """Объявленный в матрице endpoint обязан существовать и отвечать по объявленному типу."""
    if probe.status_code != 200:
        return [
            _finding(
                "INF-009",
                "высокая",
                probe.url,
                f"объявленный endpoint отдаёт {probe.status_code}: "
                "объявление не соответствует витрине",
            )
        ]
    ctype = (probe.content_type or "").lower()
    if expected_content_type not in ctype:
        return [
            _finding(
                "INF-010",
                "высокая",
                probe.url,
                f"объявленный endpoint отдаёт {ctype or '?'} вместо {expected_content_type}",
            )
        ]
    return []


def probe_site(
    base_url: str,
    *,
    fetcher: Fetcher,
    expect_sitemap_entries: bool,
    coverage_endpoint: str | None = None,
) -> list[ProbeFinding]:
    base = base_url.rstrip("/")
    out: list[ProbeFinding] = []
    out += check_robots(fetcher(f"{base}/robots.txt"))
    out += check_sitemap(fetcher(f"{base}/sitemap.xml"), expect_entries=expect_sitemap_entries)
    out += check_absent_path(fetcher(f"{base}{ABSENT_PATH}"))
    if coverage_endpoint:
        out += check_declared_endpoint(fetcher(f"{base}{coverage_endpoint}"))
    return out


def as_dicts(findings: Iterable[ProbeFinding]) -> list[dict]:
    return [
        {
            "id": f.id,
            "category": "infrastructure",
            "severity": f.severity,
            "summary": f.summary,
            "affected_urls": [f.url],
            "recommendation": "привести адрес в соответствие с объявленным поведением",
            "evidence": "проверка инфраструктурных адресов суточного цикла",
        }
        for f in findings
    ]
