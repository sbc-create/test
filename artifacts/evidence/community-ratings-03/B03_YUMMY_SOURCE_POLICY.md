# Yummy source-policy gate — COMMUNITY-RATINGS-03

## Site indexability

`yummyani.site` is **open** for indexing (`robots.txt` Allow:/; no global X-Robots-Tag noindex).

## Existing Shikimori grant

Stage1–5 / Stage02 evidence scopes Shikimori publication as:

```text
publication_scope=CLOSED_NOINDEX_ANIMEDIA_UNTIL_INDEXING_DECISION
```

Owner Stage02 approval: `SHADOW_AND_PUBLIC_READ_ONLY` applied to Animedia (currently noindex).

Owner Stage03 decision `COMMUNITY-RATINGS-03-CANARY-20260920` authorizes supervised **native-vote canary** only — it does **not** expand Shikimori/derived prior public display onto an open-index Yummy.

## Decision

```text
YUMMY_SOURCE_POLICY_PASS=0
YUMMY_PUBLIC_DISPLAY_ALLOWED=0
YUMMY_DISPLAY_MODE=SHADOW_LOADER_ONLY
```

Actions:

- Wire Next.js community projection **loader** + UI scaffolding.
- Keep public Shikimori badge and Yummy derived prior **hidden** via feature flag on open Yummy.
- Do **not** set Yummy noindex as a workaround.
- Animedia canary proceeds.
- Yummy native canary / public derived display: `BLOCKED_SOURCE_POLICY` until explicit owner grant for open-index publication.
