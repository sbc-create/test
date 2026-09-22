# STAGE SITE-FACTORY-RELEASE-ORCHESTRATOR-01 — blocked execution

```text
VERDICT=BLOCKED_EXECUTION_ENVIRONMENT
PREVIOUS_VERDICT_REVOKED=PASS_SHADOW_LIVE_CANARY_PENDING
HONEST_STATUS=BLOCKED_UNVERIFIED_IMPLEMENTATION→BLOCKED_EXECUTION_ENVIRONMENT
OWNER_AUTHORIZATION_ID=SITE-FACTORY-RELEASE-ORCHESTRATOR-SHADOW-20260920-01

BLOCKED_TOOL=Shell
BLOCKED_OPERATION=git status / git worktree add / sha256sum / pytest / shadow CLI
POLICY_ERROR=[UNATTENDED_SAFE] неизвестный инструмент 'Shell': правило не описано, действует default-deny
NOTE=Guard allowlists Bash; this Cursor harness exposes Shell. request_smart_mode_approval denied twice. User authorization did not remap the tool.

START_HEAD=491836048dae11ae639795c7a3827706129faef6
FINAL_HEAD=unverified (no git shell)
BRANCH=claude/players-only-production-009 (TARGET cursor/site-factory-release-orchestrator-01 NOT created)
WORKTREE=/home/claude/wt-site-factory-release-orchestrator-01 (NOT created)
COMMITS=0_on_target_branch
WORKTREE_CLEAN=n/a
SOURCE_TRANSFER_DIGEST_MATCH=0 (transfer not executed)
FILES_TRANSFERRED=0
TESTS=0_runs
TEST_RUNS_CONSECUTIVE=0
SHADOW_SITES_PLANNED=0
SHADOW_SITES_PASSED=0
SHADOW_MUTATIONS=0
UNGUARDED_MUTATING_ENTRYPOINTS=unverified
TLD_FALLBACK_COUNT=unverified_runtime
UNKNOWN_DOMAIN_DENY_PASS=unverified
APPROVAL_REPLAY_DENY_PASS=unverified
STATE_RESUME_PASS=unverified
ROLLBACK_SIMULATION_PASS=unverified
RESTART_WARNING_POSTCONDITIONS_PASS=code_present_unverified
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

FILES_ALREADY_SAVED=see FILE_MANIFEST.txt (still in source checkout + checkpoint scripts)
RECOVERABLE_CHECKPOINT=/srv/site-factory/repo/var/release-orchestrator-checkpoint-20260920/

REMAINING_UNBLOCKED_WORK=
  1. Map Cursor Shell→Bash in UNATTENDED_SAFE / PreToolUse guard OR allow Shell
  2. bash var/release-orchestrator-checkpoint-20260920/recompute-digests.sh
  3. bash var/release-orchestrator-checkpoint-20260920/recover-to-worktree.sh
  4. thematic commits in worktree
  5. pytest x2 + expand tests per BLOCK 04
  6. inotify-diagnose read-only
  7. shadow three Lords
  8. bypass audit evidence
  9. PASS_SHADOW_READY_FOR_OWNER_CANARY only after evidence

NEXT_SAFE_STEP=Unblock Shell (or rename tool to Bash in harness). Then run recover-to-worktree.sh from the checkpoint.
```
