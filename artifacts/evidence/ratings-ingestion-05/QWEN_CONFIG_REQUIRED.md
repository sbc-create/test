# QWEN_CONFIG_REQUIRED

Stage 5 supervised cycle may proceed without Qwen delivery.
Daily timer enable requires configured delivery + ACK.

## Status

- QWEN_DELIVERY_CONFIGURED=NO
- endpoint_set=False
- token_file_exists=False
- mode=unset

## Required fields (exactly as used by code)

- `QWEN_DELIVERY_ENDPOINT — HTTPS URL for report POST`
- `QWEN_DELIVERY_TOKEN_FILE — path to token file (mode 0600); contents never logged`
- `QWEN_DELIVERY_MODE — dry_run | http_post`

## Outbox item schema

- report_id
- run_id / cycle_id
- report_digest / payload_digest
- created_at
- delivery_state / status
- attempt_count / attempts
- last_error_class / last_error
- delivered_at (in receipt)
- ack (in receipt)

Do not invent endpoint, token, channel, project ID, or recipient.
