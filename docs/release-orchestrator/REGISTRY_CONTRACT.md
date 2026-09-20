# Registry Contract

## Authority

There is **one** Core identity source: `config/site-profiles/*.json`.

Ops fields required by the Release Orchestrator live in `config/release-registry.json` and are **joined** by `site_id`. Domains in the overlay **must** appear in the profile `domains[]`.

Schema: `schemas/release-orchestrator/release-registry.schema.json`.

## Required fields (per site)

```text
site_id domain www_policy site_family template_profile design_id
repository source_branch build_command artifact_type artifact_destination
runtime service_name container_name_if_any health_url version_url
smoke_profile expected_indexability robots_policy sitemap_policy
canonical_policy analytics_policy deploy_handler restart_handler
rollback_handler data_sources owner_state enabled
```

## Exact-domain lookup

```python
ReleaseRegistry.by_domain("lordfilm47.space")  # OK
ReleaseRegistry.by_domain("lordfilm47.org")     # RegistryError — no TLD fallback
ReleaseRegistry.by_domain("film47.space")       # RegistryError — no substring
```

Forbidden:

- policy by TLD
- fallback `.site/.org/.biz`
- substring matching
- hardcoded allowlists outside the registry
- guessed systemd units
- one `service_name` for two `site_id`s without an explicit shared-service contract

## Handlers

Handlers are allowlisted verbs in `ALLOWED_HANDLERS`, never free-form shell.
