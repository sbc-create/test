# Rollback COMMUNITY-RATINGS-06

## One-shot kill / disable writes
```bash
PYTHONPATH=/home/claude/wt-ratings-ingestion-01 \
  python3 -c 'from factory.community.rollout import trigger_kill_switch, as_public_dict; print(as_public_dict(trigger_kill_switch("owner_manual")))'
# or
PYTHONPATH=/home/claude/wt-ratings-ingestion-01 python3 -c 'from factory.community.rollout import disable_public_writes, as_public_dict; print(as_public_dict(disable_public_writes()))'
```

Also set overlay `PUBLIC_NATIVE_WRITES_ENABLED=0` in
`/srv/sites/yummyani-staging/runtime/overlays/yummyani.site/community-ratings-flags.json`.

## Guarantees
- ROLLBACK_PRESERVES_REAL_VOTES=1 (no DB restore unless corruption)
- ROLLBACK_PRESERVES_OPEN_INDEXABILITY=1
- ROLLBACK_DOES_NOT_ENABLE_COMMENTS=1
