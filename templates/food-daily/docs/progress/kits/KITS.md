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
| food-appliances | `food-appliances-e2ae237` | `claude/template-food-appliances-b` `e2ae237` | 97 КБ | 24 passed, 1 skipped in 1.11s | 26 / 3 / 0 | — |
| food-baking | `food-baking-3202315` | `claude/template-food-baking-b` `3202315` | 110 КБ | 34 passed, 1 skipped in 1.98s | 26 / 3 / 0 | — |
| food-daily | `food-daily-4121565` | `claude/template-food-daily-c` `4121565` | 16889 КБ | 141 passed in 12.33s | 53 / 3 / 0 | база: 24 материалов, 50 версий |
| food-weekly | `food-weekly-1d7cf83` | `claude/template-food-weekly-c` `1d7cf83` | 63 КБ | 30 passed in 1.45s | 35 / 3 / 0 | — |
| games-rpg | `games-rpg-d950fc7` | `claude/template-games-rpg-c` `d950fc7` | 89 КБ | 22 passed in 1.25s | 36 / 4 / 0 | — |
| games-story | `games-story-79d2753` | `claude/template-games-story-c` `79d2753` | 77 КБ | 21 passed in 1.03s | 26 / 4 / 0 | — |
| games-survival | `games-survival-2debb36` | `claude/template-games-survival-c` `2debb36` | 96 КБ | 28 passed in 1.56s | 37 / 4 / 0 | — |
| garden-season | `garden-season-97f7bd6` | `claude/template-garden-season-c` `97f7bd6` | 133 КБ | 21 passed in 2.50s | 60 / 4 / 0 | — |
| home-practical | `home-practical-e3ad4da` | `claude/template-home-practical-c` `e3ad4da` | 103 КБ | 23 passed in 1.37s | 51 / 10 / 0 | — |
| plants-home | `plants-home-85a668a` | `claude/template-plants-home-c` `85a668a` | 120 КБ | 21 passed in 1.33s | 43 / 8 / 0 | — |

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
