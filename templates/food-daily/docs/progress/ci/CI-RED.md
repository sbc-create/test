# Красный CI на PR вариантов: разбор (13.10.2026)

## Итог

Все 30 PR (#95–#124) красные по **одной** причине: стадия `Lint (ruff)` в `scripts/verify.sh`
падает на 20 ошибках в **shared core** — 2 файла `factory/contracts/` и 13 файлов `tests/unit/`.
Эти файлы во всех 30 ветках байт в байт совпадают с `origin/main` (a7f7cb6), а сам `main` красный
с 2026-09-04 (последние прогоны CI на main — failure). Шаблоны сайтов ошибок lint не дают.

Исправить в ветках вариантов нельзя: задание запрещает править shared core. Ниже — точное
воспроизведение и готовый патч для отдельного PR в main (решение владельца).

## Воспроизведение (фактически запущено)

| что | команда | exit | результат |
| --- | --- | --- | --- |
| CI PR #95, run 38333063165 | `gh run view 38333063165 --log-failed` | — | 7 стадий PASS, `FAIL: Lint (ruff)`; pytest 2953 passed, 18 skipped; шаг «Confirm committed evidence» пропущен |
| ветка claude/template-food-daily, локально | `./scripts/verify.sh` | 1 | 7 PASS, 1 FAIL — Lint (ruff) |
| то же | `ruff check . --output-format concise` (ruff 0.6.9) | 1 | 20 ошибок, список ниже |
| снимок `origin/main` (git archive, без .git) | `ruff check .` | 1 | те же 20 ошибок |
| снимок main | `./scripts/verify.sh` | 2 | Lint FAIL; pytest FAIL — 3 теста вызывают `git ls-files`, а у снимка нет `.git` (артефакт снимка) |
| снимок main + `shared-lint-fix.patch` | `ruff check . && ruff format --check .` | 0 | чисто |
| снимок main + патч | `./scripts/verify.sh` | 1 | Lint PASS; pytest — те же 3 теста без `.git`, 2963 passed |

В настоящем checkout (локальная ветка и CI) эти 3 теста проходят: см. pytest в CI выше.

```
factory/contracts/mock_server.py:16:1: I001 [*] Import block is un-sorted or un-formatted
factory/contracts/provider_conformance.py:38:1: UP035 [*] Import from `collections.abc` instead: `Callable`, `Iterable`
tests/unit/test_backup_retention_prunes_orphan_archives.py:36:8: F401 [*] `pytest` imported but unused
tests/unit/test_backup_space_precheck.py:24:8: F401 [*] `pytest` imported but unused
tests/unit/test_catalog_content_check.py:19:8: F401 [*] `pytest` imported but unused
tests/unit/test_health_log_ownership.py:29:8: F401 [*] `pytest` imported but unused
tests/unit/test_install_units_selective.py:19:8: F401 [*] `pytest` imported but unused
tests/unit/test_provider_conformance.py:12:8: F401 [*] `pytest` imported but unused
tests/unit/test_schema_compat.py:15:8: F401 [*] `pytest` imported but unused
tests/unit/test_site_backup_retention.py:24:8: F401 [*] `pytest` imported but unused
tests/unit/test_site_backup_retention.py:110:20: E741 Ambiguous variable name: `l`
tests/unit/test_site_backup_schedule.py:21:8: F401 [*] `pytest` imported but unused
tests/unit/test_site_backup_schedule.py:46:23: E741 Ambiguous variable name: `l`
tests/unit/test_template_boundary.py:11:8: F401 [*] `pytest` imported but unused
tests/unit/test_unit_provenance.py:23:8: F401 [*] `sys` imported but unused
tests/unit/test_unit_provenance.py:26:8: F401 [*] `pytest` imported but unused
tests/unit/test_unit_provenance.py:132:9: UP031 Use format specifiers instead of percent format
tests/unit/test_validate_registries_derived.py:23:8: F401 [*] `pytest` imported but unused
tests/unit/test_yummy_content_from_image.py:22:8: F401 [*] `sys` imported but unused
tests/unit/test_yummy_content_from_image.py:91:25: E741 Ambiguous variable name: `l`
Found 20 errors.
[*] 16 fixable with the `--fix` option (1 hidden fix can be enabled with the `--unsafe-fixes` option).
```

## Причина

Ошибки появились в main вместе с тестами и контрактами (импорт `pytest` без использования,
`typing.Callable` вместо `collections.abc`, порядок импортов, имя `l`, `%`-форматирование);
CI main с тех пор красный, поэтому каждая ветка от main наследует красный lint.

## Что нужно изменить (патч `ci/shared-lint-fix.patch`, 15 файлов)

1. `ruff check --fix` — 16 автоисправлений: удалить неиспользуемые `import pytest` (11 файлов) и
   `import sys` (2), отсортировать импорты в `factory/contracts/mock_server.py`, импортировать
   `Callable`, `Iterable` из `collections.abc` в `factory/contracts/provider_conformance.py`.
2. Вручную (4): переименовать `l` → `ln` в генераторах (`test_site_backup_retention.py`,
   `test_site_backup_schedule.py`, `test_yummy_content_from_image.py`); в `test_unit_provenance.py`
   заменить `"…%s…" % (unit, exec_start)` на f-строки с тем же текстом скрипта.

Поведение тестов не меняется: правки только в импортах, именах переменных и способе форматирования строки.
Схемы и тесты не ослабляются, ни один тест не удаляется и не пропускается.

Применение — отдельный PR в main владельцем (или по его прямому разрешению):
`git apply templates/food-daily/docs/progress/ci/shared-lint-fix.patch`, затем `./scripts/verify.sh` и
`./scripts/record-evidence.sh --check` (закоммиченная запись `docs/verification/latest-run.md` — «все 8 PASS»,
после патча свежий прогон должен с ней совпасть). После слияния в main ветки вариантов станут зелёными
после обновления от main.

## Прочее в логах CI (не ошибки)

- Предупреждение: actions на Node.js 20 принудительно запускаются на Node 24 (`actions/checkout@v4`,
  `actions/setup-python@v5`) — стоит обновить версии actions в `.github/workflows/ci.yml` (shared).
- `ubuntu-latest` переедет на Ubuntu 26 с 19.10.2026.

## Отличие веток от main в shared-каталогах

Во всех 30 ветках отличается только `tests/unit/test_permission_matrix.py` — запись разрешённых хостов
задания TEMPLATE-FOOD-DAILY-01 (коммит 361ae67, 11.10). Патч этот файл не затрагивает.

## Решение владельца и итог (13.10.2026)

Владелец разрешил отдельный черновой PR с минимальным патчем shared core. Перед созданием найден
**уже открытый PR [#71](https://github.com/sbc-create/test/pull/71)** (`claude/lint-green-trunk`, 98f373d, от 2026-09-15):
те же 15 файлов, та же суть исправлений (расхождения с `shared-lint-fix.patch` — только в контексте diff).

| что | команда | exit | результат |
| --- | --- | --- | --- |
| снимок 98f373d (git archive, без symlink) | `ruff check .` (ruff 0.6.9) | 0 | All checks passed |
| CI PR #71 | `gh pr view 71 --json statusCheckRollup` | — | Verify (schemas, lint, tests) — SUCCESS, MERGEABLE |

Дубликат PR не создан, чтобы не тратить CI и не плодить конкурирующие правки shared core.
Остаётся одно действие владельца: слить #71 в main; после этого ветки вариантов станут зелёными
после обновления от main (shared-файлы в них совпадают с main a7f7cb6).

## Повторная проверка PR #71 (13.10.2026, вечер)

| что | команда | результат |
| --- | --- | --- |
| состояние | `gh pr view 71 --json state,isDraft,mergeable,mergeStateStatus,baseRefName,headRefOid,statusCheckRollup` | OPEN, не черновик, MERGEABLE, CLEAN; head 98f373d; CI «Verify (schemas, lint, tests)» — SUCCESS (2026-09-15) |
| свежесть | `git merge-base --is-ancestor origin/main origin/claude/lint-green-trunk` | exit 0 — main (a7f7cb6) не уходил вперёд, обновлять ветку PR не нужно |
| объём | `git diff --stat origin/main origin/claude/lint-green-trunk` | 15 файлов, +16/−34 — те же файлы, что в этом разборе |
| суть правок | просмотр diff | только lint: сортировка импортов, `collections.abc`, удалены неиспользуемые `import pytest`/`import sys`, `l` → `line`/`raw`, `%` → f-string; поведение тестов не меняется |
| ruff на голове PR | `ruff check .` (0.6.9, снимок 98f373d) | exit 0 |

Вывод: #71 — нужное исправление, дубликат не нужен. Слияние в main не выполнялось (ждёт решения владельца).

## Итог (13.10.2026, вечер)

PR #71 слит владельцем (304c3d6), CI main — success. `origin/main` влит в 11 рабочих веток.
Файл `ci/shared-lint-fix.patch` удалён: тест гигиены репозитория (`tests/unit/test_repo_hygiene.py::test_no_dle_core_patches`)
запрещает файлы `*.patch`; пока стадия lint падала, CI до этой проверки не доходил. Моя ошибка: патч был положен в
ветку отчётов утром, и после влития main CI этой ветки (прогон 38469688352) упал именно на нём. Содержание патча
совпадало с PR #71 и теперь в main.

