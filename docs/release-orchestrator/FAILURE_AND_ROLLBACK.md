# Failure and Rollback

## Default policy

```text
FAILURE_POLICY=ROLLBACK_CURRENT_SITE_AND_STOP_BATCH
```

Already successful sites are **not** auto-rolled back if their checks stay green.

## Current failed site

1. rollback
2. restart once
3. verify previous build
4. smoke rollback
5. mark `ROLLED_BACK`
6. stop batch

## Prepare before deploy

```text
ROLLBACK_PREPARED=1
ROLLBACK_DIGEST_MATCH=1
ROLLBACK_REHEARSAL_PASS=1
```

Code: `factory/release_orchestrator/rollback.py`

## Atomic-all

`ROLLBACK_ALL_ATOMIC` is schema-ready but **not** the default and not used in shadow runs.
