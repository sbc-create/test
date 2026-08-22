"""
Технические SEO-проверки.

Работают над записями страниц (из CMS/краулера), а не над живой сетью:
так проверки детерминированы и тестируемы, а сетевой краул подключается
как источник этих же записей.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable
from urllib.parse import urlparse, parse_qs

SEVERITY_ORDER = {"critical": 3, "high": 2, "medium": 1, "low": 0}


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    url: str | None
    detail: str
    auto_fixable: bool = False


@dataclass
class Page:
    url: str
    status: int = 200
    redirect_to: str | None = None
    canonical: str | None = None
    robots_meta: str = "index,follow"
    x_robots: str | None = None
    title: str | None = None
    description: str | None = None
    h1: str | None = None
    rendered_main_text: str = ""
    internal_links_out: list[str] = field(default_factory=list)
    internal_links_in: int = 0
    in_sitemap: bool = False
    sitemap_lastmod: str | None = None
    content_hash: str | None = None
    depth: int = 0
    media_available: bool | None = None
    mobile_parity: bool = True
    structured_data: list[dict[str, Any]] = field(default_factory=list)
    cls: float | None = None
    lcp_ms: int | None = None
    console_errors: int = 0

    @property
    def indexable(self) -> bool:
        blocked = "noindex" in (self.robots_meta or "") or "noindex" in (self.x_robots or "")
        return self.status == 200 and not blocked


def check_status_and_redirects(pages: Iterable[Page]) -> list[Finding]:
    out = []
    by_url = {p.url: p for p in pages}
    for p in by_url.values():
        if p.status >= 500:
            out.append(Finding("http_status", "critical", p.url, f"Ответ {p.status}"))
        elif p.status == 404 and p.internal_links_in > 0:
            out.append(Finding("broken_internal_link", "high", p.url,
                               f"404 при {p.internal_links_in} входящих внутренних ссылках", True))
        elif 300 <= p.status < 400:
            chain, cur, seen = 0, p, set()
            while cur and cur.redirect_to and cur.url not in seen:
                seen.add(cur.url)
                chain += 1
                cur = by_url.get(cur.redirect_to)
                if chain > 4:
                    break
            if chain >= 3:
                out.append(Finding("redirect_chain", "medium", p.url, f"Цепочка редиректов длиной {chain}"))
            if cur and cur.url in seen:
                out.append(Finding("redirect_loop", "critical", p.url, "Циклический редирект"))
    return out


def check_canonical(pages: Iterable[Page], site_domain: str) -> list[Finding]:
    out = []
    for p in pages:
        if not p.canonical:
            if p.indexable:
                out.append(Finding("canonical_missing", "medium", p.url, "Нет canonical", True))
            continue
        host = urlparse(p.canonical).netloc
        if host and site_domain not in host:
            out.append(Finding("canonical_cross_domain", "critical", p.url,
                               f"Canonical указывает на чужой домен: {p.canonical}"))
        if p.canonical != p.url and not p.indexable:
            out.append(Finding("canonical_on_noindex", "high", p.url,
                               "Canonical на странице с noindex — противоречивые сигналы"))
    return out


def check_robots_conflicts(pages: Iterable[Page]) -> list[Finding]:
    out = []
    for p in pages:
        noindexed = "noindex" in (p.robots_meta or "") or "noindex" in (p.x_robots or "")
        if noindexed and p.in_sitemap:
            out.append(Finding("sitemap_noindex_conflict", "high", p.url,
                               "Страница в sitemap и одновременно noindex", True))
        if p.robots_meta and p.x_robots and (
                ("noindex" in p.robots_meta) != ("noindex" in p.x_robots)):
            out.append(Finding("robots_signal_conflict", "high", p.url,
                               f"meta='{p.robots_meta}' против X-Robots='{p.x_robots}'"))
    return out


def check_sitemap(pages: Iterable[Page], previous_count: int | None = None) -> list[Finding]:
    pages = list(pages)
    out = []
    in_sitemap = [p for p in pages if p.in_sitemap]
    for p in in_sitemap:
        if p.status != 200:
            out.append(Finding("sitemap_bad_status", "high", p.url,
                               f"В sitemap страница со статусом {p.status}", True))
    for p in pages:
        if p.indexable and not p.in_sitemap and p.internal_links_in > 0:
            out.append(Finding("sitemap_missing", "low", p.url, "Индексируемая страница вне sitemap", True))
    if previous_count is not None and previous_count > 0:
        delta = (len(in_sitemap) - previous_count) / previous_count * 100
        if abs(delta) > 50:
            out.append(Finding("sitemap_explosion", "critical", None,
                               f"Количество URL в sitemap изменилось на {delta:+.0f}%"))
    return out


def check_thin_and_duplicate(pages: Iterable[Page], min_words: int = 120) -> list[Finding]:
    pages = list(pages)
    out = []
    for p in pages:
        if not p.indexable:
            continue
        words = len(p.rendered_main_text.split())
        if words == 0:
            out.append(Finding("empty_page", "critical", p.url, "Индексируемая страница без основного контента", True))
        elif words < min_words:
            out.append(Finding("thin_page", "high", p.url,
                               f"Индексируемая страница {words} слов < {min_words}", True))

    hashes = defaultdict(list)
    for p in pages:
        if p.content_hash and p.indexable:
            hashes[p.content_hash].append(p.url)
    for h, urls in hashes.items():
        if len(urls) > 1:
            out.append(Finding("duplicate_content", "high", urls[0],
                               f"Идентичный контент на {len(urls)} URL: {urls[:5]}"))

    for field_name in ("title", "description", "h1"):
        counter = Counter(getattr(p, field_name) for p in pages
                          if p.indexable and getattr(p, field_name))
        for value, count in counter.items():
            if count > 1:
                out.append(Finding(f"duplicate_{field_name}", "medium", None,
                                   f"{field_name} повторяется на {count} страницах: {value!r}", True))
    return out


def check_meta_quality(pages: Iterable[Page]) -> list[Finding]:
    out = []
    for p in pages:
        if not p.indexable:
            continue
        if not p.title:
            out.append(Finding("title_missing", "high", p.url, "Нет title", True))
        elif len(p.title) > 70:
            out.append(Finding("title_too_long", "low", p.url, f"title {len(p.title)} символов", True))
        if not p.description:
            out.append(Finding("description_missing", "medium", p.url, "Нет description", True))
        if p.h1 and p.title and p.h1.strip().lower() == p.title.strip().lower():
            out.append(Finding("h1_title_identical", "low", p.url, "H1 дословно повторяет title"))
        if not p.h1:
            out.append(Finding("h1_missing", "medium", p.url, "Нет H1", True))
    return out


def check_crawl_traps(pages: Iterable[Page], param_limit: int = 2) -> list[Finding]:
    out = []
    param_counts: Counter = Counter()
    for p in pages:
        q = parse_qs(urlparse(p.url).query)
        if len(q) > param_limit and p.indexable:
            out.append(Finding("crawl_trap", "high", p.url,
                               f"Индексируемый URL с {len(q)} параметрами", True))
        for key in q:
            param_counts[key] += 1
    for key, count in param_counts.items():
        if count > 50:
            out.append(Finding("parameter_explosion", "high", None,
                               f"Параметр '{key}' порождает {count} URL — вероятная ловушка обхода"))
    return out


def check_orphans_and_depth(pages: Iterable[Page], max_depth: int = 4) -> list[Finding]:
    out = []
    for p in pages:
        if p.indexable and p.internal_links_in == 0 and p.depth > 0:
            out.append(Finding("orphan_page", "high", p.url, "Индексируемая страница без входящих ссылок", True))
        if p.depth > max_depth:
            out.append(Finding("excessive_depth", "medium", p.url, f"Глубина {p.depth} > {max_depth}"))
    return out


def check_structured_data(pages: Iterable[Page]) -> list[Finding]:
    """Structured data должна отражать реальность страницы, а не желаемую выдачу."""
    out = []
    for p in pages:
        for sd in p.structured_data:
            sd_type = sd.get("@type")
            if sd_type == "Review" and not sd.get("_is_genuine_review"):
                out.append(Finding("fake_review_schema", "critical", p.url,
                                   "Review schema на не-обзоре — прямое нарушение политики (GR-002)"))
            if sd_type == "AggregateRating":
                if not sd.get("_from_real_published_ratings"):
                    out.append(Finding("fabricated_rating", "critical", p.url,
                                       "AggregateRating не из реальных опубликованных оценок (GR-002)"))
                if sd.get("reviewCount", 0) == 0:
                    out.append(Finding("empty_aggregate_rating", "high", p.url,
                                       "AggregateRating с нулём оценок"))
            if sd_type == "VideoObject" and p.media_available is False:
                out.append(Finding("video_schema_without_media", "high", p.url,
                                   "VideoObject при недоступном видео"))
    return out


def check_performance(pages: Iterable[Page], cls_budget: float = 0.1,
                      lcp_budget_ms: int = 2500) -> list[Finding]:
    out = []
    for p in pages:
        if p.cls is not None and p.cls > cls_budget:
            out.append(Finding("cls_regression", "high", p.url, f"CLS {p.cls} > {cls_budget}"))
        if p.lcp_ms is not None and p.lcp_ms > lcp_budget_ms:
            out.append(Finding("lcp_regression", "medium", p.url, f"LCP {p.lcp_ms}ms > {lcp_budget_ms}ms"))
        if p.console_errors > 0:
            out.append(Finding("console_errors", "low", p.url, f"{p.console_errors} ошибок в консоли"))
        if not p.mobile_parity:
            out.append(Finding("mobile_parity", "high", p.url, "Мобильная версия не соответствует десктопной"))
    return out


def check_leaks(pages: Iterable[Page], site_domain: str,
                other_domains: Iterable[str] = ()) -> list[Finding]:
    """Утечки staging/dev и перекрёстные ссылки между tenant."""
    out = []
    others = set(other_domains)
    for p in pages:
        if re.search(r"\b(staging|dev|demo|test)\.", p.url) and p.indexable:
            out.append(Finding("staging_leak", "critical", p.url, "Индексируемый staging/dev URL"))
        for link in p.internal_links_out:
            host = urlparse(link).netloc
            if host and host in others:
                out.append(Finding("cross_tenant_link", "high", p.url,
                                   f"Ссылка на другой сайт портфеля как внутренняя: {link}"))
    return out


def run_all(pages: list[Page], site_domain: str, *, other_domains: Iterable[str] = (),
            previous_sitemap_count: int | None = None) -> list[Finding]:
    findings: list[Finding] = []
    findings += check_status_and_redirects(pages)
    findings += check_canonical(pages, site_domain)
    findings += check_robots_conflicts(pages)
    findings += check_sitemap(pages, previous_sitemap_count)
    findings += check_thin_and_duplicate(pages)
    findings += check_meta_quality(pages)
    findings += check_crawl_traps(pages)
    findings += check_orphans_and_depth(pages)
    findings += check_structured_data(pages)
    findings += check_performance(pages)
    findings += check_leaks(pages, site_domain, other_domains)
    findings.sort(key=lambda f: -SEVERITY_ORDER[f.severity])
    return findings


def summarize(findings: list[Finding]) -> dict[str, Any]:
    by_sev = Counter(f.severity for f in findings)
    by_check = Counter(f.check for f in findings)
    return {
        "total": len(findings),
        "by_severity": dict(by_sev),
        "by_check": dict(by_check.most_common(15)),
        "auto_fixable": sum(1 for f in findings if f.auto_fixable),
        "blocking": [f.check for f in findings if f.severity == "critical"],
    }
