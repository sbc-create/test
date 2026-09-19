# FINAL — Animedia Visual Final Closure (2026-09-19)

## Verdict

`VERDICT=PASS_TEMPLATE_NEEDS_OWNER_DATA`

Geometry, player golden, grids, footer, ads collapse, responsive overflow, and cache coherence pass on live `animedia.icu` / `animedia.space`. Owner contacts and source schedule remain gaps.

## Live after (1363×936)

| Metric | ICU | Space | Target |
| --- | --- | --- | --- |
| body height | 6306 | 5466 | ≤8200 / ≤7800 |
| lower grid | 6×2 | 6×2 | 6×2 |
| lower poster | 197.8×296.7 | 197.8×296.7 | ~195–205×293–305 |
| max shelf H | 799.6 | 799.6 | ≤820 |
| top poster | 152×214 | 152×214 | ~153×214 |
| episode thumb | 60×72 | 60×72 | ~60×70 ±3 |
| footer H | 92.8 | 92.8 | ≤140 desktop |
| related | 6×1 / 412.4 | 6×1 / 412.4 | 6 cols / ≤420 |

Before (same viewport): ICU 10961 / Space 9398, lower 5×3 @250×375, shelf ~1535, footer ~302, related 5+2.

## Build

- Live build: `20260919T205122Z-1cc11582-nova` (≠ `20260919T201809Z-7cb7c901-nova`)
- Design: `1.2.4`
- Artifact: `6cae6d38890447730bd2460a499d1f4603fa9d164eda3fb538b2ff09e0ef4a46`
- Rollback: `/srv/lords/.frontend/.rollback/pre-closed-update-20260919T205122Z`

## Tests

```text
.venv/bin/python -m pytest tests/unit/test_animedia_visual_final_closure.py \
  tests/unit/test_animedia_visual_finalization.py \
  tests/unit/test_animedia_home_pagination.py \
  tests/unit/test_animedia_followup_player_collections.py \
  tests/unit/test_animedia_final_repair.py \
  tests/unit/test_animedia_parity_surfaces.py -q
→ 68 passed
```

Player golden: ICU 10/10, Space 10/10, post-restart pass.

## Gaps (honest)

- `CONTACT_DATA_GAP=1` — no owner contact/legal config
- `SCHEDULE_DATA_GAP=1` — no `next_episode_at` in snapshot
- Relations absent in details → franchise nav hidden

See `DATA_GAPS.json`, `OWNER_DATA_REQUIRED.md`.

## Close flags

```text
ANIMEDIA_HOME_FEED_CAN_BE_CLOSED=YES
ANIMEDIA_VISUAL_FINALIZATION_CAN_BE_CLOSED=YES
ANIMEDIA_TEMPLATE_CAN_BE_CLOSED=YES
ANIMEDIA_OVERALL_CAN_BE_CLOSED=NO
```
