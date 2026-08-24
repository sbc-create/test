# DLE Site Factory — постоянные правила

Фабрика повторяемого создания сайтов на DataLife Engine 20.0.
Эксплуатационная документация — по-русски; код, схемы, статусы, команды — по-английски.

## Источники истины (порядок разрешения конфликтов)

1. manifest и файлы конкретного сайта (`sites/<site_id>/`)
2. решения проекта (`knowledge/DECISIONS.md`, `adr/`)
3. замороженная официальная документация (`knowledge/`, freeze — `KNOWLEDGE_FREEZE.yaml`)
4. код и автотесты фабрики
5. сторонние паттерны — необязательная идея, не основание

Конфликт не разрешается молча: запиши его, влияние и безопасное решение в `knowledge/DECISIONS.md`.
Production блокируется, только если конфликт затрагивает лицензию, права на контент,
безопасность, данные, домен, необратимую операцию или результат публикации.

## Режим работы

Фабрика работает в CLOSED_WORLD после `knowledge/KNOWLEDGE_FREEZE.yaml`. Запрещено:
искать контент в интернете, скрапить сайты, придумывать названия, тексты, метаданные,
ID, домены, ключи, изображения, контакты и настройки интеграций, расширять список
SSH-хостов/DNS-зон/доменов по своей инициативе. **Пустое поле — не разрешение
подставить значение по умолчанию, а `BLOCKED_INPUT`.**

## Жёсткие запреты (продублированы hook'ом и deny-правилами)

- Никакого произвольного `ssh`/`scp`/`rsync` в цели. Только `python3 -m factory deploy`.
- Никаких `rm -rf` по широким путям, `mkfs`, `dd` на устройства, `DROP DATABASE`,
  `git push --force`, `git reset --hard`, `git clean -fdx`, неконтролируемого `sudo`,
  изменения firewall и DNS вне manifest.
- Секреты только через `secret_ref` (Яндекс — файл вне репозитория, systemd LoadCredential).
  Значение не попадает в git, лог, отчёт, скриншот, fixture и prompt; `.env` не читается.
- Лицензионный архив DLE не коммитится. Сторонние/nulled-сборки не скачиваются.
- `bypassPermissions` не используется.

## Профиль UNATTENDED_SAFE

Правка файлов репозитория, сборка, тесты, линтеры, зависимости и git в ветке `claude/*`
идут без подтверждений: решение выдают PreToolUse-хуки поверх `seo_operator/unattended.py`.
Профиль умеет только разрешать; запреты остаются в `guard_rules` и `guardrails`.
Два исхода (`allow`/`deny`) и стоп-сигналы — `docs/UNATTENDED_SAFE.md`, матрица — `tests/unit/test_permission_matrix.py`.

## Команды

```bash
python3 -m factory validate  --site <site_id>          # схема + семантика пакета
python3 -m factory plan      --site <site_id>          # план без единой мутации
python3 -m factory build     --site <site_id>          # детерминированная сборка
python3 -m factory deploy    --site <site_id> --environment staging|production
python3 -m factory verify    --site <site_id>          # QA + SEO + security gates
python3 -m factory rollback  --site <site_id> --environment <env>
python3 -m factory status | resume | report | queue | analytics …   # analytics пишет только с --confirm-writes
python3 -m factory seo-plan | seo-lint | seo-crawl | seo-render | seo-report --site <site_id>
bash tests/run-all.sh                                  # полный прогон с чистого состояния
```

## Архитектурная карта

- `factory/` — controller, state machine, locks, retry, redaction, audit, SEO, цели, `analytics/`
- `schemas/` — `site-package.schema.json` (единственный вход), `job-result.schema.json`
- `knowledge/` — замороженная база знаний; менять только через skill `/research-freeze`
- `inventory/` — разрешённые SSH-хосты, DNS-зоны, лицензии, дистрибутивы, targets
- `blueprints/dle20/` — воспроизводимый blueprint (без лицензионного архива)
- `themes/`, `plugins/` — одобренные оригинальные шаблоны и расширения
- `sites/`, `queue/` — пакеты сайтов и очередь заданий
- `automation/ansible/` — декларативный SSH deployment слой
- `tests/`, `docs/`, `artifacts/`, `adr/`

## Конвейер и статусы

`RECEIVED → VALIDATING → READY → BUILDING → BUILT → STAGING_DEPLOY → STAGING_QA →
AUTHORIZATION_CHECK → PRODUCTION_DEPLOY → PRODUCTION_SMOKE → MONITORING → DONE`

Ошибки — только точными статусами: `BLOCKED_INPUT | BLOCKED_LICENSE | BLOCKED_RIGHTS |
BLOCKED_SECRET | BLOCKED_ACCESS | BLOCKED_AUTHORIZATION | BLOCKED_SEO |
BLOCKED_ANALYTICS_ACCESS | QA_FAILED | DEPLOY_FAILED | ROLLED_BACK | QUARANTINED`.

Успешный staging **не** является разрешением на production. Production требует
`production_authorized: true` в manifest и подходящей лицензии DLE.

## Definition of Done

Нельзя ставить `DONE`, если: провален критический тест; не подтверждена лицензия DLE;
не подтверждены права/происхождение контента; в production попали test/demo данные;
нет бэкапа или не проверен rollback; canonical/TLS/домен указывают не на тот сайт;
обнаружена cross-site утечка; production не авторизован в manifest; отчёт утверждает
проверку, которая фактически не запускалась.

Отчёт содержит команду, фактический exit code и путь к артефакту. Формулировки
«проверено» без запуска — ошибка отчёта, а не стилистика.

## Детальные правила

`.claude/rules/` (подгружаются по путям): `dle-php.md`, `frontend.md`, `content.md`,
`security.md`, `tests.md`, `infrastructure.md`, `deployment.md`, `seo.md`; аналитика — `docs/YANDEX_ANALYTICS.md`.
Повторяемые процессы — skills: `/research-freeze`, `/site-intake`, `/site-build`,
`/site-qa`, `/site-deploy`, `/site-rollback`, `/site-update`, `/incident-report`.

---

# Слой SEO-оператора

Ниже — правила и описание SEO-оператора, перенесённого из ветки
`claude/seo-operator`. Они дополняют правила фабрики выше и не отменяют их:
при расхождении действует фабрика.

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
