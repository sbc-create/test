# FINAL REPORT — continuation turn (Shell blocked)

Previous `PASS_SHADOW_LIVE_CANARY_PENDING` **revoked**.

```text
VERDICT=BLOCKED_EXECUTION_ENVIRONMENT
STAGE=SITE-FACTORY-RELEASE-ORCHESTRATOR-01
OWNER_AUTHORIZATION_ID=SITE-FACTORY-RELEASE-ORCHESTRATOR-SHADOW-20260920-01

BLOCKED_TOOL=Shell
BLOCKED_OPERATION=git status | git worktree add | sha256sum | pytest | shadow CLI
POLICY_ERROR=[UNATTENDED_SAFE] неизвестный инструмент 'Shell': правило не описано, действует default-deny
NOTE=PreToolUse allowlists Bash; Cursor session exposes Shell. request_smart_mode_approval denied. Owner auth ID did not remap tools.

START_HEAD=491836048dae11ae639795c7a3827706129faef6
FINAL_HEAD=unverified
BRANCH=claude/players-only-production-009 (target branch NOT created)
WORKTREE=/home/claude/wt-site-factory-release-orchestrator-01 (NOT created)
COMMITS=0
WORKTREE_CLEAN=n/a
SOURCE_TRANSFER_DIGEST_MATCH=0
FILES_TRANSFERRED=0
TESTS=0
TEST_RUNS_CONSECUTIVE=0
SHADOW_SITES_PLANNED=0
SHADOW_SITES_PASSED=0
SHADOW_MUTATIONS=0
UNGUARDED_MUTATING_ENTRYPOINTS=unverified
TLD_FALLBACK_COUNT=unverified
UNKNOWN_DOMAIN_DENY_PASS=unverified
APPROVAL_REPLAY_DENY_PASS=unverified
STATE_RESUME_PASS=unverified
ROLLBACK_SIMULATION_PASS=unverified
RESTART_WARNING_POSTCONDITIONS_PASS=code+tests_written_not_executed
INOTIFY_DIAGNOSIS=not_run
INDEXABILITY_PRESERVATION_PASS=unverified
CLI_PASS=unverified
JSON_REPORT_PASS=unverified
LIVE_DEPLOY_PERFORMED=0
RESTART_PERFORMED=0
SYSTEMD_MUTATIONS=0
INDEXABILITY_MUTATIONS=0
DNS_MUTATIONS=0
PUSH_PERFORMED=0
MERGE_PERFORMED=0
READY_FOR_OWNER_CANARY=0

FILES_ALREADY_SAVED=orchestrator sources in checkout + content copies under checkpoint/files/
RECOVERABLE_CHECKPOINT=/srv/site-factory/repo/var/release-orchestrator-checkpoint-20260920/
  FILE_MANIFEST.txt
  files/ (44 content copies from earlier + locks.py still only in checkout)
  recompute-digests.sh
  recover-to-worktree.sh
  RECOVERY.md
  docs/release-orchestrator/BLOCKED_EXECUTION_ENVIRONMENT.md

REMAINING=
  1. Unblock Shell (map to Bash in guard) or provide Bash tool
  2. recompute-digests.sh → SOURCE SHA256
  3. recover-to-worktree.sh → branch+worktree+digest match
  4. thematic commits 1–7
  5. pytest x2 consecutive
  6. inotify-diagnose read-only
  7. shadow Lords×3 + mutation digests
  8. bypass evidence
  9. only then PASS_SHADOW_READY_FOR_OWNER_CANARY

NEXT_SAFE_STEP=Fix UNATTENDED_SAFE tool name: allow `Shell` OR expose `Bash` in this harness, then run recover-to-worktree.sh
```
