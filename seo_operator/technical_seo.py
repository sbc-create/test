"""Technical SEO checks over crawled page records.

Each check returns findings in the shape the repository's seo-audit schema
already defines, so the operator's output validates against the same contract
as a hand-written audit.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

TITLE_MAX = 60
DESCRIPTION_MAX = 160


@dataclass
class Page:
    """One crawled page. Fields left as None mean 'not measured'."""

    url: str
    status_code: int | None = None
    title: str | None = None
    description: str | None = None
    h1: list[str] = field(default_factory=list)
    canonical: str | None = None
    indexable: bool | None = None
    rendered_text_length: int | None = None
    raw_html_text_length: int | None = None
    open_graph: dict[str, str] = field(default_factory=dict)
    structured_data: list[dict[str, Any]] = field(default_factory=list)
    internal_links_in: int = 0
    internal_links_out: int = 0
    lastmod: str | None = None
    in_sitemap: bool = False
    redirect_chain: list[str] = field(default_factory=list)
    player_available: bool | None = None
    content_status: str | None = None
    lcp_ms: int | None = None
    cls: float | None = None
    queries: list[str] = field(default_factory=list)


def _finding(fid, category, severity, summary, urls, recommendation, evidence, detail=None):
    out = {
        "id": fid,
        "category": category,
        "severity": severity,
        "summary": summary[:200],
        "affected_urls": sorted(set(urls))[:50],
        "recommendation": recommendation,
        "evidence": evidence,
    }
    if detail:
        out["detail"] = detail
    return out


def check_server_rendered(pages: Iterable[Page]) -> list[dict]:
    """Substantive server-rendered HTML: the raw response must carry the content."""
    bad = [
        p.url
        for p in pages
        if p.raw_html_text_length is not None
        and p.rendered_text_length
        and p.raw_html_text_length < 0.3 * p.rendered_text_length
    ]
    if not bad:
        return []
    return [
        _finding(
            "SSR-001",
            "crawlability",
            "high",
            f"{len(bad)} страниц отдают почти пустой HTML до исполнения JS",
            bad,
            "Обеспечить server-rendered разметку основного контента.",
            "Сравнение длины текста в сыром ответе и после рендеринга (<30%).",
        )
    ]


def check_titles(pages: Iterable[Page]) -> list[dict]:
    pages = list(pages)
    findings = []
    missing = [p.url for p in pages if not p.title]
    if missing:
        findings.append(
            _finding(
                "ONP-001",
                "on-page",
                "high",
                f"{len(missing)} страниц без title",
                missing,
                "Добавить уникальный title.",
                "Поле title пустое в результатах обхода.",
            )
        )
    too_long = [p.url for p in pages if p.title and len(p.title) > TITLE_MAX]
    if too_long:
        findings.append(
            _finding(
                "ONP-002",
                "on-page",
                "medium",
                f"{len(too_long)} title длиннее {TITLE_MAX} символов",
                too_long,
                f"Сократить title до {TITLE_MAX} символов.",
                f"Длина строки title > {TITLE_MAX}.",
            )
        )
    groups = defaultdict(list)
    for p in pages:
        if p.title:
            groups[p.title.strip().lower()].append(p.url)
    dupes = [urls for urls in groups.values() if len(urls) > 1]
    if dupes:
        flat = [u for urls in dupes for u in urls]
        findings.append(
            _finding(
                "ONP-003",
                "on-page",
                "medium",
                f"{len(dupes)} групп страниц с одинаковым title",
                flat,
                "Сделать title уникальным для каждой страницы.",
                "Точное совпадение строк title после нормализации регистра.",
            )
        )
    return findings


def check_descriptions(pages: Iterable[Page]) -> list[dict]:
    pages = list(pages)
    findings = []
    missing = [p.url for p in pages if not p.description]
    if missing:
        findings.append(
            _finding(
                "ONP-004",
                "on-page",
                "medium",
                f"{len(missing)} страниц без description",
                missing,
                "Добавить уникальный description.",
                "Поле description пустое.",
            )
        )
    too_long = [p.url for p in pages if p.description and len(p.description) > DESCRIPTION_MAX]
    if too_long:
        findings.append(
            _finding(
                "ONP-005",
                "on-page",
                "low",
                f"{len(too_long)} description длиннее {DESCRIPTION_MAX}",
                too_long,
                f"Сократить до {DESCRIPTION_MAX} символов.",
                f"Длина description > {DESCRIPTION_MAX}.",
            )
        )
    return findings


def check_h1(pages: Iterable[Page]) -> list[dict]:
    pages = list(pages)
    findings = []
    none_h1 = [p.url for p in pages if len(p.h1) == 0]
    many_h1 = [p.url for p in pages if len(p.h1) > 1]
    if none_h1:
        findings.append(
            _finding(
                "ONP-006",
                "on-page",
                "medium",
                f"{len(none_h1)} страниц без H1",
                none_h1,
                "Добавить ровно один H1.",
                "H1 не найден при обходе.",
            )
        )
    if many_h1:
        findings.append(
            _finding(
                "ONP-007",
                "on-page",
                "low",
                f"{len(many_h1)} страниц с несколькими H1",
                many_h1,
                "Оставить один H1.",
                "Найдено более одного H1.",
            )
        )
    return findings


def check_canonical(pages: Iterable[Page]) -> list[dict]:
    bad = [
        p.url
        for p in pages
        if p.canonical is not None and p.canonical.rstrip("/") != p.url.rstrip("/")
    ]
    if not bad:
        return []
    return [
        _finding(
            "IDX-001",
            "indexation",
            "high",
            f"{len(bad)} страниц канонизированы на другой URL",
            bad,
            "Установить self-canonical, если это не осознанная склейка.",
            "rel=canonical не совпадает с URL страницы.",
        )
    ]


def check_status_and_redirects(pages: Iterable[Page]) -> list[dict]:
    findings = []
    errors = [p.url for p in pages if p.status_code and p.status_code >= 400]
    if errors:
        findings.append(
            _finding(
                "TEC-001",
                "crawlability",
                "critical",
                f"{len(errors)} страниц отдают код 4xx/5xx",
                errors,
                "Восстановить страницу или отдать корректный 404/410.",
                "HTTP-статус получен при обходе.",
            )
        )
    chains = [p.url for p in pages if len(p.redirect_chain) > 1]
    if chains:
        findings.append(
            _finding(
                "TEC-002",
                "crawlability",
                "medium",
                f"{len(chains)} цепочек редиректов длиннее одного шага",
                chains,
                "Сократить цепочку до одного перехода.",
                "Длина redirect_chain > 1.",
            )
        )
    return findings


def check_sitemap_and_lastmod(pages: Iterable[Page]) -> list[dict]:
    pages = list(pages)
    findings = []
    missing = [p.url for p in pages if p.indexable and not p.in_sitemap]
    if missing:
        findings.append(
            _finding(
                "IDX-002",
                "indexation",
                "medium",
                f"{len(missing)} индексируемых страниц вне sitemap",
                missing,
                "Добавить URL в sitemap.",
                "URL отсутствует в разобранном sitemap.",
            )
        )
    no_lastmod = [p.url for p in pages if p.in_sitemap and not p.lastmod]
    if no_lastmod:
        findings.append(
            _finding(
                "IDX-003",
                "indexation",
                "low",
                f"{len(no_lastmod)} записей sitemap без lastmod",
                no_lastmod,
                "Проставить реальный lastmod по дате изменения контента.",
                "Поле lastmod пустое в sitemap.",
            )
        )
    return findings


def check_orphans(pages: Iterable[Page]) -> list[dict]:
    orphans = [p.url for p in pages if p.indexable and p.internal_links_in == 0]
    if not orphans:
        return []
    return [
        _finding(
            "LNK-001",
            "links",
            "high",
            f"{len(orphans)} orphan-страниц без входящих внутренних ссылок",
            orphans,
            "Связать страницы из рубрик, подборок или меню.",
            "internal_links_in == 0 по графу внутренних ссылок.",
        )
    ]


def check_open_graph(pages: Iterable[Page]) -> list[dict]:
    required = {"og:title", "og:description", "og:image", "og:type"}
    bad = [p.url for p in pages if p.open_graph and not required <= set(p.open_graph)]
    empty = [p.url for p in pages if not p.open_graph]
    urls = bad + empty
    if not urls:
        return []
    return [
        _finding(
            "SD-001",
            "structured-data",
            "low",
            f"{len(urls)} страниц с неполной разметкой Open Graph",
            urls,
            "Заполнить og:title, og:description, og:image, og:type.",
            "Набор og-полей сверен с обязательным перечнем.",
        )
    ]


def check_structured_data_truthfulness(pages: Iterable[Page]) -> list[dict]:
    """Structured data must not assert values the page does not contain.

    This is the check that keeps the operator honest: markup claiming a rating
    or a release date the page never shows is a policy violation, not an
    optimisation.
    """
    violations = []
    for p in pages:
        for block in p.structured_data:
            for key in ("aggregateRating", "ratingValue", "reviewCount", "review"):
                if key in block and not block.get("_verified_on_page"):
                    violations.append(p.url)
    if not violations:
        return []
    return [
        _finding(
            "SD-002",
            "structured-data",
            "critical",
            f"{len(set(violations))} страниц размечают рейтинги/отзывы без "
            "подтверждения на странице",
            violations,
            "Удалить разметку значений, которых нет в видимом контенте.",
            "Поля рейтингов в JSON-LD без флага подтверждения на странице.",
        )
    ]


def check_cannibalization(pages: Iterable[Page]) -> list[dict]:
    """Two indexable URLs targeting the same query compete with each other."""
    by_query: dict[str, list[str]] = defaultdict(list)
    for p in pages:
        if not p.indexable:
            continue
        for q in p.queries:
            by_query[q.strip().lower()].append(p.url)
    conflicts = {q: urls for q, urls in by_query.items() if len(set(urls)) > 1}
    if not conflicts:
        return []
    flat = sorted({u for urls in conflicts.values() for u in urls})
    return [
        _finding(
            "ONP-008",
            "on-page",
            "medium",
            f"{len(conflicts)} запросов, на которые нацелено несколько URL",
            flat,
            "Оставить один целевой URL на запрос, остальные переориентировать.",
            "Пересечение целевых запросов по индексируемым URL.",
            detail="; ".join(f"{q}: {len(set(u))} URL" for q, u in list(conflicts.items())[:10]),
        )
    ]


def check_player_availability(pages: Iterable[Page]) -> list[dict]:
    broken = [
        p.url for p in pages if p.player_available is False and p.content_status == "published"
    ]
    if not broken:
        return []
    return [
        _finding(
            "TEC-003",
            "performance",
            "critical",
            f"{len(broken)} опубликованных страниц с недоступным плеером",
            broken,
            "Проверить источник видео или снять страницу с публикации.",
            "Флаг доступности плеера получен из мониторинга.",
        )
    ]


def check_core_web_vitals(pages: Iterable[Page]) -> list[dict]:
    slow = [p.url for p in pages if p.lcp_ms is not None and p.lcp_ms > 2500]
    shifty = [p.url for p in pages if p.cls is not None and p.cls > 0.1]
    findings = []
    if slow:
        findings.append(
            _finding(
                "PRF-001",
                "performance",
                "medium",
                f"{len(slow)} страниц с LCP выше 2500 мс",
                slow,
                "Оптимизировать самый крупный элемент шаблона.",
                "LCP измерен инструментом рендеринга.",
            )
        )
    if shifty:
        findings.append(
            _finding(
                "PRF-002",
                "performance",
                "medium",
                f"{len(shifty)} страниц с CLS выше 0.1",
                shifty,
                "Задать размеры изображений и зарезервировать место под блоки.",
                "CLS измерен инструментом рендеринга.",
            )
        )
    return findings


ALL_CHECKS = (
    check_server_rendered,
    check_titles,
    check_descriptions,
    check_h1,
    check_canonical,
    check_status_and_redirects,
    check_sitemap_and_lastmod,
    check_orphans,
    check_open_graph,
    check_structured_data_truthfulness,
    check_cannibalization,
    check_player_availability,
    check_core_web_vitals,
)


def run_all(pages: Iterable[Page]) -> list[dict]:
    pages = list(pages)
    findings: list[dict] = []
    for check in ALL_CHECKS:
        findings.extend(check(pages))
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    return sorted(findings, key=lambda f: (severity_order[f["severity"]], f["id"]))
