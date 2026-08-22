"""Google Search Console. Данные неполны за последние ~3 дня — это учитывается в completeness."""
from __future__ import annotations

from datetime import date
from typing import Any

from .base import Connector, ConnectorResult, register
from . import fixtures


@register("gsc_search_analytics")
class SearchAnalyticsConnector(Connector):
    lag_days = 3

    def fetch(self, start: date, end: date) -> ConnectorResult:
        if not self.spec.get("secret_ref"):
            return self.not_configured("secret_ref на service account")
        if self.spec.get("status") != "available":
            if self.site.site_id.startswith("demo-"):
                return fixtures.gsc_rows(self, start, end)
            return self.not_configured(
                "OAuth/service account в secret store + property в PORTFOLIO_REGISTRY.gsc_property")
        raise NotImplementedError(
            "Реальный транспорт GSC подключается после передачи credentials: "
            "POST webmasters/v3/sites/{property}/searchAnalytics/query, "
            "dimensions=[date,query,page,device], rowLimit=25000, пагинация по startRow."
        )


@register("gsc_url_inspection")
class UrlInspectionConnector(Connector):
    lag_days = 0

    def fetch(self, start: date, end: date) -> ConnectorResult:
        if self.spec.get("status") != "available":
            return self.not_configured("service account с доступом к URL Inspection API")
        raise NotImplementedError("urlInspection.index.inspect — дорогая квота, только priority URLs.")
