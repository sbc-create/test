# Ratings Ingestion Stage 1 — Architecture Decision

## Decision

Centralized module: `factory/ratings/` (not Lords-owned).

Chain:

`external sources → adapters → title identity resolver → append-only observations
→ current projection → immutable ratings_snapshot_v1 → rating_gateway → templates`

## Why not extend only `factory/lords/`

Committed `factory/lords/ratings_contract.py` is a **consumer** contract
(`ratings-enrichment/1.0.0`) for kinopoisk/imdb observations — it correctly
refuses to own the ingestion queue. Historical prototypes under
`factory/lords/rating_*` in a dirty checkout are Lords-shaped and incomplete.

`factory/site_engine/rating_{sources,feed,discovery}.py` owns provider-feed
display rights and must keep **exactly one** authorized vitrine source
(`provider-feed`). Shikimori is documented there with `enabled=false` so
site_engine.authorized stays `provider-feed` only.

## Storage

SQLite via `migrations/0002_ratings_ingestion.py`, applied only to isolated
paths (`var/ratings/` or evidence DB). **Not** applied to production DB on Stage 1.

## Read-only prototypes used (from `/srv/site-factory/repo`, not copied blindly)

| Prototype | What we took | What we rejected |
| --- | --- | --- |
| `rating_gateway.py` | provenance, no title-string match, NULL≠0, separate sources | Russian-only API; KP/IMDb flat fields as sole model |
| `rating_sources.py` | User-Agent discipline, batch-50 idea, zero-is-absent | **REST** `/api/animes` — replaced with official GraphQL |
| `nova-ratings-backfill.py` | separate backfill from publish; flock; quarantine idea | Fuzzy title threshold 0.34 auto-confirm — **forbidden** for auto-publish |
| `canonical_projection.py` | last-good merge semantics | Lords-only projection schema |
| `nova_publish.py` | atomic publish mindset | Not a ratings pipeline |
| `nova-rating-ceiling-probe.py` | ceiling probe concept | Provider-detail specific |

## AnimeMedia

`UNVERIFIED_DISABLED`. Our `animedia.icu` / `animedia.space` are not external
sources. No scraper.

## Stage 1 gates

- No production migration apply
- No systemd enable/start
- No live snapshot switch
- No push/merge
- Candidate snapshot only under `artifacts/evidence/ratings-ingestion-01/`
