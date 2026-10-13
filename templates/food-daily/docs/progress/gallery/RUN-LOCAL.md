# Локальный запуск: 10 основных сайтов и галерея

Всё работает только на 127.0.0.1, превью закрыты от индексации (`noindex`, robots `Disallow: /`).
Production, домены и DNS здесь не участвуют: `origin.production` в `config/site.yaml` каждого сайта — `null`
(BLOCKED_INPUT, домен будет подключён отдельно).

## Что нужно

- Python 3.10+, пакеты `jinja2`, `pyyaml` (для приёмки ещё `playwright` и Chromium; axe-core лежит в `qa/node_modules` шаблона).
- Клон репозитория; каждый сайт — своя ветка и своя рабочая копия (`git worktree`).

## 1. Рабочие копии основных вариантов

Из корня клона (рядом появятся каталоги `wt-template-<сайт>-<буква>`):

```bash
git fetch origin
for s in food-daily:c food-baking:b food-weekly:c food-appliances:b home-practical:c \
         garden-season:c plants-home:c games-story:c games-rpg:c games-survival:c; do
  site=${s%:*}; v=${s#*:}
  git worktree add "../wt-template-$site-$v" "claude/template-$site-$v"
done
```

Если рабочая копия уже есть — `git -C ../wt-template-<сайт>-<буква> pull --ff-only`.

## 2. Запуск превью

У каждого сайта штатный скрипт `templates/<сайт>/bin/<сайт>`: у всех есть `start | stop | restart | status | test`,
остальные команды различаются — полный список выводит `bash bin/<сайт>` без аргументов.
Он запускает только своё превью на своём порту и пишет журнал в `var/<сайт>/logs/preview.log` своей копии.

```bash
for s in food-daily:c food-baking:b food-weekly:c food-appliances:b home-practical:c \
         garden-season:c plants-home:c games-story:c games-rpg:c games-survival:c; do
  site=${s%:*}; v=${s#*:}
  bash "../wt-template-$site-$v/templates/$site/bin/$site" start
done
```

| сайт | вариант | порт | редактор |
| --- | --- | --- | --- |
| food-daily | C party-list | 8876 | `/redaktor/`, учётка — `python3 -m fooddaily.editor_secret` (переменная `FOOD_DAILY_C_EDITOR_SECRET`) |
| food-baking | B oven-bench | 8864 | `/redaktor/` (только чтение), `python3 -m bakebook.editor_secret` (`FOOD_BAKING_B_EDITOR_SECRET`) |
| food-weekly | C own-week | 8873 | нет |
| food-appliances | B step-console | 8866 | нет |
| home-practical | C home-audit | 8867 | нет |
| garden-season | C my-plot | 8868 | нет |
| plants-home | C my-collection | 8869 | нет |
| games-story | C atlas | 8870 | нет |
| games-rpg | C index-compare | 8871 | нет |
| games-survival | C inventory-first | 8872 | нет |

Секрет редактора создаётся только вне репозитория (по умолчанию `~/.config/<сайт>-<буква>-preview/`), пароль — в файле 0600.

Проверка: `bash ../wt-template-<сайт>-<буква>/templates/<сайт>/bin/<сайт> status` (ответ `/healthz`).
Альтернативные варианты (A/B/C) запускаются так же из своих веток; их порты — в галерее.

## 3. Галерея

```bash
python3 -m http.server 8877 --bind 127.0.0.1 \
  --directory ../wt-template-food-daily/templates/food-daily/docs/progress/gallery
```

Открыть http://127.0.0.1:8877/. С другой машины — через SSH-туннель на 127.0.0.1 (порты 8877 и порты превью).
Страница статическая: открывается и как файл, но ссылки «Превью» работают только при запущенных превью.

Галерея собирается и проверяется инструментами вне шаблона (их sha256 — в `README.md`): живой опрос превью,
переходы из карточек и таблицы основных вариантов в Chromium, 320/390/768/1440 × светлая/тёмная тема, axe-core.
Последний результат — `click-result.json` (переходы) и `check-result.json` (ширины, темы, axe).

## 4. Чистая копия рядом с действующим превью (свободный порт)

Так проверяется, что сайт собирается и работает из одного git, без накопленных `var/` и `node_modules`.
Действующее превью не останавливается: чистая копия слушает другой порт (у сервера есть `--port`,
у приёмки — переменная `QA_BASE`; конфигурация не правится).

```bash
git worktree add --detach /tmp/clean/wt-template-<сайт>-<буква> claude/template-<сайт>-<буква>
cd /tmp/clean/wt-template-<сайт>-<буква>/templates/<сайт>
(cd qa && npm ci --no-audit --no-fund)          # axe-core 4.13.0 по package-lock.json
bash bin/<сайт> test
python3 -m <пакет>.server --port 89NN &          # та же команда, что в bin/<сайт> start, плюс --port
QA_BASE=http://127.0.0.1:89NN python3 -m <модуль приёмки> --shots /tmp/clean/shots --out /tmp/clean/qa.json
python3 qa/viewports.py 89NN <доп. адреса>
kill %1                                          # остановить сервер чистой копии
git worktree remove /tmp/clean/wt-template-<сайт>-<буква>   # когда копия больше не нужна
```

| сайт | пакет сервера | модуль приёмки | порт чистой копии |
| --- | --- | --- | --- |
| food-daily C | `fooddaily` | `fooddaily.qa_browser` | 8901 |
| food-baking B | `bakebook` | `bakebook.qa` | 8902 |
| food-weekly C | `weekplan` | `weekplan.qa` | 8903 |
| food-appliances B | `techkitchen` | `techkitchen.qa` | 8904 |
| home-practical C | `udobdom` | `udobdom.qa` | 8905 |
| garden-season C | `sezon` | `sezon.qa` | 8906 |
| plants-home C | `flora` | `flora.qa` | 8907 |
| games-story C | `saga` | `saga.qa` | 8908 |
| games-rpg C | `quest` | `quest.qa` | 8909 |
| games-survival C | `craft` | `craft.qa` | 8910 |

Чего нет в чистой копии и что из этого следует:
- `qa/node_modules` — ставится `npm ci` (выше).
- `var/<сайт>/private` — закрытые снимки источников (сырой текст страниц, не в git: права и срок хранения).
  Публичный сайт без них работает полностью. Логика валидатора черновиков food-baking и food-appliances
  проверяется на синтетической фикстуре и в чистой копии; не выполняется там только полная сверка текста черновиков
  с источником — по одному тесту на сайт, SKIPPED с причиной «нет закрытых снимков источников» (32 passed + 1 skipped
  и 22 passed + 1 skipped). Снимки не в git, а скачать их заново после заморозки знаний нельзя (CLOSED_WORLD).
- food-daily: БД пайплайна (`var/food-daily/preview/*.sqlite3`) не нужна — сайт читает `data/content-snapshot.json`;
  редактор `/redaktor/` без секрета отвечает 401 с запросом Basic Auth (проверено: `FOOD_DAILY_C_EDITOR_SECRET`
  на несуществующий файл, чистая копия на 8901); секрет создаётся вне репозитория, см. выше.

## Проверено 13.10.2026

- Шаг 1 на чистой копии: `git worktree add --detach <scratchpad>/wt-template-food-weekly-c origin/claude/template-food-weekly-c` → exit 0;
  в ней `bash templates/food-weekly/bin/food-weekly test` → 22 passed, главная отдаёт 200; копия удалена (`git worktree remove`).
  Превью из неё не запускалось: порт 8873 занят рабочим превью той же ветки.
- Шаги 2–3: все 10 основных превью запущены штатным `bin/<сайт>`, галерея — `http.server` на 127.0.0.1;
  переходы из галереи — `click-result.json`.
- Шаг 4 для всех 10 сайтов (13.10.2026, порты 8901–8910, действующие превью 8864–8876 продолжали отвечать):
  `npm ci` exit 0; запуск штатной командой с `--port` — `/healthz` за 0,25 с; главная 200 со своим variant-id;
  обход sitemap и всех `/static/` ресурсов — 0 ошибок; полная браузерная приёмка через `QA_BASE` — exit 0,
  провалов 0, axe 0; ширины 320/390/768/1440 — 0 замечаний; сервер остановлен. Тесты: 8 сайтов — все passed;
  food-baking и food-appliances на первом прогоне упали (3 и 1 тест: нет `var/.../private`), после пометки —
  28 passed + 3 skipped и 20 passed + 1 skipped. Итоги по сайтам — `clean-result.json` рядом.

## 5. Перенос на другую машину

Комплекты переноса 10 основных сайтов (код из коммита, публичный контент, редакционная база food-daily с версиями,
точные команды) — `../kits/KITS.md`; у каждого комплекта свой `INSTALL.md`.

