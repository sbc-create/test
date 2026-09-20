"""Модели данных централизованного ratings pipeline."""

from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def payload_sha256(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SourceState(str, enum.Enum):
    READY = "READY"
    UNVERIFIED_DISABLED = "UNVERIFIED_DISABLED"
    BLOCKED = "BLOCKED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    DISABLED = "DISABLED"


class MappingState(str, enum.Enum):
    VERIFIED = "VERIFIED"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"


class MappingMethod(str, enum.Enum):
    SHIKIMORI_ID = "SHIKIMORI_ID"
    MAL_ID_CROSSWALK = "MAL_ID_CROSSWALK"
    EXACT_TITLE_YEAR_KIND_SEASON = "EXACT_TITLE_YEAR_KIND_SEASON"
    FUZZY_CANDIDATE = "FUZZY_CANDIDATE"  # только для review, не auto-publish
    MANUAL = "MANUAL"
    NONE = "NONE"


class ValidationState(str, enum.Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    NOT_FOUND = "NOT_FOUND"
    UNCHANGED = "UNCHANGED"


class FreshnessState(str, enum.Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    MISSING = "MISSING"
    CONFLICT = "CONFLICT"
    UNVERIFIED = "UNVERIFIED"


class QueueItemState(str, enum.Enum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    DONE = "DONE"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"
    SKIPPED = "SKIPPED"
    DEFERRED_CAPACITY = "DEFERRED_CAPACITY"


class HealthState(str, enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


@dataclass
class SourceRecord:
    source_key: str
    display_name: str
    canonical_origin: str
    adapter_version: str
    state: SourceState
    score_scale: float = 10.0
    supports_vote_count: bool = False
    supports_distribution: bool = False
    max_rps: float = 2.0
    max_requests_per_minute: int = 60
    freshness_policy: dict[str, Any] = field(default_factory=dict)
    legal_access_evidence: str = ""
    last_schema_check: str = ""
    last_successful_fetch: str = ""
    health_state: HealthState = HealthState.UNKNOWN
    attribution_gate: str = ""  # CONTRACT_GATE if attribution rules unknown
    enabled: bool = False

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        d["health_state"] = self.health_state.value
        return d


@dataclass
class TitleSourceMapping:
    canonical_title_id: str
    source_key: str
    external_title_id: str
    external_url: str = ""
    mapping_method: MappingMethod = MappingMethod.NONE
    confidence: float = 0.0
    evidence: str = ""
    verified_at: str = ""
    state: MappingState = MappingState.REVIEW

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["mapping_method"] = self.mapping_method.value
        d["state"] = self.state.value
        return d


@dataclass
class RatingObservation:
    canonical_title_id: str
    source_key: str
    external_id: str
    raw_score: float | None
    source_scale: float
    normalized_score: float | None
    vote_count: int | None
    score_distribution: dict[str, int] | None
    source_updated_at: str
    observed_at: str
    payload_sha256: str
    adapter_version: str
    provenance_url: str
    mapping_method: MappingMethod
    validation_state: ValidationState
    run_id: str = ""
    idempotency_key: str = ""

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["mapping_method"] = self.mapping_method.value
        d["validation_state"] = self.validation_state.value
        return d


@dataclass
class RatingCurrent:
    canonical_title_id: str
    source_key: str
    observation_id: int | None
    raw_score: float | None
    normalized_score: float | None
    vote_count: int | None
    freshness: FreshnessState
    observed_at: str
    provenance_url: str
    payload_sha256: str
    adapter_version: str
    external_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["freshness"] = self.freshness.value
        return d


@dataclass
class CatalogTitle:
    """Кандидат из каталога для планирования очереди."""

    canonical_title_id: str
    title: str = ""
    original_title: str = ""
    russian_title: str = ""
    aliases: tuple[str, ...] = ()
    year: int | None = None
    kind: str = ""
    season: str | None = None
    episode_count: int | None = None
    is_ongoing: bool = False
    has_new_episode: bool = False
    is_seasonal: bool = False
    days_since_release: int | None = None
    on_home_or_top: bool = False
    is_popular: bool = False
    external_ids: dict[str, str] = field(default_factory=dict)
    has_rating: bool = False
    first_seen_at: str = ""
    is_new_catalog: bool = False

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["aliases"] = list(self.aliases)
        return d
