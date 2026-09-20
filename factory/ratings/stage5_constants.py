"""Stage 5R constants — dual independent caps."""

from __future__ import annotations

STAGE = "RATINGS-INGESTION-05R"
SOURCE_ALLOWED = "shikimori"
SOURCE_DISABLED = ("amd_online", "amd.online", "animemedia", "imdb", "kinopoisk")

# Two independent limits (must not collapse claim==accepted)
CANDIDATE_ATTEMPT_CAP = 150
ACCEPTED_HARD_CAP = 100
ACCEPTED_TARGET = ACCEPTED_HARD_CAP  # alias
CANDIDATE_CAP = CANDIDATE_ATTEMPT_CAP  # alias for older imports

RATE_LIMIT_RPS = 0.1
CONCURRENCY = 1
MAX_LIVE_CYCLES = 1
PILOT_MAX_CYCLES = 7
REQUIRED_SUCCESSFUL_CYCLES = 7

CATALOG_DEFAULT = "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"
EVIDENCE_DIR = "artifacts/evidence/ratings-ingestion-05r"
EVIDENCE_DIR_LEGACY = "artifacts/evidence/ratings-ingestion-05"

STAGE5_INCIDENT_RUN_ID = "stage5-supervised-20260919T224456Z-9bc222"
