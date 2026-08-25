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
#: Ниже этого объёма containment не применяется: короткая цитата целиком
#: содержится в длинном тексте и давала бы 100% совпадения на честно разных страницах.
MIN_SHINGLES_FOR_CONTAINMENT = 12
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
    #: Имя сайта, вырезаемое из заголовков перед сравнением.
    site_name: str = ""
    #: Собственный хост сайта. Нужен CSU-7: чтобы решить, ведёт ли canonical за
    #: пределы сайта, надо знать, где эти пределы. Пустое значение означает
    #: «хост не передан», и проверка тогда не выполняется, а не проходит.
    site_host: str = ""


def _host_of(url: str) -> str:
    """Хост из абсолютного адреса. Относительный адрес хоста не содержит."""
    from urllib.parse import urlsplit

    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


@dataclass
class UniquenessInput:
    pages: list[PageObservation] = field(default_factory=list)


def normalize(text: str, *, drop: tuple[str, ...] = ()) -> str:
    words = _WORD_RE.findall((text or "").lower())
    if drop:
        # Название сайта присутствует в каждом заголовке по шаблону. Сравнивать
        # с ним — значит никогда не найти совпадения: разные имена сайтов делают
        # любые два заголовка различными, даже если остальное слово в слово одно.
        excluded = {word for item in drop for word in _WORD_RE.findall(item.lower())}
        words = [word for word in words if word not in excluded]
    return " ".join(words)


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
            value = normalize(getattr(page, attribute), drop=(page.site_name, page.site_id))
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
            left_size = len(shingles(left.own_text))
            right_size = len(shingles(right.own_text))
            if min(left_size, right_size) < MIN_SHINGLES_FOR_CONTAINMENT:
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
    ordered = sorted(non_empty)
    # Сравнение попарно: пара зеркал внутри тройки — уже дубль, а прежнее условие
    # «совпало у всех» на трёх сайтах не срабатывало никогда.
    for i, left in enumerate(ordered):
        for right in ordered[i + 1:]:
            if non_empty[left] == non_empty[right]:
                report.add(Finding(
                    "cross-site-uniqueness", "critical", f"{left}, {right}",
                    f"Состав индексируемых адресов у сайтов {left} и {right} совпадает полностью: "
                    "это зеркала, а не два самостоятельных сайта.",
                    "CSU-6",
                ))

    # CSU-7: canonical индексируемой страницы обязан вести на её собственный сайт.
    #
    # Сравниваются хосты, а не подстроки. Прежняя проверка искала в canonical
    # подстроку `//<site_id>` и держалась на совпадении идентификатора пакета с
    # именем хоста. У прежних сайтов оно совпадало (`site-a` ↔
    # `site-a.localhost`), у настоящего домена — нет: `lords-01` не встречается
    # в `https://lordfilm47.space/`, и правильный canonical объявлялся бы чужим.
    # Хост, которого нет, не заменяется догадкой: проверка отмечается
    # невыполненной для такой страницы.
    skipped_canonical = 0
    for page in indexable:
        if not page.canonical:
            continue
        host = _host_of(page.canonical)
        expected = (page.site_host or "").strip().lower()
        if not expected:
            # Хост не передан — проверить нечем. Молча пропустить нельзя: тогда
            # достаточно забыть одно поле, чтобы ворота перестали существовать,
            # и об этом никто не узнает. Это неисправность вызывающей стороны, и
            # она сообщается как неисправность.
            skipped_canonical += 1
            report.add(Finding(
                "cross-site-uniqueness", "critical", f"{page.site_id}{page.path}",
                "Проверить canonical нечем: собственный хост сайта не передан "
                "в наблюдение. Это не пройденная проверка, а невыполненная.",
                "CSU-7",
            ))
            continue
        if host != expected:
            report.add(Finding(
                "cross-site-uniqueness", "critical", f"{page.site_id}{page.path}",
                f"Canonical ведёт на «{host or page.canonical}», а сайт живёт на «{expected}».",
                "CSU-7",
            ))
    if skipped_canonical:
        report.counts["canonical_host_unknown"] = skipped_canonical

    report.counts["duplicates"] = len(report.critical)
    return report
