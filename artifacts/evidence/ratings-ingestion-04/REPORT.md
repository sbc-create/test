# Stage 4 REPORT — first launch

## Verdict

```text
VERDICT=NEEDS_QWEN_CONFIG
STAGE3_TECHNICAL_CANARY=PASS_WITH_OPEN_GATES
READY_FOR_SUPERVISED_DAILY_100_PILOT=CONDITIONAL
READY_FOR_DAILY_500=NO
READY_FOR_AUTONOMOUS_PRODUCTION=NO
RATINGS_STAGE4_CAN_BE_CLOSED=NO
```

## Why not PILOT_STARTED

All technical gates except **Qwen delivery configuration** pass. No approved
endpoint/credentials exist; durable outbox + dry-run receipt were exercised,
but `QWEN_DELIVERY_CONFIGURED=NO` blocks timer enable per Stage 4 contract.

AMD recurring fetches are **disabled** (`AMD_SOURCE_DISABLED_PERMISSION_MISSING`);
last-good AMD observations preserved. Shikimori policy resolved (GraphQL only).

## Global coverage (not canary 150)

See `GLOBAL_COVERAGE.json`. Denominator = lords-01 catalog (53548 titles) with
per-source eligibility. Stage 3 `100/150` is explicitly excluded as global %.

## Pilot

Timer **not** enabled. Closeout tool: `python -m factory.ratings.stage4_closeout`.
After ops provides Qwen config and AMD grant (if AMD desired), re-run Stage 4
enable checklist before supervised Daily-100.
