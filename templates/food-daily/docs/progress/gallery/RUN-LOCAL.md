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

## Проверено 13.10.2026

- Шаг 1 на чистой копии: `git worktree add --detach <scratchpad>/wt-template-food-weekly-c origin/claude/template-food-weekly-c` → exit 0;
  в ней `bash templates/food-weekly/bin/food-weekly test` → 22 passed, главная отдаёт 200; копия удалена (`git worktree remove`).
  Превью из неё не запускалось: порт 8873 занят рабочим превью той же ветки.
- Шаги 2–3: все 10 основных превью запущены штатным `bin/<сайт>`, галерея — `http.server` на 127.0.0.1;
  переходы из галереи — `click-result.json`.
