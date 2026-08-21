# BOOTSTRAP_PLAN — фабрика сайтов на DLE

Дата: 2026-08-21. Ветка: `claude/dle-sites-factory-z8cbxf`.
Исходное состояние git: пустой репозиторий `sbc-create/test` (0 коммитов, 0 файлов).
Пользовательских изменений, которые можно перезаписать, нет — зафиксировано командой
`git status --porcelain` и `find . -not -path './.git/*'` (0 записей).

## Задачи и команды доказательства

| # | Задача | Команда доказательства | Ожидаемый результат |
|---|--------|------------------------|---------------------|
| 1 | Инвентаризация окружения (read-only) | `python3 -m factory env-report` | `artifacts/env-report.json` со списком найденного тулинга |
| 2 | Knowledge pack и freeze | `python3 -m factory knowledge verify` | все файлы из `KNOWLEDGE_FREEZE.yaml` совпадают по SHA-256 |
| 3 | Конфигурация Claude Code | `python3 -m factory selfcheck claude-config` | CLAUDE.md ≤ 200 строк, settings.json валиден, hooks исполняемы |
| 4 | Схемы site package / job result | `pytest tests/unit/test_schemas.py -q` | positive и negative fixtures ведут себя как заявлено |
| 5 | Controller, state machine, lock, retry, redaction | `pytest tests/unit -q` | все unit-тесты зелёные |
| 6 | Валидация пилотного пакета | `python3 -m factory validate --site pilot-local` | статус `READY` или точный `BLOCKED_*` |
| 7 | Plan без мутаций | `python3 -m factory plan --site pilot-local` | план шагов, `mutations: 0` |
| 8 | Сборка | `python3 -m factory build --site pilot-local` | каталог сборки + `build-manifest.json` |
| 9 | Staging deploy на disposable local target | `python3 -m factory deploy --site pilot-local --environment staging` | сайт поднят на `127.0.0.1`, health OK |
| 10 | SEO-контур | `python3 -m factory seo-lint/seo-crawl/seo-report --site pilot-local` | отчёты в `artifacts/seo/` без критических ошибок |
| 11 | QA (E2E, a11y, visual, security, perf-budget) | `python3 -m factory verify --site pilot-local` | `artifacts/qa/verify-*.json`, все обязательные проверки pass |
| 12 | Backup + restore | `pytest tests/integration/test_backup_restore.py -q` | восстановление подтверждено сравнением контента |
| 13 | Идемпотентность | `python3 -m factory deploy … && python3 -m factory deploy …` | второй запуск: `changed: 0`, дублей нет |
| 14 | Rollback | `python3 -m factory rollback --site pilot-local --environment staging` | `current` указывает на предыдущий release, health OK |
| 15 | Запрет production без авторизации | `pytest tests/unit/test_authorization.py -q` | `production_authorized=false` → `BLOCKED_AUTHORIZATION`, 0 мутаций |
| 16 | Полный прогон с чистого состояния | `bash tests/run-all.sh` | сводная таблица, exit code 0 |
| 17 | Независимый review | subagents architecture/security/QA в свежем контексте | замечания зафиксированы и исправлены |
| 18 | Пакет недостающих данных | `python3 -m factory input-request` | `docs/INPUT_REQUEST.md` + `artifacts/input-request.json` |

## Границы этого задания

- Production не трогается: ни один site package с `environment: production` не передан,
  `production_authorized` нигде не выставлен в `true`.
- Реальный staging-хост не передан → пилот выполняется на disposable local target
  (PHP built-in server на 127.0.0.1), см. `docs/OPERATIONS.md`.
- CDN Video Hub не интегрируется: создана только версионируемая extension point.
