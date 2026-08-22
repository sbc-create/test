# Keyword research

Output of this process is a plan validating against
[`keyword-plan.schema.json`](../../schemas/keyword-plan.schema.json).

## The one-to-one rule

**One primary keyword maps to one URL.** Two pages targeting the same primary
keyword compete with each other; the search engine picks one and the other
wastes its internal links. When you find two, the fix is to consolidate, not to
differentiate the titles slightly.

The schema models this by making each entry in `targets` carry exactly one
`keyword` and one `url`.

## Intent classification

Every target declares an `intent`. This drives what the page must contain:

| Intent | The searcher wants | Page type that satisfies it |
| --- | --- | --- |
| `informational` | To understand something | Guide, explainer, documentation |
| `navigational` | To reach a specific place | Homepage, login, named product page |
| `commercial` | To compare before buying | Comparison, review, category page |
| `transactional` | To act now | Product page, pricing, signup |

Intent mismatch is the most common reason a well-optimized page does not rank:
a product page cannot win an informational query regardless of its metadata.
Check what currently ranks for the term — that is the search engine telling you
which intent it has assigned.

## Sourcing numbers

`search_volume` and `difficulty` are estimates from third-party tools, and they
disagree with each other substantially. The schema therefore requires a
`source` string on any target carrying them. Record the tool and the window
(for example, "Search Console impressions, 90-day window").

Rules:

- Never present an estimate as a measurement.
- Never mix sources within one plan without labelling each.
- Prefer first-party data (Search Console impressions and positions) over
  third-party volume estimates when both are available.

## Current position

`current_position` is `null` when the URL does not rank in the tracked range —
explicitly null, never `0` and never omitted-to-mean-unranked. The distinction
between "not ranking" and "not measured" matters when the plan is reread later.

## Prioritization

Rank targets by expected gain, not by volume. A term at position 11 with 500
searches is usually worth more than a term at position 90 with 10,000, because
moving from 11 to 8 is achievable and moving from 90 to 8 is not.

Order of work:

1. Existing pages ranking 5-15 for terms with real volume (largest, cheapest gain).
2. Pages ranking 1-4 where intent is matched but metadata is weak.
3. Genuine content gaps where no page targets a relevant term.
4. Everything else.
