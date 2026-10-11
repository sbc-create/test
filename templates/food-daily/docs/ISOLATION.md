# Изоляция food-daily

Машиночитаемо — `OWNERSHIP.yaml`. Проверки — `tests/test_isolation.py` и
команды ниже. Фактические результаты прогона — `docs/verification/`.

## Окружение (подтверждено 11.10.2026)

| что | значение | как получено |
| --- | --- | --- |
| хост | `claude-control-01` | прочитано из `/proc/sys/kernel/hostname` 11.10.2026 (команда `hostname` запрещена профилем, файл ядра — нет) |
| пользователь | `claude` | путь `/home/claude`, владелец файлов |
| worktree | `/home/claude/wt-template-food-daily` | `git worktree list` |
| ветка | `claude/template-food-daily` | `git branch --show-current` |
| base | `a7f7cb6` = `origin/main` | `git merge-base HEAD origin/main` |
| origin | `https://github.com/sbc-create/test.git` | `git remote -v` |
| `claude/practical-network-01` | не существует ни локально, ни в списке веток | `git branch -a --list '*practical-network*'` — пусто; переносить нечего |

## Что изолировано и чем

| ресурс | food-daily | доказательство |
| --- | --- | --- |
| код, шаблоны, CSS, JS, SVG | только `templates/food-daily/` | `test_no_references_to_other_templates`, `test_static_assets_are_own_files`, нет симлинков (`test_no_symlinks_inside_template`) |
| сборка | `fooddaily.build` берёт `git archive <commit> templates/food-daily` — соседние каталоги физически не попадают | `var/food-daily/build/<commit>/manifest.json` |
| БД | собственный SQLite, `meta.site_id=food-daily`; чужая БД отвергается | `test_store_refuses_foreign_site_db` (отрицательный тест tenant `games-rpg`) |
| снимок контента | `site_id` сверяется при загрузке | `test_foreign_snapshot_refused` (tenant `home-practical`) |
| медиа | `var/food-daily/media` (пусто) | `config/site.yaml` |
| очередь заданий | таблица `jobs` своей БД + `var/food-daily/qwen/` | |
| кэш HTTP | `var/food-daily/cache` | |
| поисковый индекс | в памяти своего процесса | |
| порт | `127.0.0.1:8847`, отказ при bind не на петлю | `fooddaily/server.py::main` |
| процесс | свой pid-файл; `bin/food-daily stop` проверяет, что pid принадлежит `fooddaily.server` | `bin/food-daily::alive` |
| секрет редактора | вне репозитория, 0600 | `~/.config/food-daily-preview/` |
| сеть | исходящие — только https GET к хостам allowlist; петля/частные адреса запрещены | `tests/test_pipeline.py::test_client_refuses*` |
| production-БД | не подключается: production-режим не включён, внешних БД нет | `config/site.yaml` |

Отдельный Compose-проект, сеть Docker и роль СУБД не создавались: preview —
один процесс Python на петле с файловой БД. Это проще и не трогает общий
Docker-демон; при выкладке на удалённую цель понадобится отдельный
compose-проект — в задание следующего этапа.

## Граница diff

```
git diff --stat a7f7cb6 -- . ':!templates/food-daily'
 inventory/network-allowlist.yaml    | 77 +++++  (только добавление записей)
 tests/unit/test_permission_matrix.py |  ожидаемый состав allowlist + 14 хостов из ТЗ
```

## Находки, которые не исправлял

* `knowledge/DECISIONS.md` **не изменён**: первая попытка добавить строку D128
  нарушила контрольную сумму `KNOWLEDGE_FREEZE`, и пайплайн фабрики стал
  блокировать любые задания (`tests/unit/test_authorization.py::
  test_staging_success_is_not_production_permission` → BLOCKED_INPUT). Правка
  отменена; решение записано в `templates/food-daily/DECISIONS.md` (FD-01, FD-13),
  внесение D128 в центральный журнал — через `/research-freeze` (handoff).

* `node_modules` в корне worktree — **висячая ссылка** на
  `/srv/site-factory/repo/node_modules` (создана при подготовке worktree,
  игнорируется git). food-daily её не использует (сборка без Node), поэтому
  не трогал; QA-браузер — Python Playwright из пользовательского окружения.
  Рекомендация: удалить ссылку при следующей подготовке worktree шаблонов.
* Корневой `tests/` фабрики шаблон не собирает (`pytest.ini: testpaths = tests`);
  тесты шаблона запускаются `bin/food-daily test`.
