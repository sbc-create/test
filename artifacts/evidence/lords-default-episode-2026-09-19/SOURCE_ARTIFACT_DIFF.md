# SOURCE_ARTIFACT_DIFF

| Layer | SHA256 | Notes |
| --- | --- | --- |
| START worktree `lords-frontend.py` | `a51dade469321e3078b8a7eee124e5ac936f286a33c28f327368bfbfabb85346` | equals git `8ececc6c` blob; no awaiting |
| Live claimed artifact | `a51dade…` | manifest claim only |
| Live disk before fix | `06e991c3e558621c494e1150483b98eca67f2fcdc62ccaf0b165adf3e5b33432` | animedia-finalization twin |
| Worktree after hotfix | `36ce7eada5691b7ed949c0c301c45e1123dd6ddbf9c667701566ea37e883d1a6` | animedia base + first-playable selection |

## Behavioural diff (hub)

| | START `7dc251d` blob | Live stale process | Disk twin pre-fix | Hotfix |
| --- | --- | --- | --- | --- |
| Hub episode | hardcode `1` | `None` → awaiting | last avail | first avail |
| Aggregators | kp/mdl/mali | cvh via provider-id | cvh via provider-id | same + first ep |
| Awaiting literal | absent | present | present if None | not used when episodes exist |
