# BLOCK_MATRIX — Animedia blockwise visual pass

UTC date: 2026-09-19  
Branch: `claude/animedia-template-finalization-01`  
START_HEAD: `939df3d31b1ddc7648004c0b55dd2f475ebafa38`  
FEATURE_HEAD (live artifact source): `1cc115824ce684fc47f005edfaa393bd61037f94`  
Live build: `20260919T205122Z-1cc11582-nova`  
Worktree artifact SHA256: `6cae6d38890447730bd2460a499d1f4603fa9d164eda3fb538b2ff09e0ef4a46`

## Provenance note

| Layer | Value |
| --- | --- |
| Live HTTP artifact | `6cae6d38…` (matches worktree / FEATURE_HEAD) |
| `/srv/lords/.frontend/lords-frontend.py` on disk | `dec73873…` (foreign overwrite; **not** Animedia 1.2.4) |
| Running ports 9121/9122 | still serve 1.2.4 from process memory |

Disk ≠ live until next restart. Do not treat disk hash as live proof. Restore on next authorized Animedia deploy.

Unrelated dirty (left untouched): `artifacts/evidence/animedia-final-repair-…/FINAL.md`, `player-probe/`, `lords-frontend.animedia-prev.py`.

---

## Blocks

| block_id | route | boundary | status | attempt | commit |
| --- | --- | --- | --- | --- | --- |
| BLOCK_01 | `/*` shell | `.zhd`, `.zwrap`, theme tokens, body | **PASS** | 1 | `eec2d2a` |
| BLOCK_02 | `/` top shelf | `.ahero` | **PASS** | 1 | `d76ee94` |
| BLOCK_03 | `/`, `/new/` | `.ahome-eps`, episode events | **PASS** | 1 | `f5ac02e` |
| BLOCK_04 | `/` lower | `.zsec` shelves | **PASS** | 1 | `18cd7d7` |
| BLOCK_05 | `/title/*` info | `.ztitle` (no player) | **PASS** | 1 | `3209a8e` |
| BLOCK_06 | `/title/*` ratings | `.rbs`, ratings contract | **PASS** | 1 | `139e9e7` |
| BLOCK_07 | `/title/*` player | `.zpl` | **PASS** | 1 | `fa43b38` |
| BLOCK_08 | `/catalog/` | filters + cards | **PASS** | 1 | _(pending)_ |
| BLOCK_09 | `/search/` | ranking | **PASS** | 1 | _(pending)_ |
| BLOCK_10 | collections/related | `.zhub`, `.zsec--rel` | **PASS** | 1 | _(pending)_ |
| BLOCK_11 | footer/schedule | `.zft`, schedule | **PASS** | 1 | _(pending)_ |
| BLOCK_12 | regression | all routes × viewports × themes | PENDING | 0 | — |

Close flags until owner review:

```text
ANIMEDIA_VISUAL_FINALIZATION_CAN_BE_CLOSED=NO
ANIMEDIA_TEMPLATE_CAN_BE_CLOSED=NO
ANIMEDIA_OVERALL_CAN_BE_CLOSED=NO
OWNER_VISUAL_REVIEW_REQUIRED=YES
```
