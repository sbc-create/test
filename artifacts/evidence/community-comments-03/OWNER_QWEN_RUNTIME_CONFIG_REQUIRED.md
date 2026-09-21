# OWNER ACTION REQUIRED — Qwen runtime configuration for community comments

**Stage:** `COMMUNITY-COMMENTS-03-QWEN-STAGING-CANARY`
**Verdict without this packet:** `BLOCKED_QWEN_RUNTIME_CONFIG_OWNER_ACTION_REQUIRED`
**Authorization referenced below:** `COMMUNITY-COMMENTS-QWEN-STAGING-CANARY-20260920-01`

Everything that does not depend on a live provider is finished and committed.
The only thing missing is a credential and endpoint that **you** must install.
Nothing here may be guessed by the agent: an absent value is `BLOCKED_INPUT`,
never a default.

---

## 1. What was searched, and what was found

Every Qwen runtime configuration in the factory was enumerated (presence and
scope only — no credential body was read or printed):

| Family | Scope it was granted | Configured? | Reusable for comments? |
| --- | --- | --- | --- |
| `ratings_qwen_delivery` (`factory/ratings/qwen_delivery.py`) | ratings daily **report delivery** | NO | **No — `BLOCKED_SCOPE_MISMATCH`** |
| `comments_qwen_postmod` (`factory/community/comments/qwen/provider.py`) | comments post-moderation (this stage) | **NO** | own scope, but absent |
| control-plane Qwen consumer (`docs/ai/control-plane.md`) | Qwen calling *into* the factory API | n/a | Not a credential — opposite direction |

The ratings delivery token was **not** borrowed even as a fallback. Its scope
covers shipping a finished report, not submitting user-authored comment text to
a provider for classification — a different payload and a different data
category. Reusing it would silently widen what the owner approved.

`REUSABLE_FOREIGN_CREDENTIALS = 0`.

---

## 2. The three values required

| # | Name | Requirement |
| --- | --- | --- |
| 1 | `QWEN_COMMENTS_ENDPOINT` | HTTPS URL, port 443, **no** query string, **no** userinfo, **no** fragment. The host must also be admitted to inventory — see §3. |
| 2 | `QWEN_COMMENTS_MODEL` | The provider's model id, exactly as the provider spells it. |
| 3 | `qwen_comments_token` | The API token, installed as a **file** and delivered by systemd `LoadCredential`. Never an env value, never a command-line argument, never in Git. |

---

## 3. Fourth item — the inventory allowlist entry

`.claude/rules/infrastructure.md`: a target absent from `inventory/` does not
exist. The endpoint gate therefore refuses any host that is not listed, **and**
refuses a host listed for some other purpose — an entry admitted for comments
*research* must not double as a moderation provider.

Add to `inventory/network-allowlist.yaml`, with `ref` spelled exactly:

```yaml
  - ref: community-comments-qwen-postmod
    host: <the endpoint host, no scheme, no path>
    purpose: "COMMUNITY-COMMENTS-03: Qwen comment post-moderation (staging canary)"
    methods: [POST]
    token_secret_ref: file:/etc/site-factory/secrets/qwen_comments_token
```

Without this entry the preflight reports
`endpoint_host_not_in_inventory_allowlist` and the canary will not start.

---

## 4. Installing the token safely

On the host, as root:

```bash
install -d -m 0700 -o root -g root /etc/site-factory/secrets
install -m 0400 -o site-factory -g site-factory /dev/null \
  /etc/site-factory/secrets/qwen_comments_token

# Paste the token without it entering shell history or the process table.
# The leading space keeps it out of history on a HISTCONTROL=ignorespace shell.
 systemd-ask-password --echo "Qwen comments token: " \
   > /etc/site-factory/secrets/qwen_comments_token
chmod 0400 /etc/site-factory/secrets/qwen_comments_token
chown site-factory:site-factory /etc/site-factory/secrets/qwen_comments_token
```

Rules:

* The token goes **only** into that file. Not into `.env`, not into
  `Environment=`, not into a unit drop-in, not into Git, not into a shell
  argument, not into evidence, not into the journal.
* Mode must be `0400` or `0600` and owned by the service user. A
  world-readable or group-writable file is reported as
  `INSECURE_WORLD_READABLE` / `INSECURE_GROUP_WRITABLE` and blocks the canary.

---

## 5. The unit that consumes the credential

`automation/host/systemd/site-factory-comments-qwen-staging.service`

It already carries the `LoadCredential` line; fill in the two commented values:

```ini
LoadCredential=qwen_comments_token:/etc/site-factory/secrets/qwen_comments_token
Environment=QWEN_COMMENTS_TOKEN_FILE=%d/qwen_comments_token
Environment=QWEN_COMMENTS_ENDPOINT=https://<host>/<path>
Environment=QWEN_COMMENTS_MODEL=<provider model id>
Environment=QWEN_COMMENTS_MODE=http_post
Environment=QWEN_COMMENTS_TIMEOUT_SEC=20
```

`%d` is systemd's credentials directory. The token is materialised there for
the service process only, and never appears in the unit file itself.

The unit hard-locks the production gates (`COMMENTS_PUBLICATION_ENABLED=0`,
`COMMENTS_API_WRITE_ENABLED=0`, `COMMENTS_QWEN_POSTMOD_ENABLED=0`,
`COMMENTS_SEO_RENDERING_ENABLED=0`) so that enabling the canary cannot enable
publication as a side effect.

Enable it for the supervised run only — this is a `Type=oneshot` staging unit
and must not be left enabled.

---

## 6. Verifying the configuration without revealing the token

Preferred — run the unit itself, which already carries the correct
`LoadCredential` and `%d` expansion, then read the JSON it writes:

```bash
systemctl start site-factory-comments-qwen-staging.service
systemctl status site-factory-comments-qwen-staging.service --no-pager
cat /srv/site-factory/repo/artifacts/evidence/community-comments-03/01-runtime/RUNTIME_PREFLIGHT.json
```

Ad-hoc alternative. Note that `%d` is a *unit-file* specifier and is not
expanded by `--setenv`, so resolve the credentials directory inside the
service instead, via the `$CREDENTIALS_DIRECTORY` systemd exports:

```bash
cd /srv/site-factory/repo
systemd-run --unit=qwen-comments-preflight --wait --collect \
  --property=LoadCredential=qwen_comments_token:/etc/site-factory/secrets/qwen_comments_token \
  --property=WorkingDirectory=/srv/site-factory/repo \
  --setenv=QWEN_COMMENTS_ENDPOINT=https://<host>/<path> \
  --setenv=QWEN_COMMENTS_MODEL=<model> \
  --setenv=QWEN_COMMENTS_MODE=http_post \
  /bin/sh -c 'QWEN_COMMENTS_TOKEN_FILE="$CREDENTIALS_DIRECTORY/qwen_comments_token" \
    exec /usr/bin/python3 -m factory.community.comments.staging_canary'
```

The single quotes matter: `$CREDENTIALS_DIRECTORY` must be expanded by the
service's shell, not by yours.

This prints and writes
`artifacts/evidence/community-comments-03/01-runtime/RUNTIME_PREFLIGHT.json`
containing **only**: endpoint host, model, whether the credential file exists,
its permission status, and the boolean gates. The preflight reads the token's
*metadata* and never its contents, by construction
(`credential_meta()` stats the file; it does not open it).

Expected when correct:

```json
{ "QWEN_PROVIDER_CONFIGURED": "YES", "READY_FOR_REAL_CANARY": true,
  "BLOCKED_REASON": null, "BLOCKING_CHECKS": [] }
```

If a gate is still open, `BLOCKING_CHECKS` names exactly which one.

---

## 7. Running the one supervised canary

Only after §6 reports `READY_FOR_REAL_CANARY: true`, and only with a **new**
authorization id and an explicit spend cap:

```bash
cd /srv/site-factory/repo
.venv/bin/python scripts/comments_qwen_staging_canary.py \
  --provider live \
  --owner-authorization-id <OWNER_AUTHORIZATION_ID> \
  --spend-cap-rub <N>
```

The runner refuses to start if the preflight is not ready, if the
authorization id is missing, or if the spend cap is absent or `<= 0`. It will
**not** silently fall back to the fake provider — a fake is never reported as a
real canary.

Caps enforced in code (`factory/community/comments/qwen/caps.py`), on a durable
ledger outside Git:

| Cap | Value |
| --- | --- |
| `REAL_QWEN_REQUEST_CAP` | 50 requests |
| `REAL_QWEN_INPUT_TOKEN_CAP` | 100 000 input tokens |
| `REAL_QWEN_SPEND_CAP_RUB` | **100 ₽ maximum** |
| `PAID_RETRIES_MAX` | 2 |

**Maximum possible spend for the whole canary: 100 ₽.** The ledger refuses the
call that would cross any cap, and refuses a duplicate `call_id` outright, so a
re-run with the same idempotency key cannot produce a second billed call.

Before the first paid call the provider's price per request must be confirmed
such that 50 requests stay under 100 ₽. If that cannot be confirmed, stop —
do not run the canary.

---

## 8. Rollback / disable

```bash
# Stop and disable the canary unit
systemctl disable --now site-factory-comments-qwen-staging.service

# Engage the comments kill switch (no deploy required)
cd /srv/site-factory/repo
.venv/bin/python -c "from factory.community.comments.kill_switch import \
  KillSwitchCapabilities, save_capabilities; \
  save_capabilities(KillSwitchCapabilities(block_writes=1, stop_worker=1, \
  hide_new_public=1, reason='owner_disable'), actor='owner')"

# Remove the credential entirely
shred -u /etc/site-factory/secrets/qwen_comments_token
systemctl daemon-reload
```

Removing the credential returns the preflight to
`missing_qwen_comments_credential` and the stage to its blocked state. No
comment row is affected: the canary writes only to the isolated staging
database and deletes its own rows.

---

## 9. What remains forbidden

* Public comment rollout — including 1% — is **not** authorized by this packet.
  It is a separate future owner approval. `READY_FOR_PUBLIC_COMMENTS_1PCT=NO`.
* `COMMENTS_API_WRITE_ENABLED_PRODUCTION`, `COMMENTS_PUBLICATION_ENABLED_PRODUCTION`,
  `COMMENTS_QWEN_POSTMOD_ENABLED_PRODUCTION`, `COMMENTS_SEO_RENDERING_ENABLED`
  all stay `0`.
* No production comment rows. The canary runs on the synthetic staging corpus
  only, never on real user comments.
* Never send Qwen: device id, IP, user agent, email, phone, cookie, internal
  moderation ids, system prompts, or secrets. Only the minimal redacted
  staging comment text and a bounded policy context.
* Ratings rollout stays at 1%. `yummyani.site` indexability stays `OPEN`.
  DNS, robots, sitemap and production deploy are untouched.
