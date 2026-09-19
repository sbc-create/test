"""Stage 5 supervised pilot constants — hard caps, not defaults to override casually."""

from __future__ import annotations

STAGE = 5
SOURCE_ALLOWED = "shikimori"
SOURCE_DISABLED = ("amd_online", "amd.online", "animemedia", "imdb", "kinopoisk")
ACCEPTED_TARGET = 100
CANDIDATE_CAP = 150
RATE_LIMIT_RPS = 0.1
CONCURRENCY = 1
MAX_LIVE_CYCLES = 1
PILOT_MAX_CYCLES = 7
CATALOG_DEFAULT = "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"
EVIDENCE_DIR = "artifacts/evidence/ratings-ingestion-05"
