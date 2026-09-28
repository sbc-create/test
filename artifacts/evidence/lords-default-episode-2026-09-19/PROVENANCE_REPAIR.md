# Provenance repair — lords-default-episode-2026-09-19

## Goal

Replace dirty-worktree install provenance with a committed FEATURE_HEAD
artifact + honest manifest, without restarting the unit.

## Heads

| Ref | Value |
| --- | --- |
| BASE_HEAD | `7dc251d66d65c9b041a1c7cb706e7b3070dbd6e0` |
| FEATURE_HEAD | `ef17a7094ad7f7663ecff29fb5338998d3defe03` |
| ARTIFACT_SOURCE_HEAD | `ef17a7094ad7f7663ecff29fb5338998d3defe03` |
| unsafe build not reused | `20260919T194500Z-36ce7ead-nova` |

## Clean rebuild

- Export: `git archive FEATURE_HEAD` → tempfile via Python `tempfile.mkdtemp`
- Stage (allowlisted): `/srv/lords/.frontend/.rollback/ef17a709-clean-stage/lords-frontend.py`
- Install: `lords-nova-canary.py install --site lords-01 ... --no-restart`
- New rollback (not overwriting deferred candidate): `/srv/lords/.frontend/.rollback/20260919T201039Z-lords-01`
- Verdict: `STAGED_AWAITING_OWNER_RESTART`
- `RESTART_PERFORMED=0`

## Digest proof (pre-restart)

See `ARTIFACT_HASHES.json`. Staged = manifest = live disk = FEATURE_HEAD bytes.
Runtime HTML still serves build `20260913T2300Z-8ececc6c-nova` / artifact `a51dade…`
→ `ARTIFACT_RUNTIME_DIGEST_MATCH=0`, `RUNTIME_STATE=STALE_PROCESS_EXPECTED`.

## Rollback

See `ROLLBACK_VERIFICATION.json`. Candidate
`/srv/lords/.frontend/.rollback/20260919T194936Z-lords-01-deferred` is
**ROLLBACK_VERIFIED=NO** (bytes `06e991c3…` ≠ manifest claim `a51dade…`).
Exact `a51dade` bytes exist under zona-named rollback dirs.

## Scope

See `GIT_DIFF_SCOPE.txt`. Deploy scope: lordfilm47.space files+manifest only.

## Owner next step

`OWNER_RESTART_COMMAND.md` — single restart command; then checklist.


## Viewport P0 follow-up

- FEATURE_HEAD updated to `63216915c75ab75fe579363ef40d318774053350` (includes default-episode + full-size player)
- New clean build `20260919T201932Z-63216915-nova` sha `4b541137ff4df012eb189e4ed5ce2125d47af7d205188e5e7554170954abb120`
- FULL_SIZE_PLAYER_GATE_PASS=YES (playwright 5/5)
- RESTART_PERFORMED=0
