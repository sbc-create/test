"""Ежедневный read-only сбор показателей Метрики и Вебмастера.

Модуль ничего не меняет: ни счётчика, ни цели, ни сайта в Вебмастере, ни
sitemap. Он собирает тринадцать групп показателей, названных в задании, и
складывает их в артефакт.

Главное свойство — честность пустоты. Показатель, который не удалось измерить,
попадает в отчёт как ``measured: false`` с причиной. Ноль означает «Яндекс
вернул ноль», и ничего больше: отчёт, в котором «0 визитов» и «счётчика ещё
нет» выглядят одинаково, хуже отсутствующего отчёта.
"""

from __future__ import annotations

import datetime as _dt
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from factory.analytics import registry
from factory.analytics.yandex import YandexAnalyticsProvider
from factory.errors import FactoryError

NOT_MEASURED = "не измерено"


@dataclass
class Measurement:
    """Один показатель. Либо значение, либо причина его отсутствия — не оба."""

    key: str
    title: str
    measured: bool = False
    value: object = None
    reason: str = ""
    source: str = ""
    sampled: bool | None = None
    sample_share: float | None = None
    #: Сколько строк разбивки запрошено. Страница вне списка — «вне первых N»,
    #: а не ноль: без этого числа отсутствие строки читается как нулевой трафик.
    top_n: int | None = None

    def as_dict(self) -> dict:
        out = {
            "key": self.key,
            "title": self.title,
            "measured": self.measured,
            "source": self.source,
        }
        if self.measured:
            out["value"] = self.value
            if self.sampled is not None:
                out["sampled"] = self.sampled
                out["sample_share"] = self.sample_share
            if self.top_n is not None:
                out["top_n"] = self.top_n
        else:
            out["value"] = NOT_MEASURED
            out["reason"] = self.reason
        return out


@dataclass
class DomainCollection:
    domain: str
    counter_id: int | None
    host_id: str | None
    measurements: list[Measurement] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "domain": self.domain,
            "counter_id": self.counter_id,
            "webmaster_host_id": self.host_id,
            "measured_count": sum(1 for m in self.measurements if m.measured),
            "total_count": len(self.measurements),
            "measurements": [m.as_dict() for m in self.measurements],
        }


#: Тринадцать групп задания. Каждая строка — (ключ, заголовок, откуда берётся).
METRIKA_TOTALS = (
    ("visitors", "Посетители", "ym:s:users"),
    ("visits", "Визиты", "ym:s:visits"),
    ("page_depth", "Глубина просмотра", "ym:s:pageDepth"),
    ("avg_visit_duration", "Время на сайте, сек", "ym:s:avgVisitDurationSeconds"),
    ("bounce_rate", "Отказы, %", "ym:s:bounceRate"),
)
METRIKA_BREAKDOWNS = (
    ("traffic_sources", "Источники трафика", "ym:s:lastsignTrafficSource"),
    ("search_engines", "Поисковые системы", "ym:s:lastsignSearchEngine"),
    ("landing_pages", "Входные страницы", "ym:s:startURLPath"),
)
WEBMASTER_RESOURCES = (
    ("pages_in_search", "Страницы в поиске", "search_urls_in_search"),
    # Заголовок исправлен 2026-10-10. Ресурс `search_urls_events` отдаёт ЛЕНТУ
    # СОБЫТИЙ страниц, а не перечень исключённых: у всех пятидесяти образцов по
    # четырём доменам (animeg0.site, animedia.icu, yummyani7.site,
    # lordserial33.biz) поле `event` равно `APPEARED_IN_SEARCH`, то есть
    # «страница ПОЯВИЛАСЬ в поиске», и `excluded_url_status` пуст. Прежний
    # заголовок приглашал прочитать 1507 появлений как 1507 исключений — а это
    # противоположный вывод о том, индексируется ли сайт.
    ("excluded_pages", "События страниц в поиске: появления и исключения", "search_urls_events"),
    ("external_links", "Внешние ссылки", "external_links"),
    ("technical_issues", "Технические проблемы", "diagnostics"),
)


#: Сколько строк просит каждая разбивка (источники, поисковики, страницы).
BREAKDOWN_LIMIT = 20


def _webmaster_unbound_reason(entry: dict) -> str:
    """Почему Вебмастер не читается — словами реестра, а не догадкой.

    Прежний текст «домен ещё не развёрнут» стоял у всех доменов без host_id,
    включая работающие: решение «ждать выкладки» принималось там, где ждать
    нечего, а нужна привязка сайта в Вебмастере.
    """
    webmaster = entry.get("webmaster") or {}
    if webmaster.get("enabled") is False:
        return "Вебмастер для домена выключен в реестре аналитики"
    status = webmaster.get("verification_status") or "не записан"
    checked = entry.get("last_checked_at") or "ни разу"
    return (
        "сайт не привязан к Вебмастеру: host_id в реестре аналитики пуст, "
        f"статус подтверждения {status} (последняя сверка реестра: {checked})"
    )


def _разметить_события(resource: str, payload):
    """Разбор ленты событий страниц по типу — внутри самого измерения.

    Зачем. Лента `search_urls_events` несёт и появления страниц в поиске, и
    исключения, а наружу отдавался только общий `count`. Прочитать его как
    «исключено N страниц» — ровно та ошибка, в которую приглашал прежний
    заголовок: 1507 событий у animeg0.site оказались 1507 ПОЯВЛЕНИЯМИ.

    Разбор считается по `samples`, а не по всей ленте, и называется именно так
    (`samples_by_event`, `samples_total`): API отдаёт образцы, а не весь список,
    и выдавать долю образцов за долю ленты нельзя.
    """
    if resource != "search_urls_events" or not isinstance(payload, dict):
        return payload
    образцы = payload.get("samples")
    if not isinstance(образцы, list):
        return payload
    по_событию: dict[str, int] = {}
    for с in образцы:
        если = str((с or {}).get("event") or "UNKNOWN")
        по_событию[если] = по_событию.get(если, 0) + 1
    размеченное = dict(payload)
    размеченное["samples_total"] = len(образцы)
    размеченное["samples_by_event"] = dict(sorted(по_событию.items()))
    размеченное["count_note"] = (
        "count — число СОБЫТИЙ в ленте (появления и исключения вместе), а не "
        "число исключённых страниц; разбор по типу считан по образцам"
    )
    return размеченное


def _unmeasured(key: str, title: str, reason: str, source: str) -> Measurement:
    return Measurement(key=key, title=title, measured=False, reason=reason, source=source)


def collect_domain(
    provider: YandexAnalyticsProvider,
    entry: dict,
    *,
    date1: str,
    date2: str,
) -> DomainCollection:
    domain = entry["domain"]
    counter_id = entry.get("counter_id")
    host_id = (entry.get("webmaster") or {}).get("host_id")
    out = DomainCollection(domain=domain, counter_id=counter_id, host_id=host_id)

    # ---------------------------------------------------------- Метрика
    if not counter_id:
        reason = "счётчик Метрики не создан"
        for key, title, source in METRIKA_TOTALS + METRIKA_BREAKDOWNS:
            out.measurements.append(_unmeasured(key, title, reason, source))
        out.measurements.append(
            _unmeasured("popular_pages", "Популярные страницы", reason, "ym:pv:pageviews")
        )
        out.measurements.append(
            _unmeasured("goal_reaches", "Достижение целей", reason, "ym:s:goal<id>reaches")
        )
        for key, title, source in (*EXTRA_METRIKA, *COUNTER_EXTRAS):
            out.measurements.append(_unmeasured(key, title, reason, source))
    else:
        metrics = [source for _, _, source in METRIKA_TOTALS]
        try:
            report = provider.get_metrica_report(
                counter_id, date1=date1, date2=date2, metrics=metrics
            )
            totals = report.get("totals") or []
            for index, (key, title, source) in enumerate(METRIKA_TOTALS):
                if index < len(totals):
                    out.measurements.append(
                        Measurement(
                            key=key,
                            title=title,
                            measured=True,
                            value=totals[index],
                            source=source,
                            sampled=report.get("sampled"),
                            sample_share=report.get("sample_share"),
                        )
                    )
                else:
                    out.measurements.append(
                        _unmeasured(
                            key, title, "Метрика не вернула значение для этой метрики", source
                        )
                    )
        except FactoryError as exc:
            for key, title, source in METRIKA_TOTALS:
                out.measurements.append(_unmeasured(key, title, exc.reason, source))

        for key, title, dimension in METRIKA_BREAKDOWNS:
            try:
                report = provider.get_metrica_report(
                    counter_id,
                    date1=date1,
                    date2=date2,
                    metrics=["ym:s:visits"],
                    dimensions=[dimension],
                    limit=BREAKDOWN_LIMIT,
                )
                out.measurements.append(
                    Measurement(
                        key=key,
                        title=title,
                        measured=True,
                        value=report.get("data"),
                        source=dimension,
                        sampled=report.get("sampled"),
                        sample_share=report.get("sample_share"),
                        top_n=BREAKDOWN_LIMIT,
                    )
                )
            except FactoryError as exc:
                out.measurements.append(_unmeasured(key, title, exc.reason, dimension))

        # Просмотры используют префикс ym:pv: и не смешиваются с ym:s: в одном
        # запросе — это правило контракта, а не стилистика.
        try:
            report = provider.get_metrica_report(
                counter_id,
                date1=date1,
                date2=date2,
                metrics=["ym:pv:pageviews"],
                dimensions=["ym:pv:URLPath"],
                limit=BREAKDOWN_LIMIT,
            )
            out.measurements.append(
                Measurement(
                    key="popular_pages",
                    title="Популярные страницы",
                    measured=True,
                    value=report.get("data"),
                    source="ym:pv:pageviews",
                    sampled=report.get("sampled"),
                    sample_share=report.get("sample_share"),
                    top_n=BREAKDOWN_LIMIT,
                )
            )
        except FactoryError as exc:
            out.measurements.append(
                _unmeasured("popular_pages", "Популярные страницы", exc.reason, "ym:pv:pageviews")
            )

        out.measurements.append(_goal_reaches(provider, entry, counter_id, date1, date2))
        out.measurements.extend(_metrika_daily_and_search(provider, counter_id, date1, date2))
        out.measurements.append(_counter_passport(provider, counter_id))
        out.measurements.extend(_metrika_today(provider, counter_id))

    # -------------------------------------------------------- Вебмастер
    if not host_id:
        reason = _webmaster_unbound_reason(entry)
        for key, title, resource in WEBMASTER_RESOURCES:
            out.measurements.append(_unmeasured(key, title, reason, resource))
        out.measurements.append(
            _unmeasured("popular_queries", "Популярные запросы", reason, "popular_queries")
        )
    else:
        for key, title, resource in WEBMASTER_RESOURCES:
            try:
                payload = provider.get_webmaster_report(host_id, resource)
                out.measurements.append(
                    Measurement(
                        key=key,
                        title=title,
                        measured=True,
                        value=_разметить_события(resource, payload.get("payload")),
                        source=resource,
                    )
                )
            except FactoryError as exc:
                out.measurements.append(_unmeasured(key, title, exc.reason, resource))
        out.measurements.append(_popular_queries(provider, host_id))

    return out


#: Окно суточных рядов: 14 дней, чтобы день сравнивался с тем же днём прошлой
#: недели (2026-10-10: при окне 7 дней 01–02.10 для сравнения с 08–09.10 не было).
DAILY_WINDOW_FROM = "14daysAgo"

#: Индикаторы популярных запросов (SRC-YA-WEBMASTER-POPULAR-QUERIES). До
#: 2026-10-10 запрашивались только показы — клики не приходили, и кликабельность
#: не была измерена.
QUERY_INDICATORS = ["TOTAL_SHOWS", "TOTAL_CLICKS", "AVG_SHOW_POSITION", "AVG_CLICK_POSITION"]

#: Добавлено 2026-10-09 для цели «пользователей в сутки» и разбора поисковых
#: входов: суточная разбивка с признаком робота и поисковые входы по страницам.
#: Паспорт счётчика и неполные текущие сутки (2026-10-10) — для «не измерено»
#: у доменов без счётчика.
COUNTER_EXTRAS = (
    ("counter_passport", "Паспорт счётчика", "GET /management/v1/counter/{counterId}"),
    ("today_users", "Сегодня (неполные сутки): пользователи", "ym:s:date × ym:s:isRobot"),
    (
        "today_search",
        "Сегодня (неполные сутки): поисковые визиты",
        "ym:s:date × ym:s:lastsignTrafficSource × ym:s:lastsignSearchEngineRoot",
    ),
)

EXTRA_METRIKA = (
    (
        "daily_users",
        "Пользователи по дням (с признаком робота)",
        "ym:s:users × ym:s:date × ym:s:isRobot",
    ),
    (
        "search_landing_pages",
        "Поисковые входы по страницам",
        "ym:s:visits × lastsignTrafficSource × startURLPath",
    ),
    (
        "daily_search",
        "Поисковые визиты и пользователи по дням и поисковым системам",
        "ym:s:users, ym:s:visits × ym:s:date × lastsignTrafficSource × lastsignSearchEngineRoot",
    ),
)


def _metrika_daily_and_search(
    provider, counter_id: int, date1: str, date2: str
) -> list[Measurement]:
    """Суточные пользователи и поисковые входы по страницам. Только чтение.

    Роботы не отфильтрованы запросом: строки разбиты по ym:s:isRobot, и людей
    считает читатель отчёта по значению признака из ответа. Поисковые входы —
    строки с источником organic из разбивки «источник × страница» (первые 200).
    """
    out: list[Measurement] = []
    try:
        report = provider.get_metrica_report(
            counter_id,
            date1=DAILY_WINDOW_FROM,
            date2=date2,
            metrics=["ym:s:users", "ym:s:visits"],
            dimensions=["ym:s:date", "ym:s:isRobot"],
            limit=100,
        )
        out.append(
            Measurement(
                key="daily_users",
                title=EXTRA_METRIKA[0][1],
                measured=True,
                value=report.get("data"),
                source=EXTRA_METRIKA[0][2],
                sampled=report.get("sampled"),
                sample_share=report.get("sample_share"),
            )
        )
    except FactoryError as exc:
        out.append(_unmeasured("daily_users", EXTRA_METRIKA[0][1], exc.reason, EXTRA_METRIKA[0][2]))
    try:
        report = provider.get_metrica_report(
            counter_id,
            date1=date1,
            date2=date2,
            metrics=["ym:s:visits", "ym:s:users"],
            dimensions=["ym:s:lastsignTrafficSource", "ym:s:startURLPath"],
            limit=200,
        )
        rows = [
            r
            for r in report.get("data") or []
            if ((r.get("dimensions") or [{}])[0].get("id") == "organic")
        ]
        out.append(
            Measurement(
                key="search_landing_pages",
                title=EXTRA_METRIKA[1][1],
                measured=True,
                value=rows,
                source=EXTRA_METRIKA[1][2],
                sampled=report.get("sampled"),
                sample_share=report.get("sample_share"),
                top_n=200,
            )
        )
    except FactoryError as exc:
        out.append(
            _unmeasured(
                "search_landing_pages", EXTRA_METRIKA[1][1], exc.reason, EXTRA_METRIKA[1][2]
            )
        )
    try:
        report = provider.get_metrica_report(
            counter_id,
            date1=DAILY_WINDOW_FROM,
            date2=date2,
            metrics=["ym:s:users", "ym:s:visits"],
            dimensions=[
                "ym:s:date",
                "ym:s:lastsignTrafficSource",
                "ym:s:lastsignSearchEngineRoot",
            ],
            limit=1000,
        )
        rows = [
            r
            for r in report.get("data") or []
            if ((r.get("dimensions") or [{}, {}])[1].get("id") == "organic")
        ]
        out.append(
            Measurement(
                key="daily_search",
                title=EXTRA_METRIKA[2][1],
                measured=True,
                value=rows,
                source=EXTRA_METRIKA[2][2],
                sampled=report.get("sampled"),
                sample_share=report.get("sample_share"),
            )
        )
    except FactoryError as exc:
        out.append(
            _unmeasured("daily_search", EXTRA_METRIKA[2][1], exc.reason, EXTRA_METRIKA[2][2])
        )
    return out


def _counter_passport(provider, counter_id: int) -> Measurement:
    """Часовой пояс и сайт счётчика (SRC-YA-METRIKA-COUNTER-GET). Только чтение.

    ym:s:date считается в часовом поясе счётчика; без паспорта «сутки по Москве»
    — допущение, а не факт.
    """
    getter = getattr(provider, "get_counter", None)
    if getter is None:
        return _unmeasured(
            "counter_passport",
            "Паспорт счётчика",
            "провайдер не читает паспорт счётчика",
            "GET /management/v1/counter/{counterId}",
        )
    try:
        counter = getter(counter_id)
        return Measurement(
            key="counter_passport",
            title="Паспорт счётчика",
            measured=True,
            value={
                k: counter.get(k)
                for k in ("id", "site", "status", "time_zone_name", "time_zone_offset")
            },
            source="GET /management/v1/counter/{counterId}",
        )
    except FactoryError as exc:
        return _unmeasured(
            "counter_passport",
            "Паспорт счётчика",
            exc.reason,
            "GET /management/v1/counter/{counterId}",
        )


def _metrika_today(provider, counter_id: int) -> list[Measurement]:
    """Неполные текущие сутки: люди/роботы и поисковые визиты по системам.

    Отдельный показатель с временем отсечения: смешивать неполный день с полными
    нельзя.
    """
    отсечка = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: list[Measurement] = []
    for key, title, dims in (
        ("today_users", "Сегодня (неполные сутки): пользователи", ["ym:s:date", "ym:s:isRobot"]),
        (
            "today_search",
            "Сегодня (неполные сутки): поисковые визиты",
            ["ym:s:date", "ym:s:lastsignTrafficSource", "ym:s:lastsignSearchEngineRoot"],
        ),
    ):
        try:
            report = provider.get_metrica_report(
                counter_id,
                date1="today",
                date2="today",
                metrics=["ym:s:users", "ym:s:visits"],
                dimensions=dims,
                limit=200,
            )
            out.append(
                Measurement(
                    key=key,
                    title=f"{title}, отсечка {отсечка}",
                    measured=True,
                    value=report.get("data"),
                    source=" × ".join(dims),
                    sampled=report.get("sampled"),
                    sample_share=report.get("sample_share"),
                )
            )
        except FactoryError as exc:
            out.append(_unmeasured(key, title, exc.reason, " × ".join(dims)))
    return out


def _popular_queries(provider, host_id: str) -> Measurement:
    """Популярные запросы Вебмастера (показы, клики, позиция). Только чтение."""
    try:
        payload = provider.get_webmaster_report(
            host_id,
            "popular_queries",
            {"order_by": "TOTAL_SHOWS", "query_indicator": QUERY_INDICATORS},
        )
        return Measurement(
            key="popular_queries",
            title="Популярные запросы",
            measured=True,
            value=payload.get("payload"),
            source="popular_queries",
        )
    except FactoryError as exc:
        return _unmeasured("popular_queries", "Популярные запросы", exc.reason, "popular_queries")


def _goal_reaches(provider, entry: dict, counter_id: int, date1: str, date2: str) -> Measurement:
    """Достижения целей.

    Метрика адресуется числовым ``goal_id``, который Метрика присваивает при
    создании цели. В реестре хранятся идентификаторы событий, а не goal_id,
    поэтому пока цели не созданы и их идентификаторы не получены из API,
    показатель честно остаётся неизмеренным.
    """
    goals = entry.get("goals") or []
    if not goals:
        return _unmeasured(
            "goal_reaches", "Достижение целей", "цели не созданы", "ym:s:goal<id>reaches"
        )
    try:
        mapping = provider.list_goal_ids(counter_id)
    except FactoryError as exc:
        return _unmeasured("goal_reaches", "Достижение целей", exc.reason, "ym:s:goal<id>reaches")

    if not mapping:
        return _unmeasured(
            "goal_reaches",
            "Достижение целей",
            "Метрика не вернула идентификаторы целей",
            "ym:s:goal<id>reaches",
        )

    # Лимит Reporting API — 20 метрик на запрос; целей девять, но ограничение
    # проверяется явно, чтобы расширение набора не сломало сбор молча.
    names = sorted(mapping)[:20]
    metrics = [f"ym:s:goal{mapping[name]}reaches" for name in names]
    try:
        report = provider.get_metrica_report(counter_id, date1=date1, date2=date2, metrics=metrics)
    except FactoryError as exc:
        return _unmeasured("goal_reaches", "Достижение целей", exc.reason, "ym:s:goal<id>reaches")

    totals = report.get("totals") or []
    return Measurement(
        key="goal_reaches",
        title="Достижение целей",
        measured=True,
        value=dict(zip(names, totals, strict=False)),
        source="ym:s:goal<id>reaches",
        sampled=report.get("sampled"),
        sample_share=report.get("sample_share"),
    )


def collect(
    *,
    date1: str = "7daysAgo",
    date2: str = "yesterday",
    provider: YandexAnalyticsProvider | None = None,
    artifacts_dir: Path | None = None,
) -> dict:
    """Собирает показатели по всем доменам реестра и пишет артефакт."""
    provider = provider or YandexAnalyticsProvider(dry_run=True)
    entries = registry.load()["properties"]
    collections = [collect_domain(provider, entry, date1=date1, date2=date2) for entry in entries]

    report = {
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "period": {"date1": date1, "date2": date2},
        "read_only": True,
        "domains": [c.as_dict() for c in collections],
    }
    total = sum(c.as_dict()["total_count"] for c in collections)
    measured = sum(c.as_dict()["measured_count"] for c in collections)
    report["summary"] = {
        "measured": measured,
        "not_measured": total - measured,
        "total": total,
        # Без этой строки отчёт из одних «не измерено» выглядит как отчёт с
        # нулями, и разница теряется ровно там, где она важнее всего.
        "note": (
            f"{total - measured} показателей из {total} не измерены. "
            "Это не нули: причина названа у каждого."
        ),
    }

    if artifacts_dir is not None:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = artifacts_dir / f"analytics-{time.strftime('%Y-%m-%d', time.gmtime())}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["artifact"] = str(path)
    return report
