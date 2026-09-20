# Formula lineage & double-counting gate

## Layers (rating_policy_v1)

1. **External observation** — `rating_observations` / `rating_current` (amd_online, shikimori, …). Immutable by user votes.
2. **Animedia native** — community accepted votes only: `A = S/N`. Currently **N=0** → absent («Пользовательских оценок пока нет»). **Does not include Shikimori or AMD.**
3. **Yummy prior** — `P_Y = 0.70×A + 0.30×R_shikimori` with renormalize-if-missing; missing ≠ 0.
4. **Yummy public** — `Y = (S_Y + m×P_Y)/(N_Y + m)`, `m=10` mathematical prior strength (**not** 10 user votes). Displayed vote count = `N_Y` only.
5. **Display projection** — presentation rounding only; never feeds next compute.

## Independence proof

| Component | Contains Shikimori? | Notes |
| --- | --- | --- |
| `animedia_native` | NO | User ledger only; empty in Stage02 |
| `animedia_blend_v1` | NO | Legacy AMD+local; **not** used as Yummy prior input |
| `amd_online` | NO | External; not in Yummy prior |
| `shikimori` | YES | External observation |

Yummy prior inputs per policy: `animedia_native` XOR/AND `shikimori` with double-count guard.  
Since `animedia_native` does **not** embed Shikimori, using both when native exists is valid.  
When `N_A=0`, Animedia component is **absent** → renormalize to Shikimori-only prior (not zero-fill).

```text
YUMMY_DOUBLE_COUNTING_GATE=PASS
DOUBLE_COUNTED_SOURCE_COUNT=0
animedia_embeds_shikimori=false
```

## Display when N_native=0

- Animedia: native absent label; external Shikimori badge separate.
- Yummy: «Предварительная оценка Yummy» from prior; tooltip discloses confirmed sources; **vote count = 0** (m not shown as votes).
