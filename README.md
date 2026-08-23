# DLE Site Factory

Фабрика повторяемого создания, проверки, публикации, обновления и отката сайтов на
DataLife Engine 20.0.

```bash
pip3 install -r requirements.txt
python3 -m factory validate --site pilot-local     # проверить пакет
python3 -m factory deploy   --site pilot-local     # собрать, выкатить, проверить
bash tests/run-all.sh                              # полный прогон всех уровней
```

## С чего начать

| Вопрос | Документ |
|--------|----------|
| Как устроена фабрика | `docs/ARCHITECTURE.md`, `adr/` |
| Как ввести новый сайт | `docs/NEW_SITE.md` |
| Как подключить новый домен | `docs/NEW_DOMAIN.md` |
| Как эксплуатировать | `docs/OPERATIONS.md` |
| Как устроен управляющий сервер | `docs/INFRASTRUCTURE.md` |
| Сколько сайтов помещается и когда нужен второй сервер | `docs/CAPACITY.md` |
| Что восстанавливать после сбоя | `docs/DISASTER_RECOVERY.md` |
| Как выкатывать и откатывать | `docs/DEPLOY.md`, `docs/ROLLBACK.md` |
| Правила безопасности | `docs/SECURITY.md` |
| Чего не хватает для production | `docs/INPUT_REQUEST.md` |
| Что зафиксировано как факт | `knowledge/FACTS.md`, `knowledge/SOURCE_REGISTRY.yaml` |

## Текущее состояние

- Пилот проходит полный конвейер на одноразовой локальной цели: 48 маршрутов,
  6 ворот качества, backup с подтверждённым восстановлением, откат с health-проверкой.
- **DLE не устанавливается**: лицензионный дистрибутив и профиль путей не переданы,
  а угадывать структуру каталогов запрещено. Гейт — `BLOCKED_INPUT`.
- **Production недоступен**: ни одного SSH-хоста, DNS-зоны и лицензии не передано.
- **CDN Video Hub не интегрирован**: создана только extension point.

Полный список недостающих входных данных — `docs/INPUT_REQUEST.md`.

---

# SEO-оператор

Ниже — правила и описание SEO-оператора, перенесённого из ветки
`claude/seo-operator`. Они дополняют правила фабрики выше и не отменяют их:
при расхождении действует фабрика.

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
