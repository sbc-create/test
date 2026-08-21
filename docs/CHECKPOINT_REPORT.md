# CHECKPOINT REPORT

Дата: 2026-08-21. Ветка: `claude/dle-sites-factory-z8cbxf`, коммит `667bb02`.
Файлов в репозитории: 206. Knowledge freeze: `2026-08-21.3`.

## Полный прогон (`bash tests/run-all.sh`)

pass=18, fail=0, skipped=3 — отчёт `artifacts/qa/run-all.json`.

| Проверка | Статус | Exit | Примечание |
|---|---|---|---|
| `knowledge-freeze` | PASS | 0 | 0s |
| `claude-config` | PASS | 0 | 0s |
| `static-python` | PASS | 0 | 0s |
| `static-php` | PASS | 0 | 0s |
| `static-js` | PASS | 0 | 1s |
| `static-yaml` | PASS | 0 | 0s |
| `unit-tests` | PASS | 0 | 5s |
| `validate-pilot` | PASS | 0 | 0s |
| `plan-no-mutations` | PASS | 0 | 0s |
| `build-pilot` | PASS | 0 | 1s |
| `integration-fast` | PASS | 0 | 1s |
| `integration-slow` | PASS | 0 | 10s |
| `seo-lint` | PASS | 0 | 1s |
| `blueprint-profile-gate` | PASS | 2 | ожидаемый BLOCKED_INPUT |
| `deploy-pilot` | PASS | 0 | 94s |
| `seo-crawl` | PASS | 0 | 0s |
| `browser-audit` | PASS | 0 | 0s |
| `e2e-playwright` | PASS | 0 | 15s |
| `cross-browser` | SKIPPED | - | в образе только Chromium: firefox и webkit в /opt/pw-browsers отсутствуют |
| `ansible-syntax` | SKIPPED | - | ansible-playbook не установлен на управляющем хосте |
| `nginx-config-test` | SKIPPED | - | nginx не установлен на управляющем хосте |

## Пилот

Задание `pilot-local-create-20260821T233602Z-f25b75` → **DONE**, приёмка полная: True.
Сборка `4254dd6e2f89968b`, релиз `4254dd6e2f89968b`, точка отката `717c6a3a2e819907`.
Бэкап снят, восстановление подтверждено сравнением содержимого: True.

| Ворота | Результат | Exit | Артефакт |
|---|---|---|---|
| `backup-restore` | PASS | 0 | `var/restore-probe/pilot-local-4254dd6e2f89968b` |
| `seo-lint` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233602Z-f25b75/seo-lint.json` |
| `seo-crawl` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233602Z-f25b75/seo-crawl.json` |
| `seo-render` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233602Z-f25b75/seo-render.json` |
| `security-smoke` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233602Z-f25b75/security-smoke.json` |
| `acceptance-routes` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233602Z-f25b75/acceptance-routes.json` |
| `major-findings-budget` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233602Z-f25b75/major-findings-budget.json` |
| `performance-budget` | PASS | 0 | `artifacts/qa/pilot-local/pilot-local-create-20260821T233602Z-f25b75/performance-budget.json` |

SEO-сводка: {"pages_total": 48, "indexable": 45, "noindex": 3, "in_sitemap": 45, "duplicate_titles": 0, "duplicate_descriptions": 0, "redirect_chains": 0, "orphan_pages": 0, "soft_404": 0, "broken_links": 0, "jsonld_errors": 0}

## Что осознанно не сделано

- **DLE не устанавливается**: не переданы лицензионный дистрибутив и профиль путей;
  угадывать структуру каталогов запрещено (§3.8). Гейт: `BLOCKED_INPUT`.
- **Production недоступен**: нет ни одного SSH-хоста, DNS-зоны и лицензии.
- **Кросс-браузерный дым**: в образе только Chromium; firefox/webkit помечены `SKIPPED`.
- **Ansible и nginx** не установлены на управляющем хосте — соответствующие шаги `SKIPPED`.
- **CDN Video Hub**: только extension point, интеграции нет.

Доказательства прогона — `artifacts/evidence/` (обновляется `tests/tools/collect_evidence.py`).

Полный список недостающих входных данных — `docs/INPUT_REQUEST.md`.
