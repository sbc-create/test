"""
Базовый контракт коннектора.

Инвариант: коннектор НИКОГДА не возвращает данные без метаданных свежести.
Неконфигурированный источник возвращает NOT_CONFIGURED, а не пустой успех —
иначе пайплайн примет "нет данных" за "нет проблем".
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from .. import config
from ..guardrails import AuthorizationBlocked


class NotConfigured(AuthorizationBlocked):
    """Источник объявлен, но нет credentials/доступа."""


@dataclass
class ConnectorResult:
    source: str
    site_id: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    # Метаданные обязательны — DATA_SOURCE_REGISTRY.observation_metadata_required.
    source_window: str = ""
    timezone: str = "UTC"
    data_freshness: str = "unknown"
    completeness: float = 0.0
    collected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "ok"
    note: str = ""

    def is_usable(self, min_completeness: float = 0.8) -> bool:
        return self.status == "ok" and self.completeness >= min_completeness


class Connector(abc.ABC):
    source_id: str = "abstract"
    lag_days: int = 0

    def __init__(self, site: config.Site, spec: dict[str, Any]) -> None:
        self.site = site
        self.spec = spec

    @property
    def configured(self) -> bool:
        return self.spec.get("status") == "available"

    def complete_through(self, today: date | None = None) -> date:
        """Последняя дата, которую можно считать полной с учётом задержки источника."""
        today = today or datetime.now(timezone.utc).date()
        return today - timedelta(days=self.lag_days)

    def completeness_for(self, observed: date, today: date | None = None) -> float:
        """1.0 для полных дней, линейное затухание внутри окна задержки, 0.0 для сегодня."""
        today = today or datetime.now(timezone.utc).date()
        age = (today - observed).days
        if self.lag_days <= 0:
            return 1.0 if age >= 1 else 0.3
        if age >= self.lag_days:
            return 1.0
        if age <= 0:
            return 0.0
        return round(age / self.lag_days, 3)

    def not_configured(self, needs: str) -> ConnectorResult:
        return ConnectorResult(
            source=self.source_id, site_id=self.site.site_id, rows=[],
            status="NOT_CONFIGURED", completeness=0.0, data_freshness="none",
            timezone=self.site.timezone,
            note=f"Источник не подключён. Требуется: {needs}",
        )

    @abc.abstractmethod
    def fetch(self, start: date, end: date) -> ConnectorResult:
        ...


registry: dict[str, Callable[..., Connector]] = {}


def register(source_id: str) -> Callable[[type[Connector]], type[Connector]]:
    def deco(cls: type[Connector]) -> type[Connector]:
        registry[source_id] = cls
        cls.source_id = source_id
        return cls
    return deco


def build(source_id: str, site: config.Site) -> Connector:
    spec = config.data_sources()["sources"].get(source_id)
    if spec is None:
        raise KeyError(f"Источник '{source_id}' отсутствует в DATA_SOURCE_REGISTRY.yaml")
    cls = registry.get(source_id)
    if cls is None:
        raise KeyError(f"Нет реализации коннектора для '{source_id}'")
    return cls(site, spec)
