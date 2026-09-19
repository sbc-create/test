"""Конфигурация ratings ingestion. Все операционные лимиты — из env/конфига."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from factory.paths import PATHS


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return int(raw)


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return float(raw)


@dataclass(frozen=True)
class RatingsConfig:
    daily_success_target: int = 500
    daily_candidate_cap: int = 750
    initial_canary_limit: int = 100
    batch_size: int = 50
    max_rps: float = 2.0
    max_requests_per_minute: int = 60
    user_agent: str = "site-factory-ratings/1.0 (+ratings-ingestion; contact=ops)"
    shikimori_graphql_url: str = "https://shikimori.io/api/graphql"
    # Freshness (hours)
    freshness_ongoing_hours: int = 24
    freshness_recently_finished_days: int = 7
    freshness_popular_days: int = 14
    freshness_archive_min_days: int = 30
    freshness_archive_max_days: int = 90
    freshness_not_found_min_days: int = 14
    freshness_not_found_max_days: int = 30
    # Resilience
    max_retries: int = 3
    circuit_breaker_threshold: int = 5
    circuit_breaker_cooldown_sec: float = 300.0
    lease_seconds: int = 120
    heartbeat_seconds: int = 30
    # Paths (isolated; never production DB)
    db_path: Path | None = None
    evidence_dir: Path | None = None
    lock_name: str = "ratings-ingestion"

    @classmethod
    def from_env(cls, *, db_path: Path | None = None, evidence_dir: Path | None = None) -> "RatingsConfig":
        root = PATHS.root
        return cls(
            daily_success_target=_int("RATINGS_DAILY_SUCCESS_TARGET", 500),
            daily_candidate_cap=_int("RATINGS_DAILY_CANDIDATE_CAP", 750),
            initial_canary_limit=_int("RATINGS_INITIAL_CANARY_LIMIT", 100),
            batch_size=_int("RATINGS_BATCH_SIZE", 50),
            max_rps=_float("RATINGS_MAX_RPS", 2.0),
            max_requests_per_minute=_int("RATINGS_MAX_REQUESTS_PER_MINUTE", 60),
            user_agent=os.environ.get(
                "RATINGS_USER_AGENT",
                "site-factory-ratings/1.0 (+ratings-ingestion; contact=ops)",
            ),
            shikimori_graphql_url=os.environ.get(
                "RATINGS_SHIKIMORI_GRAPHQL_URL",
                "https://shikimori.io/api/graphql",
            ),
            db_path=db_path or Path(
                os.environ.get(
                    "RATINGS_DB_PATH",
                    str(root / "var" / "ratings" / "ratings.sqlite"),
                )
            ),
            evidence_dir=evidence_dir or Path(
                os.environ.get(
                    "RATINGS_EVIDENCE_DIR",
                    str(root / "artifacts" / "evidence" / "ratings-ingestion-01"),
                )
            ),
            lock_name=os.environ.get("RATINGS_LOCK_NAME", "ratings-ingestion"),
        )


#: Приоритеты очереди (меньше = раньше). Жёсткий порядок из ТЗ §8.
PRIORITY_NEW_CATALOG = 10
PRIORITY_ONGOING_NEW_EPISODE = 20
PRIORITY_ACTIVE_SEASONAL = 30
PRIORITY_NEW_30_DAYS = 40
PRIORITY_HOME_TOP_NO_RATING = 50
PRIORITY_POPULAR_NO_RATING = 60
PRIORITY_RELEASE_180_DAYS = 70
PRIORITY_STALE_REFRESH = 80
PRIORITY_ARCHIVE = 90

PRIORITY_LABELS = {
    PRIORITY_NEW_CATALOG: "new_catalog",
    PRIORITY_ONGOING_NEW_EPISODE: "ongoing_new_episode",
    PRIORITY_ACTIVE_SEASONAL: "active_seasonal",
    PRIORITY_NEW_30_DAYS: "new_30_days",
    PRIORITY_HOME_TOP_NO_RATING: "home_top_no_rating",
    PRIORITY_POPULAR_NO_RATING: "popular_no_rating",
    PRIORITY_RELEASE_180_DAYS: "release_180_days",
    PRIORITY_STALE_REFRESH: "stale_refresh",
    PRIORITY_ARCHIVE: "archive",
}
