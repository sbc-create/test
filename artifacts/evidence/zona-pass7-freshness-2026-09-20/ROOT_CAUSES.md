# Root causes — Zona Pass7

| Section / symptom | Classification | Evidence |
|---|---|---|
| Home «Популярные …» | STATIC_RANKING_SIGNAL + wrong label | Rating among 400 recent; no views/activity field |
| Home «Новые серии» | WRONG_TIME_SEMANTICS | Sorted by title `published_at`; episode timestamps = 0 |
| Collection «Новые эпизоды» | WRONG_TIME_SEMANTICS | Same; description already admitted catalog order |
| Sixth shelf «Недавно в каталоге» + genre mega-shelves on live | RUNTIME_NOT_RELOADED / cross-site overwrite | lords-01 deploy 22:51 overwrote shared `lords-frontend.py` after Pass6 |
| Zona not updating every 5 min | EXPECTED — canonical skip | `nova-catalog-refresh` logs «пропускаю … zona-01» |
| Source→live lag | INCONCLUSIVE_SOURCE_TIMESTAMP | No upstream event time in authorized snapshot |
| Stuck shelves between dailies | NO_NEW_SOURCE_DATA (for zona path) | Only daily publish writes zona snapshots |
| Collections / related stable | EXPECTED_STABLE_SECTION | When inputs unchanged |
| HTML cache | OK (no-store) | Not the freeze cause |
