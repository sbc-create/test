# Manifest Schema

Schema: `schemas/release-orchestrator/release-manifest.schema.json`
Code: `factory/release_orchestrator/manifest.py`

## Properties

- Immutable after approval (digest binding)
- Canonical JSON (`sort_keys`, compact separators)
- SHA-256 digest
- Schema / structure validation with `additionalProperties` denial
- Expiry (`expires_at`)
- No secrets (key-name scan)
- No duplicate site_ids / domains
- No duplicate services (via registry)
- No same artifact_path with different digests
- Owner approval scope checked separately

## Digest mismatch

If the on-disk manifest changes after approval:

```text
RELEASE_DENIED_MANIFEST_DIGEST_MISMATCH
```
