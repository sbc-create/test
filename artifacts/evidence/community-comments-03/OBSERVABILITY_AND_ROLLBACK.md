# Observability and rollback — COMMUNITY-COMMENTS-03

Stage: `COMMUNITY-COMMENTS-03-QWEN-STAGING-CANARY`
Evidence: `07-canary/STAGING_CANARY_RESULTS.json`, `08-tests/TEST_RUNS.log`

---

## 1. What is observable, and where it comes from

| Signal | Source | Proven by |
| --- | --- | --- |
| Provider call count / duplicates | `CountingProvider` + cap ledger `call_ids` | `duplicate_idempotency` section; `record_call` rejects a repeated `call_id` |
| Spend / tokens / requests against caps | `factory/community/comments/qwen/caps.py`, durable ledger outside Git | `caps_public_status()` in `01-runtime/RUNTIME_PREFLIGHT.json` |
| Schema validity per response | `validate_decision_v2` with `request_id` correlation | `SCHEMA_VALIDATION_PASS`, `invalid_json` section |
| Latency p50 / p95 / max | per-task timing in the harness | `latency_ms` block (local pipeline time; excludes real network) |
| Queue depth / oldest age | `DegradedController` SLA thresholds | `degraded_mode` section |
| Moderation state transitions | `community_comment_moderation_events` rows written by `apply_decision` | `state_machine`, `revision_race`, `delete_race` sections |
| Kill-switch flips | `kill_switch_audit.jsonl` + `community_comment_kill_switch_audit` | `kill_switch` section, `audit_records > 0` |
| Worker leases / crash resume | `community_comment_moderation_jobs.lease_owner`, `lease_until`, `attempts` | `concurrency_lease`, `crash_resume` sections |

**Deliberately not observable:** comment bodies. Evidence records
`text_digest`, `text_len`, labels, outcomes and timings only. This was
verified, not assumed — the finished evidence file was searched for fragments
of all 40 corpus bodies and none appear (`USER_COMMENT_TEXT_IN_EVIDENCE=0`).

---

## 2. Failure behaviour — what happens when the provider misbehaves

Every one of these was exercised, and in none of them does a comment become
public:

| Failure | Observed outcome | Comment state |
| --- | --- | --- |
| Timeout | `PROVIDER_ERROR` after bounded retries | not published |
| Malformed JSON | `PROVIDER_ERROR` | not published |
| Schema-valid but missing fields | `PROVIDER_ERROR` | not published |
| Forbidden keys smuggled in response | `PROVIDER_ERROR` (`additionalProperties: false`) | not published |
| `request_id` mismatch (crossed response) | `PROVIDER_ERROR` | not published |
| Fully compromised provider returning `ALLOW` confidence 1.0 on an injection payload | rejected; 0 bypasses | not published |
| Circuit open / backlog / stale queue | `PENDING_MODERATION_DEGRADED` | held, and that status is not publicly visible |

The governing property: **the provider classifies, the local policy engine
decides.** A decision only moves a row if it passes schema validation, matches
the current revision, and the transition is legal in the state machine.

---

## 3. What Qwen never receives

Enforced by `assert_payload_safe()`, which walks the payload at every depth
and raises rather than warns:

- device id, IP, user agent, cookie, identity id, email, phone, authorization
  headers, tokens — any forbidden key at any nesting level
- raw PII spans from the original text: the payload carries only the redacted
  form (`[EMAIL_REDACTED]`, `[PHONE_REDACTED]`, `[IP_REDACTED]`,
  `[SECRET_REDACTED]`)
- internal moderation ids (`comment_id`, `job_id`, `moderation_id`)
- the system prompt inside the untrusted data envelope

Comment text travels in `data_envelope.comment_text`, structurally separated
from `system_instructions`, which tell the model to treat that field as data.

---

## 4. Rollback

Nothing in this stage is irreversible, and nothing reached production.

**Canary rows.** The runner deletes every synthetic row it created and then
re-counts: `CANARY_COMMENT_ROWS_REMAINING=0`, with jobs and moderation events
also at zero. The staging database is a dedicated file; the runner refuses to
open anything else, and refuses any path whose name looks like production.

**Kill switch** (no deploy required):

```bash
cd /srv/site-factory/repo
.venv/bin/python -c "from factory.community.comments.kill_switch import \
  KillSwitchCapabilities, save_capabilities; \
  save_capabilities(KillSwitchCapabilities(block_writes=1, stop_worker=1, \
  hide_new_public=1, reason='rollback'), actor='owner')"
```

Restore by saving `KillSwitchCapabilities()` with the default fields. Both
directions append to the audit trail.

**Provider disable:**

```bash
systemctl disable --now site-factory-comments-qwen-staging.service
shred -u /etc/site-factory/secrets/qwen_comments_token
```

The preflight then returns to `missing_qwen_comments_credential` and refuses
to start a canary.

**Code rollback.** Every change is on `cursor/community-comments-01` in
thematic commits; nothing was pushed or merged (`PUSH_PERFORMED=0`,
`MERGE_PERFORMED=0`).

---

## 5. Untouched by this stage

- Production comment flags stay `0` (write, publication, postmod, SEO rendering)
- No production comment rows inserted or published
- Ratings public-write rollout stays at 1%
- `yummyani.site` indexability stays `OPEN`
- No changes under `inventory/`, `automation/ansible/`, `config/` — so no DNS,
  robots, sitemap or deploy mutations
- Public comments rollout at 1% remains **not authorized**; it is a separate
  future owner approval
