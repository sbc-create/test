# Owner setup — Qwen comments postmod credential

Live Qwen staging canary is **blocked** until ops provides runtime config.

## Required (do not invent values)

| Item | Env / systemd |
| --- | --- |
| Endpoint | `QWEN_COMMENTS_ENDPOINT` |
| Token file | `QWEN_COMMENTS_TOKEN_FILE` via `LoadCredential=` |
| Mode | `QWEN_COMMENTS_MODE=http_post` |

Mirror pattern: `factory/ratings/qwen_delivery.py` (`QWEN_DELIVERY_*`).

## Example unit fragment (placeholder paths only)

```ini
[Service]
LoadCredential=qwen_comments_token:/etc/site-factory/secrets/qwen_comments_token
Environment=QWEN_COMMENTS_TOKEN_FILE=%d/qwen_comments_token
Environment=QWEN_COMMENTS_ENDPOINT=
Environment=QWEN_COMMENTS_MODE=http_post
ExecStart=/usr/bin/python3 -m factory.community.comments.worker
```

## Rules

- Secret never in Git, evidence, journal, exception text, or `.env.example` real values.
- Production worker enable requires separate owner approval.
- Until configured: use `FakeQwenProvider` for tests/canary; `discover_config()["configured"]==False`.

## Status this stage

```text
QWEN_PROVIDER_CONFIGURED=NO
QWEN_REAL_CANARY_EXECUTED=0
BLOCKED_QWEN_RUNTIME_CONFIG=1
```
