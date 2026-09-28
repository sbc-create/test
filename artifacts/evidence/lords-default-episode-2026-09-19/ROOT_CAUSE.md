# ROOT_CAUSE

## Summary

Live `lordfilm47.space` was **not** serving the source tree at declared HEAD `7dc251d`.
Three independent failures stacked:

1. **Lie in the template manifest** — `source_commit` patched to `7dc251d` while `build_id` / `artifact_sha256` still claimed `8ececc6c` / `a51dade…`.
2. **Runtime file ≠ claimed artifact** — on-disk `/srv/lords/.frontend/lords-frontend.py` digest `06e991c3…` (byte-identical to `wt-animedia-finalization-01`), not `a51dade…`.
3. **Stale process** — unit PID started `2026-09-19T03:43:05Z`; file replaced at `19:41:41Z` without restart. Loopback still rendered the old in-memory `awaiting` hub path.

## Why the symptom looked like “missing selectedEpisode=1”

Declared source at `7dc251d` already calls `разметка_плеера(..., сезон_старт, 1)`.
Blindly adding another `selectedEpisode=1` would have been wrong: that source was never what live executed.

Live HTML literal `До выбора серии запросов к провайдеру нет` exists only in the animedia/integration lineage (`ждёт_выбора_серии` + hub `episode=None` / stale process), not in `7dc251d` / `8ececc6c`.

## Secondary logic bug (on the disk twin that was not yet loaded)

Even the disk twin’s `выбрать_доступную_серию` returned **last** available episode despite docstring saying first, and still allowed `episode=None` → `awaiting` when `avail=0`.
Hotfix: first playable in canonical season/episode order; never leave null when released episodes exist.

## Descriptor contract

`player-lords-01.json` has `source_mode: "provider-id"`. Exact episode routes therefore bind `cvh` + detail UUID.
Frozen `knowledge/cdnvideohub/PLAYER_CONTRACT.yaml` still lists only `kp|mali|mdl` — recorded as lag vs live Secret Hub config; lords-01 keeps the proven provider-id path so hub and exact routes stay consistent.
