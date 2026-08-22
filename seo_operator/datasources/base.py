"""Data source contract."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceStatus(str, Enum):
    AVAILABLE = "available"
    MISSING_CREDENTIALS = "missing_credentials"
    NETWORK_BLOCKED = "network_blocked"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


@dataclass
class Availability:
    status: SourceStatus
    detail: str
    checked_at: str | None = None

    @property
    def usable(self) -> bool:
        return self.status is SourceStatus.AVAILABLE


class DataSource(ABC):
    """A source of SEO signal.

    Subclasses must not invent data. If a source cannot be reached, ``probe``
    reports why and ``fetch`` raises — it does not return an empty result that a
    downstream report would render as "0 clicks".
    """

    name: str = "unnamed"
    kind: str = "generic"
    required_env: tuple[str, ...] = ()

    @abstractmethod
    def probe(self) -> Availability:
        """Report reachability without returning any data."""

    @abstractmethod
    def fetch(self, site_id: str, **kwargs: Any) -> Any:
        """Return data. Only valid when ``probe().usable`` is True."""

    def _credentials_present(self) -> bool:
        return all(os.environ.get(var) for var in self.required_env)

    def _missing(self) -> list[str]:
        return [var for var in self.required_env if not os.environ.get(var)]


class UnavailableSourceError(RuntimeError):
    """Raised when fetch is attempted on a source that is not usable."""


class CredentialedSource(DataSource):
    """Base for sources gated behind credentials and network reachability."""

    endpoint: str | None = None

    def probe(self) -> Availability:
        missing = self._missing()
        if missing:
            return Availability(
                SourceStatus.MISSING_CREDENTIALS,
                f"не заданы переменные окружения: {', '.join(missing)}",
            )
        return Availability(SourceStatus.AVAILABLE, "credentials present")

    def fetch(self, site_id: str, **kwargs: Any) -> Any:
        availability = self.probe()
        if not availability.usable:
            raise UnavailableSourceError(f"{self.name} недоступен: {availability.detail}")
        return self._fetch(site_id, **kwargs)

    def _fetch(self, site_id: str, **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError(
            f"{self.name}: транспорт не реализован — нет доступа для интеграционной проверки"
        )


@dataclass
class StaticSource(DataSource):
    """A source backed by an explicit in-memory payload.

    Used for fixtures and dry-runs. It is deliberately a distinct class so that
    a fixture can never be mistaken for a live source: everything it returns is
    tagged ``synthetic=True``.
    """

    name: str = "static"
    kind: str = "fixture"
    payload: dict = field(default_factory=dict)
    synthetic: bool = True

    def probe(self) -> Availability:
        return Availability(SourceStatus.AVAILABLE, "in-memory fixture")

    def fetch(self, site_id: str, **kwargs: Any) -> Any:
        data = self.payload.get(site_id, {})
        if isinstance(data, dict):
            return {**data, "synthetic": self.synthetic}
        return data
