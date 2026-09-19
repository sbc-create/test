# Stage 4 input (NOT STARTED)

Prerequisites from Stage 3 `PASS_CLOSED_PRODUCTION_CANARY`:

1. Confirm daily ramp stage **100 accepted/day** (manual); scheduler remains off until confirmed.
2. Configure read-only Qwen delivery channel (`QWEN_DELIVERY` currently `BLOCKED_NO_CONFIG`).
3. Second consecutive closed production run + coverage report.
4. Separate written decision for `AMD_PUBLIC_INDEXED_PUBLICATION` before any indexing change.
5. Do **not** auto-ramp 100→250→500.

Out of scope until explicit go: enable systemd timer, open indexing, mutate robots/DNS/nginx, push/merge.
