# DESCRIPTOR_CONTRACT

## Authoritative for lords-01

| Source | Decision |
| --- | --- |
| `/srv/lords/.frontend/player-lords-01.json` | `source_mode: provider-id`, `publisher_id: 10238` |
| Live exact episode HTML | `data-aggregator="cvh"`, `data-title-id=<detail.id UUID>` |
| Detail sidecar `pylnye-utesy` | `id=01a0b620-…`, `external_ids.imdb` only (no kp) |
| Frozen `PLAYER_CONTRACT.yaml` | allows kp\|mali\|mdl only — **lags** live Secret Hub mode |

## Invariant after hotfix

Generic hub and exact `/season-N/episode-M/` for the same episode emit the same primary candidate:

* aggregator identical
* title-id identical
* season/episode attributes identical for that episode

`cvh` is retained because stripping it would make `pylnye-utesy` (and other UUID-only rows) `nosource` under provider-id. Conflict with freeze recorded; not silently “fixed” by falling back to imdb (forbidden by PC-2).
