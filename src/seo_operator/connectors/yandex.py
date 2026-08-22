"""Яндекс Вебмастер 4.1 и Метрика. Logs API за текущий день не запрашивается."""
from __future__ import annotations

from datetime import date, datetime, timezone

from .base import Connector, ConnectorResult, register
from . import fixtures


@register("yandex_webmaster")
class WebmasterConnector(Connector):
    lag_days = 1

    def fetch(self, start: date, end: date) -> ConnectorResult:
        if self.spec.get("status") != "available":
            if self.site.site_id.startswith("demo-"):
                return fixtures.yandex_query_rows(self, start, end)
            return self.not_configured(
                "OAuth token Вебмастера + host_id в PORTFOLIO_REGISTRY.yandex_webmaster_host_id")
        raise NotImplementedError(
            "GET /user/{uid}/hosts/{host}/search-queries/history, /indexing/history, "
            "/diagnostics, /important-urls, /links/broken, /recrawl/quota"
        )

    def recrawl_budget(self) -> int:
        """Квота перекрауза читается из API, а не угадывается."""
        if self.spec.get("status") != "available":
            return 0
        raise NotImplementedError("GET /recrawl/quota")


@register("yandex_metrika_reports")
class MetrikaReportsConnector(Connector):
    lag_days = 1

    def fetch(self, start: date, end: date) -> ConnectorResult:
        if self.spec.get("status") != "available":
            if self.site.site_id.startswith("demo-"):
                return fixtures.metrika_rows(self, start, end)
            return self.not_configured("OAuth token Метрики + counter_id")
        raise NotImplementedError("GET stat/v1/data")


@register("yandex_metrika_logs")
class MetrikaLogsConnector(Connector):
    lag_days = 1

    def fetch(self, start: date, end: date) -> ConnectorResult:
        today = datetime.now(timezone.utc).date()
        if end >= today:
            return ConnectorResult(
                source=self.source_id, site_id=self.site.site_id, rows=[],
                status="WAITING_DATA", completeness=0.0, data_freshness="incomplete",
                timezone=self.site.timezone,
                note="Визиты текущего дня не завершены. Logs API за today не запрашивается.",
            )
        if self.spec.get("status") != "available":
            return self.not_configured("OAuth token Метрики с доступом к Logs API")
        raise NotImplementedError("POST management/v1/counter/{id}/logrequests")
