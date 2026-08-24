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
    ("excluded_pages", "Исключённые страницы и причины", "search_urls_events"),
    ("external_links", "Внешние ссылки", "external_links"),
    ("technical_issues", "Технические проблемы", "diagnostics"),
)


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
                    limit=20,
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
                limit=20,
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
                )
            )
        except FactoryError as exc:
            out.measurements.append(
                _unmeasured("popular_pages", "Популярные страницы", exc.reason, "ym:pv:pageviews")
            )

        out.measurements.append(_goal_reaches(provider, entry, counter_id, date1, date2))

    # -------------------------------------------------------- Вебмастер
    if not host_id:
        reason = "сайт не зарегистрирован в Вебмастере: домен ещё не развёрнут"
        for key, title, resource in WEBMASTER_RESOURCES:
            out.measurements.append(_unmeasured(key, title, reason, resource))
    else:
        for key, title, resource in WEBMASTER_RESOURCES:
            try:
                payload = provider.get_webmaster_report(host_id, resource)
                out.measurements.append(
                    Measurement(
                        key=key,
                        title=title,
                        measured=True,
                        value=payload.get("payload"),
                        source=resource,
                    )
                )
            except FactoryError as exc:
                out.measurements.append(_unmeasured(key, title, exc.reason, resource))

    return out


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
