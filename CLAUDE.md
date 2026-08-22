# Repository guide for Claude sessions

This repository holds the rules, schemas, knowledge pack, and automation that
an **SEO session** operates under. Read this file first; it is the entry point.

## What is here

| Path | Purpose |
| --- | --- |
| `.claude/rules/` | Operating rules for sessions in this repo |
| `.claude/hooks/session-start.sh` | Provisions the environment on session start |
| `.claude/hooks/pretooluse-guard.sh` | Permission guard for every tool call |
| `seo_operator/` | The autonomous SEO editorial operator |
| `config/` | Registries: portfolio, data sources, calendar, backlog, experiments |
| `docs/seo-operator/` | Operator policies, strategies, demos and daily reports |
| `bin/seo-operator` | Operator CLI |
| `docs/knowledge/` | SEO knowledge pack — read before doing SEO work |
| `schemas/` | JSON Schemas every data artifact must validate against |
| `scripts/` | Validation, verification, evidence, and bundle tooling |
| `tests/` | Pytest suite guarding the schemas and validator |
| `docs/verification/` | Committed evidence of verification runs |
| `.github/workflows/` | CI and deployment automation |

## Environment

The SessionStart hook creates `.venv` and installs the pinned dependencies from
`requirements.txt`. It runs automatically in Claude Code on the web. To
provision manually:

```bash
SEO_SESSION_FORCE_SETUP=1 ./.claude/hooks/session-start.sh
```

## Before you commit

Run the full verification and regenerate the evidence record:

```bash
./scripts/verify.sh            # all stages, non-zero exit = failures
./scripts/record-evidence.sh   # refresh docs/verification/latest-run.md
```

CI runs both. `record-evidence.sh --check` fails the build if the committed
evidence disagrees with a fresh run, so a stale record blocks the merge.

## Validating data

```bash
.venv/bin/python scripts/validate_schemas.py                          # schemas compile
.venv/bin/python scripts/validate_schemas.py path/to/seo-audit.json   # validate data
```

Files are matched to schemas by filename prefix: `seo-audit.*.json` validates
against `schemas/seo-audit.schema.json`.

## SEO operator

The operator runs unattended. Start here:

```bash
./bin/seo-operator probe               # what data sources are reachable
./bin/seo-operator dry-run --fixture   # full run against the synthetic tenant
```

Key documents: [`blockers.md`](docs/seo-operator/blockers.md) (what is missing),
[`runbook.md`](docs/seo-operator/runbook.md) (how to operate it),
[`protected-guardrails.md`](docs/seo-operator/protected-guardrails.md) (what it
may never do).

Two properties matter more than the rest:

- **No fabricated data.** A source that cannot be reached reports the metric as
  unmeasured with a reason, never as `0`. A factual claim without an approved
  source cannot be constructed at all.
- **Nothing irreversible.** Every change carries a before/after snapshot and a
  rollback payload before it is applied, and no change reaches more than one
  site or 10% of its pages without an earned verdict.

## Rules that are not negotiable

1. **Never commit directly to `main`.** Work on a branch, open a pull request.
2. **Schemas are authoritative.** If a document and a schema disagree about a
   constraint, the schema is right and the document needs fixing.
3. **Every numeric claim carries a source**; every finding carries evidence.
4. **Do not weaken a schema to make data pass.** Fix the data, or change the
   schema deliberately with the tests updated to match.
5. **Never delete or skip a failing test to get green.**
6. **Never widen beyond canary** without a completed observation and a `keep`
   verdict recorded in `config/experiments.json`.
7. **Never invent a fact.** Dates, cast, ratings, availability and popularity
   come from an approved source or do not appear.

Full detail in [`.claude/rules/seo-session.md`](.claude/rules/seo-session.md).
