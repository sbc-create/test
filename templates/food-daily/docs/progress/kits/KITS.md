# Комплекты переноса 10 основных сайтов (13.10.2026)

**Расположение:** `/home/claude/wt-template-food-daily/var/kits/<сайт>-<коммит>/` на машине сборки (каталог `var/`
в `.gitignore` — закрытая часть в git не попадает). Пересобрать любой комплект из его ветки:
`bash templates/<сайт>/bin/<сайт> kit build --out <каталог>` (только из закоммиченного состояния).

Состав каждого комплекта: `code.tar.gz` (templates/<сайт> без data/ и скриншотов, inventory/, .gitignore — из коммита),
`content.tar.gz` (публичный контент data/ из git), `INSTALL.md` (точные команды: распаковка, зависимости, запуск,
восстановление данных, проверка), `MANIFEST.json`, `SHA256SUMS`; у food-daily ещё `private/` — копия редакционной базы
(SQLite backup, права 0600) и опись версий `versions.json`. Не входят: закрытые снимки источников, секреты,
node_modules, скриншоты (в git). Миграций нет: у 9 сайтов нет базы, у food-daily схема хранилища 1 (таблицы создаёт Store).

| сайт | комплект | ветка и коммит | размер | тесты в изолированном каталоге | URL / ресурсы / ошибки | закрытая часть |
| --- | --- | --- | --- | --- | --- | --- |
| food-appliances | `food-appliances-6a624a8` | `claude/template-food-appliances-b` `6a624a8` | 96 КБ | 24 passed, 1 skipped in 1.52s | 26 / 3 / 0 | — |
| food-baking | `food-baking-e26066a` | `claude/template-food-baking-b` `e26066a` | 110 КБ | 34 passed, 1 skipped in 1.43s | 26 / 3 / 0 | — |
| food-daily | `food-daily-6663171` | `claude/template-food-daily-c` `6663171` | 16889 КБ | 141 passed in 12.43s | 53 / 3 / 0 | база: 24 материалов, 50 версий |
| food-weekly | `food-weekly-118eac6` | `claude/template-food-weekly-c` `118eac6` | 63 КБ | 30 passed in 1.12s | 35 / 3 / 0 | — |
| games-rpg | `games-rpg-32e2c91` | `claude/template-games-rpg-c` `32e2c91` | 89 КБ | 22 passed in 1.72s | 36 / 4 / 0 | — |
| games-story | `games-story-ac0a5ca` | `claude/template-games-story-c` `ac0a5ca` | 77 КБ | 21 passed in 4.18s | 26 / 4 / 0 | — |
| games-survival | `games-survival-5ff6362` | `claude/template-games-survival-c` `5ff6362` | 95 КБ | 28 passed in 1.32s | 37 / 4 / 0 | — |
| garden-season | `garden-season-8e5addd` | `claude/template-garden-season-c` `8e5addd` | 132 КБ | 21 passed in 1.26s | 60 / 4 / 0 | — |
| home-practical | `home-practical-45cd003` | `claude/template-home-practical-c` `45cd003` | 103 КБ | 23 passed in 1.47s | 51 / 10 / 0 | — |
| plants-home | `plants-home-8d7cfee` | `claude/template-plants-home-c` `8d7cfee` | 120 КБ | 21 passed in 1.27s | 43 / 8 / 0 | — |

## Как проверено (фактически выполнено, scratchpad `kit_check.py`, итог — `kit-check.json`)

Для каждого комплекта в пустом каталоге без git: `sha256sum -c SHA256SUMS` — exit 0; распаковка `code.tar.gz` и
`content.tar.gz`; `bash bin/<сайт> test`; запуск `python3 -m <пакет>.server --port 8901…8910` — `/healthz` за 0,25 с;
главная 200 со своим `site-factory-variant-id`; обход всех URL sitemap и всех `/static/` ресурсов — 0 ошибок; остановка.
Пропуски тестов: food-baking и food-appliances — по одному (полная сверка текста черновиков с закрытыми снимками
источников; в комплект они не входят) — **не выполнялись**.

**food-daily — восстановление редакционной базы с сохранением версий:**
`python3 -m fooddaily.editorial clone-db --from <комплект>/private/food-daily.sqlite3` — exit 0, сверено со снимком
22 из 22; `python3 -m fooddaily.kit verify-db … --versions versions.json` — {"ok": true, "content": 24, "versions": 50, "mismatch": []};
повторное восстановление поверх — отказ (exit 2); правка после восстановления (`editorial revise`) создала версию
3, прежние версии материала не изменились
(True), расхождение с описью — только у этого материала
(True).

Браузерная приёмка из комплекта не повторялась: код и контент совпадают с коммитами, на которых она пройдена
(чистые копии и рабочие превью); изменились только упаковка и модуль `kit`.

Найдено и исправлено при проверке: в первой сборке не было корневого `.gitignore` (тест изоляции food-daily это
поймал — на новом месте `var/` с закрытыми данными могла попасть в git); копия базы оставалась в режиме WAL
(файлы -wal/-shm могли менять контрольную сумму) — теперь один файл.
