# Qwen delivery config required

No approved endpoint or credentials exist in this environment.

## Required env (ops-provided)

```text
QWEN_DELIVERY_ENDPOINT=https://example.invalid/qwen/ratings-report
QWEN_DELIVERY_TOKEN_FILE=/etc/site-factory/secrets/ratings/qwen-delivery-token
QWEN_DELIVERY_MODE=dry_run|http_post
```

## Contract

- Read-only observer; write permissions = 0
- Durable outbox table `qwen_delivery_outbox` (see factory/ratings/qwen_delivery.py)
- Dedupe by sha256(cycle_id|report_id|payload_digest)
- Retry delivery only — never re-run ingestion
- Schema validation before enqueue
- Secrets never in report body

Until configured: `QWEN_DELIVERY_CONFIGURED=NO` → Stage4 verdict `NEEDS_QWEN_CONFIG`; timer stays OFF.
