# Blocks 01–12 checkpoint

## Delivered (isolated / draft; not production-activated)

| Block | Artifact |
| --- | --- |
| 00 | `BLOCK_00_AUDIT.md`, `config/community/rating_policy_v1.json` (DRAFT_OWNER_GATED) |
| 01 | `factory/community/spaces.py` — animedia shared, yummy isolated, actor merge |
| 02 | `factory/community/store.py` — events / votes / aggregates |
| 03–04 | `factory/community/formulas.py` + `YUMMY_PRIOR_COMPARISON*.json` |
| 05–06 | `factory/community/service.py`, `api.py` — GET/PUT/DELETE + preview + idempotency |
| 07 | `factory/community/antifraud.py` — CSRF/origin, rate, HMAC IP-prefix, kill switch |
| 08–09 | `factory/community/frontend/*` — Animedia + Yummy partials (not mounted prod) |
| 10 | `factory/community/reconcile.py` — rebuild mismatch blocks publication |
| 11 | `comments_foundation.py` + migration 0005 dark tables; COMMENTS_*=0 |
| 12 | unit tests + `GATES.md` |

## Explicit non-actions

- No production migration apply
- No public rating activation / deploy / restart
- No scheduler enable
- No new Shikimori ingestion cycle
- No fake user votes
- No comments publication / SEO / sitemap
