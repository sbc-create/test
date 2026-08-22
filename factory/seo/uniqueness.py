"""Ворота cross_site_uniqueness: три сайта не должны быть тремя копиями.

Общая база фактов о тайтлах разрешена, автоматическое размножение одинаковых
страниц по трём доменам — нет. Проверка работает по фактически отданным
страницам, а не по замыслу: сравниваются заголовки, описания, H1, основной текст
и сам состав индексируемых адресов.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from factory.seo.model import Finding, Report

#: Доля сочетаний меньшего текста, общих с большим, выше которой это один текст.
#: Метрика — containment, а не Jaccard: «тот же текст плюс абзац сверху» тоже дубль,
#: а Jaccard такую пару штрафует за разницу в объёме и пропускает.
NEAR_DUPLICATE_THRESHOLD = 0.75
#: Индексируемая страница обязана нести собственный текст такого объёма.
MIN_OWN_TEXT_CHARS = 200
#: Типы страниц, у которых собственный текст обязателен.
TEXT_PAGE_TYPES = frozenset({"title", "article", "collection", "legal", "season", "episode"})
#: Четыре слова — компромисс: короче даёт ложные совпадения на общих оборотах,
#: длиннее перестаёт замечать переписанный синонимами текст.
SHINGLE_SIZE = 4

_WORD_RE = re.compile(r"[\w-]+", re.UNICODE)


@dataclass(frozen=True)
class PageObservation:
    """Наблюдение одной страницы одного сайта. Заполняется только из ответа сервера."""

    site_id: str
    path: str
    page_type: str
    indexable: bool
    title: str = ""
    description: str = ""
    h1: str = ""
    own_text: str = ""
    canonical: str = ""


@dataclass
class UniquenessInput:
    pages: list[PageObservation] = field(default_factory=list)


def normalize(text: str) -> str:
    return " ".join(_WORD_RE.findall((text or "").lower()))


def shingles(text: str, size: int = SHINGLE_SIZE) -> set[str]:
    words = normalize(text).split()
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def jaccard(left: str, right: str) -> float:
    a, b = shingles(left), shingles(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similarity(left: str, right: str) -> float:
    """Доля сочетаний меньшего текста, встречающихся в большем."""
    a, b = shingles(left), shingles(right)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _indexable(pages: list[PageObservation]) -> list[PageObservation]:
    return [page for page in pages if page.indexable]


def check(pages: list[PageObservation]) -> Report:
    report = Report("cross-site-uniqueness")
    indexable = _indexable(pages)
    sites = sorted({page.site_id for page in pages})

    report.counts = {
        "sites": len(sites),
        "pages": len(pages),
        "indexable_pages": len(indexable),
        "status": "executed" if pages else "skipped",
    }
    if not pages:
        # Пустой вход — это непроведённая проверка, а не пройденная.
        report.add(Finding("cross-site-uniqueness", "critical", "-",
                           "Проверка уникальности не получила ни одной страницы.", "CSU-0"))
        return report
    if len(sites) < 2:
        report.counts["status"] = "skipped"
        report.add(Finding("cross-site-uniqueness", "critical", "-",
                           f"Для сравнения нужно минимум два сайта, получен один: {sites}.", "CSU-0"))
        return report

    # CSU-1..CSU-3: совпадение метаданных между сайтами.
    for label, attribute, rule in (
        ("title", "title", "CSU-1"),
        ("description", "description", "CSU-2"),
        ("H1", "h1", "CSU-3"),
    ):
        buckets: dict[str, list[PageObservation]] = {}
        for page in indexable:
            value = normalize(getattr(page, attribute))
            if not value:
                continue
            buckets.setdefault(value, []).append(page)
        for value, group in buckets.items():
            owners = sorted({page.site_id for page in group})
            if len(owners) > 1:
                report.add(Finding(
                    "cross-site-uniqueness", "critical",
                    ", ".join(f"{page.site_id}{page.path}" for page in group),
                    f"Совпадает {label} на индексируемых страницах разных сайтов ({', '.join(owners)}): «{value[:120]}».",
                    rule,
                ))

    # CSU-4: почти одинаковый основной текст.
    for i, left in enumerate(indexable):
        for right in indexable[i + 1 :]:
            if left.site_id == right.site_id:
                continue
            score = similarity(left.own_text, right.own_text)
            if score >= NEAR_DUPLICATE_THRESHOLD:
                report.add(Finding(
                    "cross-site-uniqueness", "critical",
                    f"{left.site_id}{left.path} ↔ {right.site_id}{right.path}",
                    f"Основной текст совпадает на {score:.0%}: это одна и та же страница на двух доменах.",
                    "CSU-4",
                ))

    # CSU-5: содержательная страница без собственного текста. Списки сюда не
    # попадают: у каталога и ленты ценность в наборе материалов, а не в прозе,
    # и их различие проверяют CSU-1..CSU-3 и CSU-6.
    for page in indexable:
        if page.page_type not in TEXT_PAGE_TYPES:
            continue
        if len(normalize(page.own_text)) < MIN_OWN_TEXT_CHARS:
            report.add(Finding(
                "cross-site-uniqueness", "critical", f"{page.site_id}{page.path}",
                f"Индексируемая страница несёт {len(normalize(page.own_text))} символов собственного текста "
                f"при минимуме {MIN_OWN_TEXT_CHARS}.",
                "CSU-5",
            ))

    # CSU-6: одинаковая индексируемая поверхность у всех сайтов.
    surfaces = {site: frozenset(page.path for page in indexable if page.site_id == site) for site in sites}
    non_empty = {site: surface for site, surface in surfaces.items() if surface}
    if len(non_empty) > 1 and len(set(non_empty.values())) == 1:
        report.add(Finding(
            "cross-site-uniqueness", "critical", ", ".join(sorted(non_empty)),
            "Состав индексируемых адресов полностью совпадает у всех сайтов: это зеркала, а не три сайта.",
            "CSU-6",
        ))

    # CSU-7: canonical индексируемой страницы обязан вести на её собственный сайт.
    for page in indexable:
        if page.canonical and f"//{page.site_id}" not in page.canonical:
            report.add(Finding(
                "cross-site-uniqueness", "critical", f"{page.site_id}{page.path}",
                f"Canonical указывает за пределы своего сайта: {page.canonical}.",
                "CSU-7",
            ))

    report.counts["duplicates"] = len(report.critical)
    return report
