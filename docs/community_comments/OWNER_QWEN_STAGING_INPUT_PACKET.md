# Owner input packet — COMMUNITY-COMMENTS-03 real Qwen staging canary

**Authorization:** `COMMUNITY-COMMENTS-QWEN-STAGING-CANARY-20260920-01`  
**Verdict if incomplete:** `BLOCKED_QWEN_RUNTIME_CONFIG`

Do **not** invent endpoint/model/token values. Fill only ops-owned secrets.

## Required inputs

| Item | Value / instruction |
| --- | --- |
| Credential name | `qwen_comments_token` |
| Secret path on host | `/etc/site-factory/secrets/qwen_comments_token` (mode `0400`/`0600`, owner service user) |
| systemd | `LoadCredential=qwen_comments_token:/etc/site-factory/secrets/qwen_comments_token` |
| Env token file | `QWEN_COMMENTS_TOKEN_FILE=%d/qwen_comments_token` |
| Endpoint | `QWEN_COMMENTS_ENDPOINT=https://<host>/...` (HTTPS only; no query secrets) |
| Mode | `QWEN_COMMENTS_MODE=http_post` |
| Model | `QWEN_COMMENTS_MODEL=<provider model id>` |
| Timeout | `QWEN_COMMENTS_TIMEOUT_SEC=20` |
| Caps | `REAL_QWEN_REQUEST_CAP=50`, `REAL_QWEN_INPUT_TOKEN_CAP=100000`, `REAL_QWEN_SPEND_CAP_RUB=100` |

## Unit

`automation/host/systemd/site-factory-comments-qwen-staging.service`

Enable **only** for supervised staging. Production publication/write/postmod/SEO stay `0`.

## Pricing preflight

Before first paid call, owner/provider must confirm projected cost of ≤50 requests ≤ 100 ₽.
If unknown or projected over 100 ₽ → stop with `BLOCKED_QWEN_RUNTIME_CONFIG` / spend gate.

## Forbidden

- Token in Git, `.env`, evidence, journal, exception text, shell history
- Using FakeQwenProvider as a claimed real canary
- Public comment publication
- Push / merge
