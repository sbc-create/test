# Comment Language Methodology V1

Status: research foundation for COMMUNITY-COMMENTS-01 (dark mode).  
Does **not** authorize public publication.

## Purpose

Define how comment text is normalized, labeled, and scored for moderation
research. Labels inform human reviewers; they never auto-publish.

## Pipeline

1. **Unicode normalize** — NFC; strip zero-width and bidi override characters.
2. **Sanitize** — strip HTML/tags, `javascript:` / event-handler vectors; plain text only.
3. **Size gate** — 1..4000 characters after sanitize.
4. **PII scan** — email, phone-like, payment-like, messenger/social handles.
5. **Heuristic labels** (`COMMENT_LABELS_HEURISTIC_V1`):
   - sentiment (positive / negative / mixed / neutral)
   - spoiler score
   - toxicity score
   - spam score
   - quality score
   - composite risk score
6. **Persist risk signal** — append-only `community_comment_risk_signals`.
7. **Human moderation** — approve / quarantine / reject / remove / restore.

## Hard invariants

| Invariant | Value |
| --- | --- |
| `auto_publish` | always `false` |
| `COMMENTS_PUBLICATION_ENABLED` | `0` |
| Labels alone may publish | **no** |
| Silent admin rewrite | **forbidden** |
| Fake comment insert | **forbidden** |

## Scoring notes

Scores are calibrated for **precision over recall** in the research stage.
High spam/toxicity/PII → quarantine suggestion, not deletion.
Spoiler suggestion sets the spoiler flag; body remains author-controlled
until a moderator marks spoiler.

## Out of scope (this version)

- Multi-language ML classifiers
- 1000-observation research corpus (parallel agent)
- Public SEO rendering of comment bodies
