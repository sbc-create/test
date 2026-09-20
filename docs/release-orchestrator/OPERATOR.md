# Operator guide — Release Orchestrator

## How to add a new site

1. Add/update `config/site-profiles/<site_id>.json` with exact `domains[]` and `seo_profile.indexing_enabled`.
2. Add a row to `config/release-registry.json` with service_name, handlers, smoke_profile, artifact destination.
3. Ensure `expected_indexability` matches the profile (`OPEN`/`CLOSED`).
4. Assign a distinct `design_id` / `template_profile` (run distinctness checks for same-family batches).
5. Build tenant-specific artifacts; put digests into the release manifest.
6. `bin/site-factory-release plan` → `validate` → `record-approval` → `shadow` → (owner) live canary.

New sites stay CLOSED unless the immutable manifest + approval explicitly allow OPEN.

## Required Core registry fields

See `REGISTRY_CONTRACT.md`. Join key is `site_id`; domain must match profile `domains[]` exactly.

## domain / profile / service / artifact / indexability

| Concept | Source |
| --- | --- |
| domain | release-registry.domain ≡ site-profiles.domains[] |
| profile | template_profile + design_id |
| service | service_name (never guessed) |
| artifact | artifact_path + artifact_sha256 in manifest |
| indexability | expected_indexability ≡ seo_profile.indexing_enabled |

## Create release manifest

```text
bin/site-factory-release plan --intake sites.json --release-id rel-… --source-head <40hex> --sites lords-01,lords-02,lords-03 --out release.json
bin/site-factory-release validate --manifest release.json
```

## Owner approval

```text
bin/site-factory-release record-approval --manifest release.json --approval-id apr-… --approved-by owner --out approval.json
```

Bound to release_id + manifest digest + exact site/artifact digests. Replay/expiry blocked.

## Canary order

Manifest `canary_site_id` runs first. Others start only after `POST_DEPLOY_PASS`.

## Resume

```text
bin/site-factory-release resume --release-id … --manifest … --approval …
```

Reads checkpoint; skips `POST_DEPLOY_PASS` sites; does not duplicate deploy/restart.

## Rollback

Default: rollback current failed site only, then stop batch. Prepared before stage with rehearsal.

## Dashboard / report

```text
bin/site-factory-release status --release-id …
bin/site-factory-release report --release-id …
```

Artifacts under `reports/releases/<release_id>/`.

## Never automated without owner approval

- production live canary / mutate
- OPEN↔CLOSED indexability flips
- DNS mutations
- paid operations
- root bootstrap (one-time)
- sysctl / live systemd unit installs beyond the allowlisted runner

Обычный batch не требует ручного SSH/systemctl/curl.
