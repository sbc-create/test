# Stage 4 git provenance

## Heads

| Role | Commit |
| --- | --- |
| START_HEAD | `e4341e0c96e22e5a9dfc5c0c657be55eaabf1e73` |
| STAGE3_FEATURE_HEAD | `c199300828c72f0b91b546e3248346cdb7c8729e` (ancestor) |
| STAGE3_REPORT_HEAD | `9b3957d6c7145b70a9496502ba846887126717c4` (ancestor) |

## Runtime vs report commits

Runtime code (fetches/DB/snapshot/scheduler): `c199300`, `ada3120`, `174f03f`, Stage3 feat commits `7b4c79a`…`3fe543e`, plus Stage4 modules.

Report/evidence-only on Stage2 tip chain: `9b3957d`, `942497b`, `65a6d38` (partial), `e4341e0` (evidence).

## Runtime source digest

```text
RUNTIME_SOURCE_DIGEST=929dfd30dfcb794aaaf73b22d3708b6b32078cfa6ab280ef37692581cd8b39b4
files=['factory/ratings/stage3_canary.py', 'factory/ratings/snapshot.py', 'factory/ratings/scheduler.py', 'factory/ratings/store.py', 'factory/ratings/closed_publish.py', 'factory/ratings/source_policy.py']
```

## Untracked `.prev`

Stage2 candidate `.prev` files remain untracked and are **not** loaded by snapshot builder, gateway, or scheduler.

## Background finds

No stale `find` / canary processes at Stage4 start.
