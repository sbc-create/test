# SEO session repository

Rules, schemas, knowledge pack, automation and an **autonomous SEO editorial
operator** for a portfolio of sites. The repository is set up so that a fresh
Claude Code cloud session can clone it and start work with no manual setup.

> **Состояние.** Контур реализован и проверен: 260 тестов, 8 стадий верификации.
> Реальных сайтов под управлением **нет**, источники данных **не подключены** —
> см. [`docs/seo-operator/blockers.md`](docs/seo-operator/blockers.md).
> Всё показанное в демонстрациях выполнено на синтетическом тенанте.

## Quick start

```bash
# Provision the environment (automatic in Claude Code on the web)
SEO_SESSION_FORCE_SETUP=1 ./.claude/hooks/session-start.sh

# Run every check
./scripts/verify.sh
```

## Оператор

```bash
./bin/seo-operator probe               # доступность источников
./bin/seo-operator dry-run --fixture   # полный прогон на синтетическом тенанте
.venv/bin/python scripts/demo_canary.py     # canary, ухудшение, откат
.venv/bin/python scripts/demo_editorial.py  # анонс, релиз, снятие
```

## Layout

```
seo_operator/              Guardrails, конвейер, эксперименты, планировщик
config/                    Реестры: портфель, источники, календарь, backlog
bin/seo-operator           CLI
docs/seo-operator/         Политики, стратегии, демонстрации, отчёты
.claude/
  settings.json              Hook registration + permission rules
  hooks/pretooluse-guard.sh  Permission guard for every tool call
  hooks/session-start.sh     Environment provisioning
  rules/seo-session.md       Operating rules
docs/
  knowledge/                 SEO knowledge pack
  verification/              Committed evidence of verification runs
  BASE_COMMIT.md             Accepted base commit record
schemas/                     JSON Schemas for SEO data artifacts
scripts/
  validate_schemas.py        Validate data against schemas
  verify.sh                  Run all checks
  record-evidence.sh         Write the committed evidence record
  build-bundle.sh            Package schemas + knowledge into dist/
tests/                       Pytest suite and fixtures
.github/workflows/           CI and deployment automation
```

## Schemas

| Schema | Describes |
| --- | --- |
| `seo-audit.schema.json` | Output of a technical SEO audit run |
| `page-metadata.schema.json` | On-page metadata for a single URL |
| `keyword-plan.schema.json` | Keyword targeting plan |
| `portfolio-registry.schema.json` | The sites under management |
| `data-source-registry.schema.json` | Data sources and their provisioning state |
| `editorial-sources.schema.json` | Approved sources for factual claims |
| `editorial-calendar.schema.json` | Per-site editorial calendar |
| `content-backlog.schema.json` | Per-site content backlog |
| `experiment-registry.schema.json` | Experiments, verdicts and evidence |

Validate data against them:

```bash
.venv/bin/python scripts/validate_schemas.py tests/fixtures/seo-audit.valid.json
```

Files match schemas by filename prefix, so name data files
`<schema-stem>.<label>.json`.

## Verification

`scripts/verify.sh` runs eight stages: JSON parses, schemas compile, fixtures
validate (including that deliberately-invalid fixtures are *rejected*),
registries validate, guardrails hold, workflows parse, lint, and tests. Its exit
code is the number of failed stages.

`scripts/record-evidence.sh` writes the result to
`docs/verification/latest-run.md` and commits it as evidence. CI runs
`record-evidence.sh --check`, which fails if the committed record no longer
matches a fresh run.

## Contributing

Read [`CLAUDE.md`](CLAUDE.md) and
[`.claude/rules/seo-session.md`](.claude/rules/seo-session.md) first. Work on a
branch; `main` is never committed to directly.
