# CHECKPOINT REPORT

Дата: 2026-08-21. Ветка: `claude/dle-sites-factory-z8cbxf`, коммит `e231c4e`.
Файлов в репозитории: 835. Knowledge freeze: `2026-08-21.3`.

## Полный прогон (`bash tests/run-all.sh`)

pass=18, fail=0, skipped=3 — отчёт `artifacts/qa/run-all.json`.

| Проверка | Команда | Статус | Exit | Примечание |
|---|---|---|---|---|
| `knowledge-freeze` | `python3 -m factory knowledge verify` | PASS | 0 | 0s |
| `claude-config` | `python3 -m factory selfcheck` | PASS | 0 | 0s |
| `static-python` | `python3 -m compileall -q factory tools .claude/hooks tests > /dev/null` | PASS | 0 | 0s |
| `static-php` | `find automation themes -name '*.php' -print0 | xargs -0 -r -n1 php -l ` | PASS | 0 | 0s |
| `static-js` | `for f in tools/*.js themes/*/assets/*.js tests/e2e/*.js playwright.con` | PASS | 0 | 1s |
| `static-yaml` | `python3 tests/tools/check_yaml.py` | PASS | 0 | 0s |
| `unit-tests` | `python3 -m pytest tests/unit tests/test_traceability.py -q -m 'not slo` | PASS | 0 | 5s |
| `validate-pilot` | `python3 -m factory validate --site pilot-local > /dev/null` | PASS | 0 | 0s |
| `plan-no-mutations` | `python3 -m factory plan --site pilot-local > /dev/null` | PASS | 0 | 0s |
| `build-pilot` | `python3 -m factory build --site pilot-local --force > /dev/null` | PASS | 0 | 1s |
| `integration-fast` | `python3 -m pytest tests/integration -q -m 'not slow'` | PASS | 0 | 1s |
| `integration-slow` | `python3 -m pytest tests/integration -q -m slow` | PASS | 0 | 10s |
| `seo-lint` | `python3 -m factory seo-lint --site pilot-local > /dev/null` | PASS | 0 | 1s |
| `blueprint-profile-gate` | `python3 -m factory blueprint check` | PASS | 2 | ожидаемый BLOCKED_INPUT |
| `deploy-pilot` | `python3 -m factory deploy --site pilot-local > /dev/null` | PASS | 0 | 94s |
| `seo-crawl` | `python3 -m factory seo-crawl --site pilot-local > /dev/null` | PASS | 0 | 0s |
| `browser-audit` | `python3 tests/tools/check_browser_audit.py` | PASS | 0 | 0s |
| `e2e-playwright` | `npx playwright test && test -s "artifacts/qa/pilot-local/playwright-re` | PASS | 0 | 15s |
| `cross-browser` | `-` | SKIPPED | - | в образе только Chromium: firefox и webkit в /opt/pw-browsers отсутствуют |
| `ansible-syntax` | `-` | SKIPPED | - | ansible-playbook не установлен на управляющем хосте |
| `nginx-config-test` | `-` | SKIPPED | - | nginx не установлен на управляющем хосте |

## Пилот

Задание `pilot-local-create-20260821T233153Z-cc68f7` → **DONE**, приёмка полная: True.
Сборка `4254dd6e2f89968b`, релиз `4254dd6e2f89968b`, точка отката `717c6a3a2e819907`.
Бэкап снят, восстановление подтверждено сравнением содержимого: True.

| Ворота | Результат | Exit | Артефакт |
|---|---|---|---|
| `backup-restore` | PASS | 0 | `var/restore-probe/pilot-local-4254dd6e2f89968b` |
| `seo-lint` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233153Z-cc68f7/seo-lint.json` |
| `seo-crawl` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233153Z-cc68f7/seo-crawl.json` |
| `seo-render` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233153Z-cc68f7/seo-render.json` |
| `security-smoke` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233153Z-cc68f7/security-smoke.json` |
| `acceptance-routes` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233153Z-cc68f7/acceptance-routes.json` |
| `major-findings-budget` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233153Z-cc68f7/major-findings-budget.json` |
| `performance-budget` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233153Z-cc68f7/performance-budget.json` |

SEO-сводка: {"pages_total": 48, "indexable": 45, "noindex": 3, "in_sitemap": 45, "duplicate_titles": 0, "duplicate_descriptions": 0, "redirect_chains": 0, "orphan_pages": 0, "soft_404": 0, "broken_links": 0, "jsonld_errors": 0}

## Что осознанно не сделано

- **DLE не устанавливается**: не переданы лицензионный дистрибутив и профиль путей;
  угадывать структуру каталогов запрещено (§3.8). Гейт: `BLOCKED_INPUT`.
- **Production недоступен**: нет ни одного SSH-хоста, DNS-зоны и лицензии.
- **Кросс-браузерный дым**: в образе только Chromium; firefox/webkit помечены `SKIPPED`.
- **Ansible и nginx** не установлены на управляющем хосте — соответствующие шаги `SKIPPED`.
- **CDN Video Hub**: только extension point, интеграции нет.

Полный список недостающих входных данных — `docs/INPUT_REQUEST.md`.
