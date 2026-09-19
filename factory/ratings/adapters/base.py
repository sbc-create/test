"""Базовый контракт source adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class FetchResult:
    external_id: str
    found: bool
    raw_score: float | None = None
    vote_count: int | None = None
    score_distribution: dict[str, int] | None = None
    source_updated_at: str = ""
    provenance_url: str = ""
    name: str = ""
    russian: str = ""
    mal_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class AdapterError(Exception):
    code: str
    message: str
    retryable: bool = False
    retry_after: float | None = None
    hard_circuit: bool = False

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@runtime_checkable
class SourceAdapter(Protocol):
    source_key: str
    adapter_version: str

    def fetch_by_ids(self, external_ids: list[str]) -> dict[str, FetchResult]:
        """Batch fetch. Keys = requested external ids."""
        ...

    def check_schema(self) -> dict[str, Any]:
        """Bounded schema/contract probe."""
        ...
