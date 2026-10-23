# Handoff: CI-гейт репозитория (владелец — ядро/инфраструктура фабрики)

Состояние на 12.10.2026.

| что | факт | доказательство |
| --- | --- | --- |
| CI на `main` | **красный** с 2026-09-04: последние два прогона `failure` | `gh run list --branch main --workflow ci.yml` → 33863375488, 33838607091 |
| CI на PR #95 (первый прогон) | стадия `Lint (ruff)` — FAIL; тесты 2953 passed, 18 skipped | run 38183112209 |
| вклад food-daily в FAIL линта | был: SIM105, E501, F401 в `templates/food-daily` | тот же лог |
| исправлено в ветке | `ruff check` и `ruff format --check` по `templates/food-daily` и `tests/unit/test_permission_matrix.py` — 0 замечаний (свой `templates/food-daily/ruff.toml`, наследует корневой) | `var/food-daily/logs/ruff*.log` |
| остаётся | 20 замечаний ruff в `tests/unit/*` (test_unit_provenance, test_yummy_content_from_image, test_site_backup_*, test_template_boundary и др.), которых нет в diff ветки — они есть на `main` | `python3 -m ruff check . --output-format concise` |
| `test_job_result.py::test_real_pilot_results_are_schema_valid` | падает только локально в свежем worktree: нужны `artifacts/jobs/pilot-local/*.json` от прогона DLE-пилота; в CI набор тестов проходит | локальный лог `var/food-daily/logs/repo-unit-full.log`; CI run 38183112209 |

Решение: общие тесты и артефакты пилота не правлю и не подделываю (это не
область шаблона). Гейт CI для PR остаётся **FAIL**, пока владелец не починит
линт `tests/unit` на `main`. Merge и production этим не разрешаются; разработка
шаблонов продолжается.

Что нужно от владельца: `ruff check --fix tests/unit` + ручная правка
оставшихся замечаний в отдельной ветке ядра; после этого — пересборка
`docs/verification/latest-run.md` через `scripts/record-evidence.sh`.
