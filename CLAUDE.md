# Repository guide for Claude sessions

This repository holds the rules, schemas, knowledge pack, and automation that
an **SEO session** operates under. Read this file first; it is the entry point.

## What is here

| Path | Purpose |
| --- | --- |
| `.claude/rules/` | Operating rules for sessions in this repo |
| `.claude/hooks/session-start.sh` | Provisions the environment on session start |
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

## Rules that are not negotiable

1. **Never commit directly to `main`.** Work on a branch, open a pull request.
2. **Schemas are authoritative.** If a document and a schema disagree about a
   constraint, the schema is right and the document needs fixing.
3. **Every numeric claim carries a source**; every finding carries evidence.
4. **Do not weaken a schema to make data pass.** Fix the data, or change the
   schema deliberately with the tests updated to match.
5. **Never delete or skip a failing test to get green.**

Full detail in [`.claude/rules/seo-session.md`](.claude/rules/seo-session.md).
