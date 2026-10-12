# food-baking — «Тесто и десерты», вариант B `oven-bench`

Вариант B: главная по температуре духовки, каталог — таблица сравнения, рецепт — рабочий лист с пекарским процентом,
отметками и таймерами в шагах. Порт 8864, ключи `fbb.*`. Вариант A — ветка `claude/template-food-baking`.

Второй сайт сети (PRACTICAL-NETWORK-NIGHT-CONTINUE-02). Отдельная ветка
`claude/template-food-baking`, worktree `/home/claude/wt-template-food-baking`,
база — `origin/main` `a7f7cb6` (не ветка food-daily). Весь сайт —
`templates/food-baking/`; код написан заново, общих файлов с food-daily нет.

## Что это

Книга рецептов выпечки: оглавление вместо сетки карточек, рецепт — разворот
(слева духовка/форма/таймеры и продукты на весах, справа ход работы с
номерами на полях), виды теста, разборы ошибок по шагам.

| тип страницы | адрес |
| --- | --- |
| главная (оглавление глав) | `/` |
| каталог / оглавление | `/recepty/`, `/recepty/page/N/`, фильтры `?testo=&duhovka=` (noindex) |
| рецепт выпечки | `/recept/<slug>/` |
| вид теста / техника | `/testo/`, `/testo/<вид>/` (≥2 рецептов) |
| разбор ошибок | `/oshibki/<вид>/` |
| тег | `/teg/<тег>/` (страница ≥2, индекс ≥3) |
| поиск | `/poisk/?q=` (noindex) |
| о книге, 404, редактор (Basic Auth, только чтение) | `/o-proekte/`, любой неизвестный, `/redaktor/` |

## Команды (из корня worktree)

```bash
bash templates/food-baking/bin/food-baking start | stop | status | restart   # только этот preview, 127.0.0.1:8864
bash templates/food-baking/bin/food-baking test                              # тесты шаблона
bash templates/food-baking/bin/food-baking import --per-group 3              # факты с eda.rambler.ru (повтор не скачивает известное)
bash templates/food-baking/bin/food-baking import --reextract                # пересчёт фактов о духовке без сети
bash templates/food-baking/bin/food-baking drafts validate | build           # проверка черновиков, снимок data/content.json
bash templates/food-baking/bin/food-baking build --commit HEAD               # артефакт var/food-baking/build/<sha>/
PYTHONPATH=templates/food-baking python3 -m bakebook.qa --shots <dir> --out <json>   # браузер + axe (axe: templates/food-baking/qa, свой lockfile)
```

Откат текста: вернуть файл черновика `data/drafts/<record>.json` к прежнему
коммиту и `drafts build` — версия увеличится, запись в `data/history.jsonl`.

## Документы

`docs/AUDIT.md` (референсы, структура, улучшения), `docs/SEO-MATRIX.md`,
`OWNERSHIP.yaml`, `DECISIONS.md`, `REPORT.md`.
