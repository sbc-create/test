"""Готовность одного адреса к индексации: READY или HOLD, всегда с причиной.

Зачем отдельный модуль. Проверки в ``technical_seo`` отвечают на вопрос «какие
дефекты есть на сайте» и группируют находки по типу. Перед открытием индексации
нужен другой разрез — поадресный: про каждый канонический URL надо уметь
сказать, попадёт он в будущую карту сайта или нет, и если нет, то почему именно.
Сводка дефектов на этот вопрос не отвечает: страница без единого дефекта из
списка всё ещё может быть пустой заготовкой.

Два решения, которые стоит проговорить.

**UNKNOWN не существует.** Неизмеренное поле — это не «неизвестно», а причина
придержать адрес: ``NOT_MEASURED:<поле>``. Иначе «неизвестно» копится молча и в
день открытия индексации превращается в неизвестного размера риск.

**Глобальный запрет индексации сам по себе не повод для HOLD.** Сейчас все
витрины закрыты заголовком, robots.txt, мета-тегом и флагом профиля — это
намеренное состояние, а не дефект страницы. Вопрос здесь другой: «стоит ли этот
адрес открывать, когда запрет снимут». Если бы замок считался причиной HOLD,
готовых адресов не было бы ни одного и мерить было бы нечего. Поэтому
``Page.indexable`` не участвует в вердикте, а постраничное правило ``noindex``
(служебные разделы вроде поиска и админки) — участвует, и для этого есть
отдельный признак.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from seo_operator.technical_seo import DESCRIPTION_MAX, TITLE_MAX, Page

READY = "READY"
HOLD = "HOLD"

#: Ниже этого объёма отрисованного текста страница не несёт пользы читателю.
#: Величина не взята из воздуха: карточка произведения с описанием провайдера
#: даёт около полутора тысяч символов, карточка без описания — около трёхсот,
#: и граница проведена между ними, ближе к нижнему краю, чтобы придерживать
#: только явные заготовки.
USEFUL_TEXT_MIN_CHARS = 500

#: Точные публичные заглушки и служебные формулировки. Их присутствие в
#: отрисованном тексте — сразу HOLD: такой адрес нельзя показывать поиску ни
#: при каких обстоятельствах.
PLACEHOLDER_MARKERS = (
    "SITE_LEGAL_NAME",
    "SITE_CONTACT_EMAIL",
    "будут опубликованы после заполнения",
    "сведения не выдумываются",
    "тестовая витрина",
    "тестовый стенд",
    "синтетический каталог",
)


@dataclass(frozen=True)
class Eligibility:
    url: str
    verdict: str
    reasons: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return self.verdict == READY


@dataclass
class EligibilitySummary:
    total: int = 0
    ready: int = 0
    hold: int = 0
    unknown: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)

    @property
    def coverage_percent(self) -> float:
        return round(100.0 * self.ready / self.total, 2) if self.total else 0.0


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _structured_data_types(page: Page) -> set[str]:
    types: set[str] = set()
    for block in page.structured_data:
        if not isinstance(block, dict):
            continue
        graph = block.get("@graph")
        nodes = graph if isinstance(graph, list) else [block]
        for node in nodes:
            if isinstance(node, dict) and isinstance(node.get("@type"), str):
                types.add(node["@type"])
    return types


def classify(
    page: Page,
    *,
    site_host: str | None = None,
    require_player: bool = False,
    page_level_noindex: bool = False,
) -> Eligibility:
    """Вердикт по одному адресу.

    ``site_host`` — канонический хост витрины. Нужен, чтобы отличить
    self-canonical от канонизации на чужое семейство: второе для самостоятельного
    домена всегда HOLD.

    ``require_player`` — для страниц просмотра. Карточка без рабочего источника
    воспроизведения бесполезна читателю независимо от качества метаданных.

    ``page_level_noindex`` — постраничное правило (поиск, админка, служебное).
    Это не глобальный замок, а свойство самого адреса.
    """
    reasons: list[str] = []

    if page_level_noindex:
        reasons.append("PAGE_RULE_NOINDEX")

    if page.status_code is None:
        reasons.append("NOT_MEASURED:status_code")
    elif page.status_code != 200:
        reasons.append(f"HTTP_{page.status_code}")

    if page.redirect_chain:
        reasons.append("REDIRECTED")

    host = site_host.lower() if site_host else None
    if page.canonical is None:
        reasons.append("NOT_MEASURED:canonical")
    else:
        canonical_host = _host(page.canonical)
        if host and canonical_host and canonical_host != host:
            reasons.append(f"CROSS_DOMAIN_CANONICAL:{canonical_host}")
        elif page.canonical.rstrip("/") != page.url.rstrip("/"):
            reasons.append("NOT_SELF_CANONICAL")

    if page.title is None:
        reasons.append("NOT_MEASURED:title")
    elif not page.title.strip():
        reasons.append("NO_TITLE")
    elif len(page.title) > TITLE_MAX:
        reasons.append("TITLE_TOO_LONG")

    if page.description is None:
        reasons.append("NOT_MEASURED:description")
    elif not page.description.strip():
        reasons.append("NO_DESCRIPTION")
    elif len(page.description) > DESCRIPTION_MAX:
        reasons.append("DESCRIPTION_TOO_LONG")

    if not page.h1:
        reasons.append("NO_H1")
    elif len(page.h1) > 1:
        reasons.append("MULTIPLE_H1")

    if page.rendered_text_length is None:
        reasons.append("NOT_MEASURED:rendered_text_length")
    elif page.rendered_text_length < USEFUL_TEXT_MIN_CHARS:
        reasons.append("THIN_CONTENT")

    if not _structured_data_types(page):
        reasons.append("NO_STRUCTURED_DATA")

    if not page.open_graph.get("og:title"):
        reasons.append("NO_OPEN_GRAPH")

    if page.internal_links_in <= 0:
        reasons.append("ORPHAN")

    if require_player:
        if page.player_available is None:
            reasons.append("NOT_MEASURED:player_available")
        elif not page.player_available:
            reasons.append("PLAYER_UNAVAILABLE")

    haystack = " ".join(
        part
        for part in (page.title, page.description, page.content_status, *(page.h1 or ()))
        if part
    )
    for marker in PLACEHOLDER_MARKERS:
        if marker in haystack:
            reasons.append(f"PLACEHOLDER:{marker}")
            break

    verdict = HOLD if reasons else READY
    return Eligibility(url=page.url, verdict=verdict, reasons=tuple(reasons))


def classify_all(
    pages: Iterable[Page],
    *,
    site_host: str | None = None,
    require_player: bool = False,
    page_level_noindex: set[str] | None = None,
) -> list[Eligibility]:
    noindex = page_level_noindex or set()
    return [
        classify(
            page,
            site_host=site_host,
            require_player=require_player,
            page_level_noindex=page.url in noindex,
        )
        for page in pages
    ]


def summarize(results: Iterable[Eligibility]) -> EligibilitySummary:
    summary = EligibilitySummary()
    for item in results:
        summary.total += 1
        if item.verdict == READY:
            summary.ready += 1
        elif item.verdict == HOLD:
            summary.hold += 1
        else:  # pragma: no cover - вердикта третьего вида не существует
            summary.unknown += 1
        for reason in item.reasons:
            key = reason.split(":", 1)[0]
            summary.by_reason[key] = summary.by_reason.get(key, 0) + 1
    return summary


def sitemap_candidates(results: Iterable[Eligibility]) -> list[str]:
    """Адреса, которые можно класть в будущую карту сайта.

    Только READY. Отправка карты в поисковые системы этим модулем не
    выполняется и выполняться не может: он ничего не отправляет.
    """
    return sorted(item.url for item in results if item.ready)
