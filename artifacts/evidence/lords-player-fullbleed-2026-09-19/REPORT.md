# Lords player full-bleed-v1 repair — 2026-09-19

## Verdict

`READY_FOR_OWNER_RESTART_PLAYER_CONTRACT_COMMITTED`

## Heads

| Ref | Value |
| --- | --- |
| START_HEAD | `92cd599e875bd732c5bc8200f74c406ccf9f7fd6` |
| PLAYER_FIX_HEAD | `0a5fe648415d30d8f22bed016205c3cd878d7b3f` |
| Commits | `f8d9e1e` fix contract · `42fe56a` regression tests · `0a5fe64` deploy gate |

## Root cause (confirmed)

1. Stale runtime still serving `20260913T2300Z-8ececc6c-nova` (no restart after prior fix).
2. Artifact/manifest lineage drift: disk briefly held foreign `128c3f6e…` while manifest claimed `63216915`/`4b541137…`.
3. Provider SDK inserts fixed `640×360` iframe; global `iframe{height:auto}` + centered shell left a small player inside a full-width black box.

## Permanent contract

- Marker: `data-player-layout-contract="full-bleed-v1"` on every player shell.
- CSS beats global iframe rules with `!important` absolute-fill.
- Client: `fitPlayerTree` + idempotent `MutationObserver`/`ResizeObserver` (childList only, busy guard, no layout loop).
- Deploy: `scripts/gate_lords_player_layout.py` + canary `_проверить_player_contract` + site flock lease + `--no-restart`.

## Staging (no restart)

| Check | Value |
| --- | --- |
| ARTIFACT_SOURCE_HEAD | `0a5fe648415d30d8f22bed016205c3cd878d7b3f` |
| MANIFEST_SOURCE_HEAD | `0a5fe648415d30d8f22bed016205c3cd878d7b3f` |
| artifact_sha256 | `b9de6b626e6578310b7e35cefd63e08d1715db2ff0664c072064d12e72b146fa` |
| build_id | `20260919T224500Z-0a5fe648-nova` |
| SOURCE_ARTIFACT_DIGEST_MATCH | 1 |
| DISK_MANIFEST_DIGEST_MATCH | 1 |
| PLAYER_CONTRACT_IN_ARTIFACT | 1 |
| CONCURRENT_DEPLOYMENT_DETECTED | NO |
| ROLLBACK_POINT | `/srv/lords/.frontend/.rollback/20260919T225105Z-lords-01` |
| ROLLBACK_VERIFIED | YES (point bytes == point.json sha) |
| ARTIFACT_RUNTIME_DIGEST_MATCH | 0 (expected until owner restart) |

## Tests

- `pytest tests/lords/test_player_layout_contract.py` + viewport + canary gate: PASS
- `npx playwright test --config=playwright.lords-viewport.config.js`: 9 passed
- Fill ratios after async SDK replacement: 1440/768/390 → width=1.0 height=1.0, overflow=0, instances=1, small=0

## Owner next step

```bash
sudo -n systemctl restart lords-nova-01.service
```

Do **not** claim `LIVE_PLAYER_PASS=YES` until post-restart live verification.
