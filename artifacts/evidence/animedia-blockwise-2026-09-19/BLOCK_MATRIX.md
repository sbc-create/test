# BLOCK_MATRIX — Animedia blockwise visual pass

UTC date: 2026-09-19  
Branch: `claude/animedia-template-finalization-01`  
START_HEAD: `939df3d31b1ddc7648004c0b55dd2f475ebafa38`  
FEATURE_HEAD (live artifact source): `ca1696796b4f95e0e474664497cf2866ca0d343f`  
FINAL_HEAD (evidence tip): `93f9f656fbd3f2eb9c74b968c7ee7f40bfffcc52`  
Live build: `20260919T224052Z-ca169679-nova`  
Worktree/live artifact SHA256: `f89b9d8257f20b5170333bbdac372eebf1be6f2aa934b49be5b27487c4cbc680`

## Provenance note

| Layer | Value |
| --- | --- |
| Live HTTP artifact | `f89b9d82…` (matches disk + runtime on both domains) |
| FEATURE_HEAD tip | `ca169679…` BLOCK_08–11 |
| Intermediate home deploy | `20260919T222328Z-18cd7d7e-nova` |
| Rollback | `/srv/lords/.frontend/.rollback/pre-closed-update-20260919T224052Z` |

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
| BLOCK_08 | `/catalog/` | filters + cards | **PASS** | 1 | `ca16967` |
| BLOCK_09 | `/search/` | ranking | **PASS** | 1 | `ca16967` |
| BLOCK_10 | collections/related | `.zhub`, `.zsec--rel` | **PASS** | 1 | `ca16967` |
| BLOCK_11 | footer/schedule | `.zft`, schedule | **PASS** | 1 | `ca16967` |
| BLOCK_12 | regression | all routes × viewports × themes | **PASS** | 1 | `93f9f65` |

Close flags until owner review:

```text
ANIMEDIA_VISUAL_FINALIZATION_CAN_BE_CLOSED=NO
ANIMEDIA_TEMPLATE_CAN_BE_CLOSED=NO
ANIMEDIA_OVERALL_CAN_BE_CLOSED=NO
OWNER_VISUAL_REVIEW_REQUIRED=YES
```
