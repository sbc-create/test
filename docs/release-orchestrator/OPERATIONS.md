# Operations

## Обычный batch не требует ручного SSH/systemctl/curl.

## CLI

```text
bin/site-factory-release plan --intake sites.json --release-id rel-… --source-head … --out release.json
bin/site-factory-release validate --manifest release.json
bin/site-factory-release record-approval --manifest release.json --approval-id apr-… --approved-by owner --out approval.json
bin/site-factory-release run --release-id rel-… --manifest release.json --approval approval.json --shadow
bin/site-factory-release status --release-id rel-…
bin/site-factory-release resume --release-id rel-… --manifest release.json --approval approval.json
bin/site-factory-release inotify-diagnose
bin/site-factory-release bootstrap-print
```

Shadow is the default for unprivileged `run`. Live mutate requires the root runner after bootstrap and explicit owner approval.

## Reports

```text
reports/releases/<release_id>/
├── manifest.json
├── manifest.sha256
├── approval.json
├── checkpoint.json
├── events.jsonl
├── dashboard.md / dashboard.json
├── sites/<site_id>/{before,artifact,rollback,restart,runtime,smoke-1,smoke-2}.json
├── FINAL_REPORT.md
├── FINAL_REPORT.json
└── FINAL_VERDICT.txt
```

## Restart postconditions

Stderr such as `Too many open files` is **not** sufficient to declare restart failure.

```text
RESTART_COMMAND_WARNING=1
RESTART_POSTCONDITIONS_PASS=1
RESTART_EFFECTIVE_RESULT=PASS
```

No second restart.

## Closing BYPASS paths

Set `RELEASE_ORCHESTRATOR_REQUIRED=1` so legacy host scripts refuse. Deprecation notices are printed when unset.

## Worktree note (this session)

Shell/git were blocked by UNATTENDED_SAFE (`Shell` default-deny). Code landed in the active checkout. Owner should create:

```bash
git -C /srv/site-factory/repo worktree add \
  -b cursor/site-factory-release-orchestrator-01 \
  /home/claude/wt-site-factory-release-orchestrator-01 \
  origin/main
```

Then cherry-pick / move orchestrator commits onto that branch.
