# Frequency / taxonomy / relevance policy

Status: dry-run only. Nothing described here calls Topvisor, GSC, Webmaster,
or any other network endpoint, and nothing here writes to a live keyword
plan. `SPEND_LIMIT` for this layer is `0` by construction — there is no code
path in it that can spend money, because there is no code path in it that
calls anything paid at all.

## Why this exists

Before any query is ever proposed for a Topvisor sync, three questions have
to be answered honestly and separately, because conflating them is the most
common source of bad SEO automation:

1. How much search volume does this query actually have, and how sure are we?
2. Does this query actually belong on this URL, or does it only share words
   with what the URL is about?
3. Does more than one site in the portfolio think it owns this query?

This module answers all three without ever fabricating an answer when the
honest answer is "we don't know."

## The five entities

| Entity | Module | What it is | What it is *not* |
| --- | --- | --- | --- |
| `QueryObservation` | `seo_operator.query_observations` | Real impressions/clicks/average position from Yandex Webmaster or Google Search Console. | Not a rank check, not an index check. |
| `RankObservation` | `seo_operator.query_observations` | An approved query's tracked position from Topvisor. | Not proof the URL is indexed. |
| `SearchIndexObservation` | `seo_operator.query_observations` | Provider-specific evidence that a URL is (or is not) in a search index. | The *only* entity here allowed to assert index presence. |
| `IndexabilityObservation` | `seo_operator.query_observations` | HTTP/robots/canonical/sitemap/rendered evidence for a URL. | Not proof of index presence, however complete. |
| `TopicalRelevanceDecision` | `seo_operator.relevance` (as `RelevanceDecision`) | A versioned verdict on whether a query belongs on a URL. | Not a keyword-overlap score. |

These are kept as five separate dataclasses on purpose. A `RankObservation`
has no field that could be misread as "indexed"; `IndexabilityObservation`
exposes `proves_indexed`, which is hard-coded `False`, specifically so a
caller reaching for "is it indexed?" on indexability evidence gets an
explicit refusal instead of an attribute that happens to look truthy.

### Forbidden inferences (enforced, not just documented)

* Position ⇏ indexed. `RankObservation` cannot express an index claim.
* Crawlable ⇏ indexed. `IndexabilityObservation.proves_indexed` is always `False`.
* Missing data ⇏ zero. Every numeric field that can be absent is `None`, and
  `seo_operator.frequency_policy.classify_frequency` returns `UNKNOWN`
  rather than a numeric default whenever a measurement is missing or stale.
* A query cannot carry `noindex`. `noindex_directive(..., subject_kind=...)`
  raises `ObservationError` for anything other than `subject_kind="url"`.
* Frequency, clustering and SERP signals are not a command to create a page.
  Nothing in this layer creates content; it only classifies and decides
  relevance for queries against URLs that already exist.
* An irrelevant impression is not automatic grounds to noindex a URL. This
  layer has no code path that changes a URL's indexability at all — that
  stays with `factory/seo` and the site's own render pipeline.

## HF / MF / LF as versioned policy, not hardcoded numbers

`seo_operator.frequency_policy` reads band boundaries from
`config/frequency-band-policy.json` (schema:
`schemas/frequency-band-policy.schema.json`). The current policy
(`ru-video-portfolio-default`, revision 1) is:

| Band | Monthly volume | Region | Searchers | Freshness limit |
| --- | --- | --- | --- | --- |
| LF | 0 – 999 | 213 (Moscow) | yandex, google | 90 days |
| MF | 1,000 – 9,999 | | | |
| HF | 10,000+ | | | |

These numbers are a **placeholder default**, not an owner-supplied fact about
real traffic. `config/frequency-band-policy.json`'s own `note` field says so.
Recalibrating them against real Wordstat/GSC data is expected to produce
revision 2 with a new digest — never an in-place edit of revision 1.

Every policy document carries a `digest`: a sha256 hex hash over its own
canonical JSON form (sorted keys, compact separators) with the `digest`
field itself removed. `load_policy()` recomputes it on every load and refuses
to load a file whose stored digest does not match — so an edit that forgets
to regenerate the digest fails closed instead of silently taking effect.

### UNKNOWN, always

A `VolumeMeasurement` with `value=None` (nothing returned by the source) or
a `measured_at` older than `freshness_max_age_days` **always** classifies as
`FrequencyBand.UNKNOWN`, tagged `Freshness.MISSING` or `Freshness.STALE`
respectively. There is no code path that turns "no data" into `0`, and no
code path that keeps reporting a stale measurement's last known band.

## Relevance decisions

`seo_operator.relevance.decide_relevance` reuses
`seo_operator.priority.QueryClass` for intent — `title_exact`,
`title_season`, `watch_intent`, `discovery`, `informational`, `navigational`,
`unclassified` — rather than inventing a second taxonomy
(see `docs/seo-operator/query-taxonomy.md`).

The verdicts:

* `APPROVED_RELEVANT` — landing page's taxonomy matches the query's, no title
  homonymy left unresolved, rendered evidence confirms the page answers the
  query, and no other site in the portfolio already claims the same
  (normalized query, taxonomy) pair.
* `OFF_TOPIC` — the landing page is tagged with a different taxonomy id than
  the query targets, or rendered evidence contradicts the query.
* `AMBIGUOUS` — the query's title text matches more than one distinct
  entity (homonymy) and nothing has resolved which one is meant.
* `SUSPICIOUS_REQUIRES_REVIEW` — either no rendered-page evidence exists to
  confirm the match, or a different site already owns the same
  (query, taxonomy) pair (a portfolio non-compete / query-ownership conflict).

### Allowed example

```
query="боевики онлайн" (watch_intent)
landing_page_taxonomy_id == taxonomy_id == "genre.action"
rendered_evidence_confirmed = True
no other site owns ("боевики онлайн", "genre.action")
→ APPROVED_RELEVANT
```

### Forbidden examples

```
query="интерстеллар" targets taxonomy_id="title.interstellar-2014"
landing_page_taxonomy_id="genre.action"          # wrong page
→ OFF_TOPIC, never APPROVED_RELEVANT no matter how well the words match
```

```
query="интерстеллар" homonym_entity_ids=(
    "movie-interstellar-2014", "ep-interstellar-cover-band"
)
→ AMBIGUOUS — title text alone never resolves this
```

```
lords-01 approves ("боевики онлайн", "genre.action")
lords-02 later submits the identical (query, taxonomy) pair
→ SUSPICIOUS_REQUIRES_REVIEW for lords-02, not a second APPROVED_RELEVANT
```

A query is never approved on word overlap alone — every path to
`APPROVED_RELEVANT` requires `rendered_evidence_confirmed is True`.

## The `approved_relevant_manifest` contract

Schema: `schemas/approved-relevant-manifest.schema.json`. Built and validated
by `seo_operator.approved_relevant_manifest`. Fields, per entry: `site_id`,
`domain`, `site_ready`, `query`, `normalized_query`, `taxonomy_id`, `intent`,
`cluster`, `frequency_band`, `frequency_measurement` (value/source/measured_at/
region/searcher/freshness), `target_url`, `relevance_decision`
(verdict/reason/policy_revision/decided_at), `evidence` (typed references to
one of the five entities above or a manual review), `owner`
(approved_by/approved_at), `created_at`, `expires_at`.

The document itself carries `manifest_id`, `version`, `revision`, `digest`,
`generated_at`, `site_authority_source`, `band_policy_revision`.

* **Deterministic order, reproducible digest.** `build_manifest()` sorts
  entries by `(site_id, normalized_query, target_url)` before hashing, so the
  digest never depends on the order entries were assembled in. The digest is
  a sha256 hex hash of the canonical JSON form with `digest` removed —
  the same technique `factory.site_engine.fingerprint.digest()` uses
  elsewhere in this repository, reimplemented locally here rather than
  imported, since `seo_operator` does not otherwise depend on
  `factory.site_engine`.
* **Only `APPROVED_RELEVANT` is ever sync-eligible.** `ManifestEntry.sync_eligible`
  (and the document-level `sync_eligible_entries()`) require the verdict to be
  `APPROVED_RELEVANT`, non-empty `evidence`, and `site_ready=True`. Nothing in
  this module *acts* on that eligibility — it only computes the filter a
  later, separately authorized sync step would use.
* **Fail-closed on unknown site or domain.** `build_entry()` resolves
  `(site_id, domain)` against a `SiteAuthority` and raises `ManifestError`
  ("`BLOCKED_INPUT`") for anything it cannot resolve — including a right
  `site_id` with a wrong `domain`.

### `validate_manifest()` — dry-run validation

```
from seo_operator.approved_relevant_manifest import validate_manifest
import json
data = json.loads(open("path/to/manifest.json").read())
problems = validate_manifest(data)
```

Checks the document against the JSON Schema and recomputes/compares its
digest. Returns a list of problem strings (empty means clean). This performs
no I/O beyond reading the schema file and the document passed to it — no
network call, no Topvisor client, no `--apply`.

## Site/domain authority: what this task found, and the gap it did not resolve

There are two site registries in this repository:

* `config/portfolio.json` (`schemas/portfolio-registry.schema.json`) — an
  owner-maintained editorial registry. On this branch it is **empty**; its own
  `note` field says it describes a future set of sites, filled in by the
  owner, and is never inferred automatically.
* `sites/*/package.yaml`, read through `seo_operator.factory_bridge` — the
  factory's own site packages. That module's docstring states this is "the
  single source of truth for which sites exist" from the operator's point of
  view.

`seo_operator.site_authority.load_site_authority()` binds to the second one,
matching what `seo_operator.factory_bridge` and `seo_operator.cli
factory-portfolio` already do — this avoids adding a third registry and
avoids silently picking a side other operator code has not picked.

This surfaced a real, pre-existing inconsistency that this task does not
resolve: `config/site-profiles/yummyani-*.json` (and the corresponding
`factory/topvisor/manifest.py` projects) name three `yummyani.*` domains that
have no matching `sites/yummyani-*/package.yaml` in this working tree, so
`seo_operator.site_authority` cannot resolve them today. None of the six
real domains currently have `production_authorized: true` and
`content_source.rights_confirmed: true` together, so `site_ready` is `False`
for all of them — meaning no entry naming a real site is `sync_eligible`
today regardless of its relevance decision. That is the correct fail-closed
outcome given the current state of those packages, not a bug in this policy
layer. Populating the missing `yummyani-*` packages, or deciding whether
`config/portfolio.json` should ever become a second recognised authority, is
an owner decision outside this task's scope, per `CLAUDE.md`'s conflict
threshold (this does not touch license, content rights, security, data,
domain, an irreversible operation, or publication — so it does not block
this dry-run work; it only limits what today's data can prove).

## What this deliberately does not do

* No Topvisor import, `add/keywords_2/keywords`, or any mutation of
  `factory/topvisor/manifest.py`. That manifest remains the operator's
  separately-curated, hand-reviewed keyword list; this policy layer is
  upstream of it and produces no import into it in this change.
* No `checker/go`, volume, clustering, snapshot, snippet, index-checker,
  watcher, audit, or competitor-research call — paid or otherwise.
* No reading or printing of any API token or credential.
* No production, DNS, indexing, PR76/77/80/81, or Content Runtime change.
* No player/provider/video path change.
