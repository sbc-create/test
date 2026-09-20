# Architecture — Site Factory Release Orchestrator

**Stage:** `SITE-FACTORY-RELEASE-ORCHESTRATOR-01`
**Target branch:** `cursor/site-factory-release-orchestrator-01`
**Target worktree:** `/home/claude/wt-site-factory-release-orchestrator-01`

## Goal

After **one** owner approval, automatically and sequentially validate → build → deploy → restart → verify → smoke×2 → (scoped rollback) for any number of sites.

```text
owner approves immutable release manifest
→ validate all sites
→ build isolated artifacts
→ deploy canary
→ restart
→ verify runtime
→ smoke×2
→ next site
→ final report
```

Normal steady state:

```text
ONE_TIME_BOOTSTRAP_OWNER_COMMANDS<=1
OWNER_COMMANDS_PER_RELEASE_BATCH=0
MANUAL_RESTART_COMMANDS_PER_SITE=0
MANUAL_CURL_CHECKS_PER_SITE=0
RELEASE_CONCURRENCY=1
AUTOMATIC_ROLLBACK=SCOPED_CURRENT_SITE
```

## Layers

```text
unprivileged planner (bin/site-factory-release plan|validate|record-approval)
→ immutable approved manifest + digest
→ root-owned runner (automation/host/site-factory-release-runner.py)
→ allowlisted handlers from Core release registry
```

## Core authority

- Identity / domains / indexing flags: `config/site-profiles/*.json`
- Ops overlay (service_name, handlers, smoke, artifact destination): `config/release-registry.json`
- Exact-domain lookup only (`factory.release_orchestrator.registry`)

## Package layout

| Path | Role |
| --- | --- |
| `factory/release_orchestrator/` | library + CLI |
| `schemas/release-orchestrator/` | JSON Schemas |
| `config/release-registry.json` | ops registry |
| `bin/site-factory-release` | unprivileged CLI |
| `automation/host/site-factory-release-runner.py` | root runner |
| `reports/releases/<release_id>/` | batch evidence |
| `docs/release-orchestrator/` | this documentation |

## Principles (enforced in code)

1. No guessed service names / domains
2. No wildcard systemctl
3. No arbitrary root shell
4. Concurrency = 1 site in deploy/restart window
5. Artifacts bound to source HEAD + SHA
6. Indexability from Core exact-domain registry
7. OPEN↔CLOSED requires explicit approval
8. One site failure does not mutate the rest (default policy)
9. Idempotent resume from checkpoint
10. PASS only after live postconditions
11. Staged ≠ deployed ≠ verified

## Обычный batch не требует ручного SSH/systemctl/curl.

После одноразового owner bootstrap новые релизы идут через CLI/runner без ручных проверок PID/build/SHA на каждый домен.
