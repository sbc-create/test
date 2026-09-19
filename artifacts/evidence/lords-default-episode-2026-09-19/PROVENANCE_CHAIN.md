# PROVENANCE_CHAIN

```text
declared START_HEAD 7dc251d
  → worktree automation/host/lords-frontend.py @ start
      sha256 a51dade469321e3078b8a7eee124e5ac936f286a33c28f327368bfbfabb85346
      (= git blob 8ececc6c:automation/host/lords-frontend.py)
      NO awaiting literal; hub calls episode=1; aggregators kp|mdl|mali only

release-manifest-lords-01.json (canary-004 evidence)
  → source_commit 8ececc6c… ; build_id 20260913T2300Z-8ececc6c-nova
  → artifact_sha256 a51dade…  (matches old worktree blob)

live template-manifest.json (/srv/lords/.frontend/)
  → source_commit "7dc251d"   ← patched label
  → build_id 20260913T2300Z-8ececc6c-nova
  → artifact_sha256 a51dade…  ← claim
  → built_at 2026-09-14T07:42:54Z

live runtime file /srv/lords/.frontend/lords-frontend.py
  → sha256 06e991c3e558621c494e1150483b98eca67f2fcdc62ccaf0b165adf3e5b33432
  → byte-identical to wt-animedia-finalization-01 @ 720825e
  → HAS awaiting literal + cvh + выбрать_доступную_серию
  → mtime 2026-09-19T19:41:41Z

live process lords-nova-01 (port 9110)
  → PID 3690779 started 2026-09-19T03:43:05Z
  → still serving awaiting hub HTML after file replace
  → STALE_PROCESS=1

live player-lords-01.json
  → publisher_id 10238 ; source_mode provider-id
  → exact episode route: data-aggregator=cvh + title UUID

generator of claimed build 8ececc6c
  → canary-dry-run: source path /home/claude/wt-lords-r2/automation/host/lords-frontend.py
  → NOT the process that currently answers lordfilm47.space
```

## Marker mismatch reason

Footer / meta `7dc251d` comes from manifest `source_commit` (and/or `LORDS_TEMPLATE_REVISION` env historically), **not** from hashing the executing bytecode.
Build id `8ececc6c` is a frozen label on a later file that no longer matches that digest.
