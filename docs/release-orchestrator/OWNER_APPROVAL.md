# Owner Approval

Schema: `schemas/release-orchestrator/owner-approval.schema.json`
Code: `factory/release_orchestrator/approval.py`

## Binding

Approval is bound to:

```text
release_id
manifest_digest
exact_site_ids
exact_artifact_digests
allowed_indexability_changes
allowed_dns_changes
allowed_paid_operations
expiry
```

## Rules

- One approval cannot be reused for another manifest digest
- Expired approvals are rejected (`EXPIRED_APPROVAL_BLOCKED`)
- After successful batch completion: `OWNER_APPROVAL_FINAL_STATE=CONSUMED`
- Re-running the same release ID with a completed checkpoint does **not** redeploy; it reads checkpoint and exits PASS without consuming again

## CLI

```text
bin/site-factory-release record-approval --manifest … --approval-id … --approved-by … --out …
bin/site-factory-release approve-status --approval …
```
