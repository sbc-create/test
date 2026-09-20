# Five-Site Intake

Schema: `schemas/release-orchestrator/site-intake.schema.json`
Code: `factory/release_orchestrator/intake.py`

## Intake fields

```text
site_id domain family template_profile desired_indexability
data_source catalog_source details_source player_policy ratings_policy
content_policy analytics_policy seo_policy owner_config
```

## Pipeline

1. register drafts
2. check domains
3. check site_id conflicts
4. assign distinct profiles
5. check template distinctness (`distinctness.py`)
6. build artifacts
7. offline gates
8. form immutable batch manifest
9. request one owner approval
10. canary-first release

## Indexing

New sites register as **CLOSED** drafts. They do not auto-OPEN because a neighbour is OPEN. OPEN requires explicit release-manifest permission + approval flag.
