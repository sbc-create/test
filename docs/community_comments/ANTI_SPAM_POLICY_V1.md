# Anti-Spam Policy V1

## Signals

- Repeated characters / low-entropy bodies
- Unsolicited URLs and promo language
- Duplicate normalized body from same identity on same title (5-minute window)
- Rate limit: 5 comment actions / identity / 60 seconds
- PII solicitation patterns escalate to quarantine, not publish

## Responses

| Signal | Response |
| --- | --- |
| Rate limit | HTTP 429; ledger `community_comment_rate_limit_events` |
| Duplicate | HTTP 409 conflict |
| High spam score | status `QUARANTINED` + risk signal |
| Toxic / PII | status `QUARANTINED` |

## Non-responses

- No auto-ban from a single heuristic hit in V1
- No shadow-publish
- No cross-title auto-block lists in V1 (research stage)
