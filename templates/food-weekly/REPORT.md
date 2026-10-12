# food-weekly — отчёт (12.10.2026)

| | |
| --- | --- |
| сайт | «Меню на неделю» (рабочее название) |
| ветка / worktree | `claude/template-food-weekly` / `/home/claude/wt-template-food-weekly` |
| база | `a7f7cb6` = origin/main |
| проверенный код | `8b1e34d` |
| preview | `http://127.0.0.1:8849/` — только петля сервера, доступ через SSH-туннель на 8849; `noindex` везде |
| артефакт | `var/food-weekly/build/8b1e34d0429ca0fe1e4e6c5fab38b39bc1a6bfdb/` (39 файлов) |
| скриншоты | `docs/screenshots/8b1e34d/{home,catalog,week,day,shopping}-{mobile,desktop}.png` |

## Объёмы

| что | число |
| --- | ---: |
| планов на 7 дней | 3 (на двоих, на семью из четырёх, осенний) |
| приёмов пищи в планах | 63 (7 × 3 × 3), блюд-ссылок — 69 |
| рецептов в каталоге-снимке food-daily | 22 (`recipe-catalog/1`, статус `preview_adapter`) |
| копий текстов рецептов | 0 |
| планов от Qwen | 0 (составлены сессией Claude, `manual_standin`) |
| проверено редактором | 0 |

## Проверки

| проверка | команда | exit | результат |
| --- | --- | :-: | --- |
| тесты | `bash templates/food-weekly/bin/food-weekly test` | 0 | 12 passed |
| ruff | `python3 -m ruff check templates/food-weekly && python3 -m ruff format --check templates/food-weekly` | 0 | 0 замечаний (линтер нашёл и помог исправить позднее связывание переменной в QA-скрипте) |
| браузер + axe 4.13.0 | `python3 -m weekplan.qa --shots docs/screenshots/8b1e34d` | 0 | все сценарии true; axe — 0 нарушений на 10 страницах × 2 экрана после исправления `heading-order` и `aria-allowed-role` |
| сканер секретов | `python3 scripts/secret_scan.py` | 0 | чисто |
| CI | GitHub Actions | ожидается FAIL | общий линт `tests/unit` на main (handoff в ветке food-daily: `docs/HANDOFF-CI.md`) |

Сценарии: замена блюда через форму меняет и неделю, и список покупок; недопустимая замена
(плов на завтрак) отклоняется с предупреждением; отметки «куплено» сохраняются; замена
работает без JS; без горизонтальной прокрутки на 390 и 1440 px.

## Готовность

Закрытый preview (главная, каталог меню, неделя, день, список покупок, инструкция,
подборка, 404, SEO-матрица и тесты, доступность, изоляция и сборка из commit): **11 из 11**.
Production — нет: домен (BLOCKED_INPUT); соседний сайт рецептов не опубликован, поэтому
ссылки ведут в его закрытый preview; планы не проверены редактором.
Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**.
