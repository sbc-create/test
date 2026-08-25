"""
Яндекс Метрика: Management API, Reports API, Logs API (ТЗ §3.1).

Три вещи, которые здесь закодированы намеренно:

1. Logs API не запрашивается за текущий день — визиты не завершены.
2. Вебвизор и свободный текст не собираются, пока владелец не изменил политику
   отдельным решением; попытка запросить такие поля отклоняется.
3. Разделение по поисковым системам делается на уровне запроса, а не постфактум:
   Яндекс, Google и прочие обязаны показываться отдельно (ТЗ §2).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from ..guardrails import AuthorizationBlocked
from ..metrics.north_star import Engine
from ..secrets import metrika_ref
from ..statuses import Status
from .base import Connector, ConnectorResult, register
from . import fixtures

# Поля Logs API, требующие отдельной правовой политики (ТЗ §3.1, §12).
RESTRICTED_LOG_FIELDS = frozenset({
    "ym:s:clientID", "ym:s:networkType", "ym:pv:URL", "ym:s:searchPhrase",
    "ym:s:ipAddress", "ym:s:UTMContent",
})

# Соответствие поисковой системы Метрики и наших движков.
SEARCH_ENGINE_MAP = {
    "yandex": Engine.YANDEX,
    "ya": Engine.YANDEX,
    "google": Engine.GOOGLE,
}

# Источники, исключаемые из organic_daily_unique.
ORGANIC_TRAFFIC_SOURCE = "organic"


def map_engine(search_engine_root: str) -> Engine:
    key = (search_engine_root or "").strip().lower()
    for marker, engine in SEARCH_ENGINE_MAP.items():
        if marker in key:
            return engine
    return Engine.OTHER


@register("yandex_metrika_management")
class MetrikaManagementConnector(Connector):
    """Состояние счётчиков и целей. Нужен для Access Auditor, а не для метрик."""

    lag_days = 0

    def fetch(self, start: date, end: date) -> ConnectorResult:
        if self.spec.get("status") != "available":
            if self.site.site_id.startswith("demo-"):
                return ConnectorResult(
                    source=self.source_id, site_id=self.site.site_id,
                    rows=[{"counter_id": 0, "name": "demo fixture", "goals": 2,
                           "webvisor_enabled": False, "data_flowing": True}],
                    source_window=f"{start}..{end}", timezone=self.site.timezone,
                    data_freshness="live", completeness=1.0,
                    note="FIXTURE DATA — не производственные показатели.")
            return self.not_configured(
                f"{metrika_ref(self.site.site_id)} в Secret Hub + counter_id в PORTFOLIO_REGISTRY")
        raise NotImplementedError(
            "GET management/v1/counters и management/v1/counter/{id}/goals — "
            "проверка прав, целей и факта поступления данных.")

    def counter_health(self) -> dict[str, Any]:
        """Для Access Auditor: счётчик с ID, но без данных — это BLOCKED, а не READY."""
        result = self.fetch(date.today(), date.today())
        if result.status != "ok":
            return {"state": "BLOCKED", "detail": result.note}
        row = result.rows[0] if result.rows else {}
        if not row.get("data_flowing"):
            return {"state": "BLOCKED", "detail": "счётчик заведён, но данные не поступают"}
        if row.get("webvisor_enabled"):
            return {"state": "READY",
                    "detail": "данные идут; Вебвизор включён — сбор свободного текста запрещён политикой"}
        return {"state": "READY", "detail": f"данные идут, целей: {row.get('goals', 0)}"}


@register("yandex_metrika_organic")
class MetrikaOrganicConnector(Connector):
    """
    Суточные уники органики с разбивкой по поисковым системам.
    Это единственный источник organic_daily_unique.
    """

    lag_days = 1

    def fetch(self, start: date, end: date) -> ConnectorResult:
        today = datetime.now(timezone.utc).date()
        if end >= today:
            end = today - timedelta(days=1)
            if end < start:
                return ConnectorResult(
                    source=self.source_id, site_id=self.site.site_id, rows=[],
                    status="WAITING_DATA", completeness=0.0, data_freshness="incomplete",
                    timezone=self.site.timezone,
                    note="Запрошен только текущий день: он не полон и в показатель не входит.")

        if self.spec.get("status") != "available":
            if self.site.site_id.startswith("demo-"):
                return fixtures.metrika_organic_rows(self, start, end)
            return self.not_configured(
                f"{metrika_ref(self.site.site_id)} в Secret Hub + counter_id")

        raise NotImplementedError(
            "GET stat/v1/data с metrics=ym:s:users, "
            "dimensions=ym:s:date,ym:s:searchEngineRoot, "
            "filters=ym:s:lastSignTrafficSource=='organic', "
            "group=day, accuracy=full. Разбивка по движкам берётся из измерения, "
            "а не восстанавливается постфактум.")


@register("yandex_metrika_logs")
class MetrikaLogsConnector(Connector):
    """Детальный разбор визитов за ПРЕДЫДУЩИЙ день, когда он действительно нужен."""

    lag_days = 1

    def fetch(self, start: date, end: date, fields: Iterable[str] = ()) -> ConnectorResult:
        today = datetime.now(timezone.utc).date()
        if end >= today:
            return ConnectorResult(
                source=self.source_id, site_id=self.site.site_id, rows=[],
                status="WAITING_DATA", completeness=0.0, data_freshness="incomplete",
                timezone=self.site.timezone,
                note="Визиты текущего дня не завершены. Logs API за today не запрашивается.")

        restricted = sorted(set(fields) & RESTRICTED_LOG_FIELDS)
        if restricted:
            raise AuthorizationBlocked(
                f"Поля {restricted} требуют отдельной правовой политики владельца "
                "(персональные данные и свободный текст).",
                {"site": self.site.site_id, "fields": restricted,
                 "needs": "правовая политика сбора ПДн", "status": Status.BLOCKED_OWNER_DECISION.value})

        if self.spec.get("status") != "available":
            return self.not_configured(f"{metrika_ref(self.site.site_id)} с доступом к Logs API")

        raise NotImplementedError(
            "POST management/v1/counter/{id}/logrequests, затем опрос статуса и "
            "выгрузка частями. Соблюдать лимит одновременных запросов на счётчик.")
