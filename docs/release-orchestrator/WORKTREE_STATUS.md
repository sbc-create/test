# STAGE SITE-FACTORY-RELEASE-ORCHESTRATOR-01 — session status

## Worktree / branch

| Item | Status |
| --- | --- |
| `TARGET_BRANCH=cursor/site-factory-release-orchestrator-01` | **not created** (Shell/git blocked in session) |
| `TARGET_WORKTREE=/home/claude/wt-site-factory-release-orchestrator-01` | **not created** |
| Code location | active checkout `/srv/site-factory/repo` (branch `claude/players-only-production-009` at start) |
| Intended BASE | `origin/main` @ `a7f7cb6236fbc9770af949ef98eae511cd3c8fc4` |
| Closest prior release worktrees | `/home/claude/wt-release-03`, `/home/claude/wt-release-03-v3` (not reused as duplicate orchestrator) |

## Owner unblock

```bash
git -C /srv/site-factory/repo worktree add \
  -b cursor/site-factory-release-orchestrator-01 \
  /home/claude/wt-site-factory-release-orchestrator-01 \
  a7f7cb6236fbc9770af949ef98eae511cd3c8fc4
# then port factory/release_orchestrator + schemas + docs + tests onto that worktree
```
