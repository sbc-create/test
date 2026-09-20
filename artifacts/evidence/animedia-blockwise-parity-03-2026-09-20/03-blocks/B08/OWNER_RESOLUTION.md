# B08 OWNER RESOLUTION — ANIMEDIA-B10-B16-20260920-01

- block_id: B08
- prior_status: BLOCKED_DEPENDENCY(owner=player)
- resolved_status: PASS_LOCAL_PENDING_LIVE
- OWNER_DECISION_ID: ANIMEDIA-B10-B16-20260920-01
- policy: FIRST_PLAYABLE_DETERMINISTIC
- evidence_root: artifacts/evidence/animedia-blockwise-parity-03-2026-09-20/

## Decision applied

| Rule | Value |
| --- | --- |
| Generic default | first playable after `(season ASC, episode ASC)` |
| Exact episode | preserved; no redirect / no swap |
| Generic URL/canonical | stay on `/title/{slug}/` |
| autoplay | 0 |
| player instances | max 1 |
| no playable | honest «Видео пока недоступно» via existing state shell |

## Implementation

- `config/animedia-default-episode-policy.json`
- `выбрать_доступную_серию` → first playable (was latest)
- DOM: `data-default-episode-policy="FIRST_PLAYABLE_DETERMINISTIC"`
- `DEFAULT_EPISODE_POLICY_DATA_GAP=0`

## Tests

`tests/unit/test_animedia_parity03_b08.py`
