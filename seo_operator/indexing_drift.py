"""Read-only проверка соответствия индексации решению владельца.

Ожидание задано декларативно в реестре портфеля: на 2026-09-15 это
`yummyani.site = OPEN` и восемь остальных площадок `= CLOSED`. Проверка ничего
не меняет и менять не может — у неё нет ни одной операции записи.

Три вещи, ради которых модуль написан именно так.

**Один ответ на все выводы.** Код, заголовки и HTML берутся из одного GET.
Запрос `HEAD` как единственное доказательство запрещён: посредник перед
приложением добавляет ``X-Robots-Tag`` на `GET`, и однажды именно `HEAD` привёл
к неверному выводу о том, какой слой закрывает витрину. Отдельная проверка
сравнивает оба метода и сообщает о расхождении, а не выбирает удобный.

**«Нарушено» и «не измерено» — разные исходы.** Таймаут, сетевая ошибка и
пустой ответ не означают ни открытия, ни закрытия. Считать их нарушением —
поднимать ложную тревогу; считать подтверждением — пропускать настоящее. У них
свой статус.

**Ожидание приходит снаружи.** Модуль не знает, какое состояние правильное, и
не должен: он сверяет факт с тем, что записано в реестре. Смена решения
владельца — правка реестра, а не кода проверки.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

OPEN = "OPEN"
CLOSED = "CLOSED"
MIXED = "MIXED"
UNMEASURED = "UNMEASURED"

#: Слои, по которым судят о состоянии. Порядок — он же порядок снятия при
#: открытии: заголовок последний, потому что перекрывает остальные.
LAYERS = ("meta_robots", "robots_txt", "x_robots_tag")

_DISALLOW_ALL = re.compile(r"(?im)^\s*Disallow:\s*/\s*$")
_META_ROBOTS = re.compile(r'name=["\']robots["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_CANONICAL = re.compile(r'rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', re.I)
_X_ROBOTS = re.compile(r"(?im)^x-robots-tag:(.*)$")


@dataclass(frozen=True)
class Response:
    """Один ответ: код, заголовки и тело вместе, а не по отдельности."""

    status: int | None
    headers: str
    body: str
    error: str | None = None

    @property
    def usable(self) -> bool:
        return self.error is None and self.status is not None and bool(self.body)


#: Загрузчик получает адрес и возвращает один ответ. Подменяется в проверках.
Fetcher = Callable[[str], Response]


@dataclass
class DomainReport:
    site_id: str
    domain: str
    expected: str
    actual: str
    reasons: tuple[str, ...] = ()
    status: int | None = None
    canonical: str | None = None
    meta: str | None = None
    layers_open: tuple[str, ...] = ()
    layers_closed: tuple[str, ...] = ()

    @property
    def matches(self) -> bool:
        return self.actual == self.expected


@dataclass
class DriftReport:
    domains: list[DomainReport] = field(default_factory=list)

    @property
    def drift(self) -> list[DomainReport]:
        """Домены, чьё состояние не совпало с решением владельца."""
        return [d for d in self.domains if not d.matches]

    @property
    def unmeasured(self) -> list[DomainReport]:
        return [d for d in self.domains if d.actual == UNMEASURED]

    @property
    def ok(self) -> bool:
        return not self.drift

    def summary(self) -> dict:
        return {
            "total": len(self.domains),
            "open": sum(1 for d in self.domains if d.actual == OPEN),
            "closed": sum(1 for d in self.domains if d.actual == CLOSED),
            "mixed": sum(1 for d in self.domains if d.actual == MIXED),
            "unmeasured": len(self.unmeasured),
            "drift": [d.domain for d in self.drift],
        }


def _layers(page: Response, robots: Response) -> dict[str, bool]:
    """Закрыт ли каждый слой. True означает «запрещает индексацию»."""
    meta = _META_ROBOTS.search(page.body)
    return {
        "meta_robots": bool(meta and "noindex" in meta.group(1).lower()),
        "robots_txt": bool(_DISALLOW_ALL.search(robots.body)),
        "x_robots_tag": bool(
            any("noindex" in m.group(1).lower() for m in _X_ROBOTS.finditer(page.headers))
        ),
    }


def inspect_domain(
    site_id: str, domain: str, expected: str, *, fetcher: Fetcher
) -> DomainReport:
    page = fetcher(f"https://{domain}/")
    if not page.usable:
        причина = page.error or (
            "пустое тело ответа" if page.status is not None else "ответ не получен"
        )
        return DomainReport(
            site_id=site_id, domain=domain, expected=expected, actual=UNMEASURED,
            reasons=(f"NOT_MEASURED:{причина}",), status=page.status,
        )
    robots = fetcher(f"https://{domain}/robots.txt")
    if robots.error is not None:
        return DomainReport(
            site_id=site_id, domain=domain, expected=expected, actual=UNMEASURED,
            reasons=(f"NOT_MEASURED:robots.txt {robots.error}",), status=page.status,
        )

    слои = _layers(page, robots)
    закрыты = tuple(n for n in LAYERS if слои[n])
    открыты = tuple(n for n in LAYERS if not слои[n])
    if not открыты:
        факт = CLOSED
    elif not закрыты:
        факт = OPEN
    else:
        факт = MIXED

    причины: list[str] = []
    if факт == MIXED:
        причины.append(f"MIXED_LAYERS:открыты {','.join(открыты)}")
    if факт != expected and факт != MIXED:
        причины.append(f"EXPECTED_{expected}_ACTUAL_{факт}")

    canonical = _CANONICAL.search(page.body)
    canonical_value = canonical.group(1) if canonical else None
    if факт == OPEN:
        # Открытый домен обязан указывать на себя: канонизация открытой витрины
        # на чужой хост отдала бы её вес другому сайту.
        if canonical_value is None:
            причины.append("OPEN_WITHOUT_CANONICAL")
        elif not canonical_value.startswith(f"https://{domain}"):
            причины.append(f"CROSS_DOMAIN_CANONICAL:{canonical_value}")
        if page.status != 200:
            причины.append(f"OPEN_WITH_STATUS_{page.status}")

    meta = _META_ROBOTS.search(page.body)
    return DomainReport(
        site_id=site_id, domain=domain, expected=expected, actual=факт,
        reasons=tuple(причины), status=page.status, canonical=canonical_value,
        meta=meta.group(1) if meta else None,
        layers_open=открыты, layers_closed=закрыты,
    )


def check_portfolio(sites: list[dict], *, fetcher: Fetcher) -> DriftReport:
    """Свести факт с ожиданием по всему портфелю. Синтетические не обходятся."""
    отчёт = DriftReport()
    for site in sites:
        if site.get("synthetic", False):
            continue
        домен = site["base_url"].split("//", 1)[1].rstrip("/")
        отчёт.domains.append(
            inspect_domain(
                site["site_id"], домен, site.get("indexing_expected", CLOSED.lower()).upper(),
                fetcher=fetcher,
            )
        )
    return отчёт


def compare_methods(domain: str, *, get: Fetcher, head: Fetcher) -> str | None:
    """Совпадают ли выводы по GET и HEAD.

    Возвращает описание расхождения или ``None``. Нужна потому, что вывод,
    сделанный по `HEAD`, однажды уже оказался неверным: посредник добавляет
    заголовок только на `GET`.
    """
    g = get(f"https://{domain}/")
    h = head(f"https://{domain}/")
    g_noindex = bool(any("noindex" in m.group(1).lower() for m in _X_ROBOTS.finditer(g.headers)))
    h_noindex = bool(any("noindex" in m.group(1).lower() for m in _X_ROBOTS.finditer(h.headers)))
    if g_noindex != h_noindex:
        return (
            f"{domain}: GET и HEAD расходятся по X-Robots-Tag "
            f"(GET noindex={g_noindex}, HEAD noindex={h_noindex}); "
            "доверять следует GET — им страницу получает читатель"
        )
    return None
