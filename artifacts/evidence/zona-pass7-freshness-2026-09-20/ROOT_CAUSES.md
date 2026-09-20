# Root causes — Zona Pass7

| Section / symptom | Classification | Evidence |
|---|---|---|
| Home «Популярные…» / rating-among-recent | Was request-time; **fixed → WEEKLY_SNAPSHOT** | `popular_weekly.py` + frontend read-only |
| Home «Новые серии» | WRONG_TIME_SEMANTICS (relabeled) | Sorted by title `published_at`; episode timestamps = 0 |
| Collection «Новые эпизоды» | WRONG_TIME_SEMANTICS (relabeled) | Same; description admits catalog order |
| Sixth shelf on live | RUNTIME cross-site overwrite | lords-01 @ 22:51; fixed via zona-isolated artifact |
| Zona not updating every 5 min | EXPECTED — canonical skip | `nova-catalog-refresh` skips zona-01 |
| Source→live lag | INCONCLUSIVE_SOURCE_TIMESTAMP | No upstream event time in snapshot |
| Popular unchanged within week | **EXPECTED_STABLE_SECTION** | Owner contract WEEKLY_SNAPSHOT |
| HTML cache | OK (no-store + week ETag) | Not the freeze cause |
