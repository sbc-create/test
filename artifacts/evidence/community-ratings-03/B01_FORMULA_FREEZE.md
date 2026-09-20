# rating_policy_v1 formula freeze — COMMUNITY-RATINGS-03

**POLICY_VERSION:** `rating_policy_v1`  
**POLICY_DIGEST:** `a2daf212d92ea40dc3de658806fb6f5f5cf7ae77890ff0c25f81bd89088c17d5`  
**Verified:** sha256sum matches `config/community/rating_policy_v1.json`

## Animedia

```text
A = S_A / N_A   # native votes in rating_space=animedia only
N=0 → absent («Пользовательских оценок пока нет» / «Пока нет оценок»)
```

External Shikimori/KP/IMDb/AMD: separate badges; never enter Animedia native average; never mutated by votes.

## Yummy

Frozen proposed prior weights in policy:

```text
animedia_native: 0.70
shikimori: 0.30
proposed_m: 10
```

```text
P = 0.70×A + 0.30×R_shikimori   # renormalize if one missing; never fill missing with 0
Y = (S_Y + m×P) / (N_Y + m)
m=10  # prior strength, NOT displayed as vote count
```

Display:

- N=0 → «Предварительная оценка Yummy», 0 голосов  
- N>0 → «Оценка Yummy», N голосов (native only)

Double-count guard: if Animedia already embeds Shikimori, drop Shikimori component (`animedia_embeds_shikimori`). Current Animedia native does **not** embed Shikimori → both components allowed when present.

```text
FORMULA_TOLERANCE<=0.01
PREVIEW_EQUALS_COMMITTED_PROJECTION=1
YUMMY_DOUBLE_COUNTING_GATE=PASS
```
