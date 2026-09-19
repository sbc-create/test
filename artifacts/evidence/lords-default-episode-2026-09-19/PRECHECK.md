# PRECHECK — lords-default-episode-2026-09-19

## Worktree gate

| Field | Expected | Actual |
| --- | --- | --- |
| WORKTREE | `/home/claude/wt-lords-default-episode-01` | match |
| BRANCH | `cursor/lords-default-episode-01` | match |
| START_HEAD | `7dc251d66d65c9b041a1c7cb706e7b3070dbd6e0` | match |

No reset / clean / foreign checkout / push / merge performed.

## Live BEFORE (lordfilm47.space)

Captured under `BEFORE/`.

| Probe | Result |
| --- | --- |
| Generic `/title/pylnye-utesy/` | `data-player data-state="awaiting"`, no `<video-player>`, literal «До выбора серии запросов к провайдеру нет», 3 episode links |
| Exact `/season-1/episode-1/` | `data-state="playable"`, `<video-player … data-aggregator="cvh" data-title-id="01a0b620-…" episode="1">` |
| Declared meta revision | `7dc251d` |
| Declared build_id | `20260913T2300Z-8ececc6c-nova` |
| Declared artifact_sha256 | `a51dade469321e3078b8a7eee124e5ac936f286a33c28f327368bfbfabb85346` |

## Provenance mismatch (already proven before edits)

See `BEFORE/provenance-snapshot.json` and `PROVENANCE_CHAIN.md`.
