# Отчёт food-appliances («Готовим в технике»)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS** (preview закрыт; production заблокирован).
Проверенный код: `0dc5e4d19c54c2f69cce8a4c9af4a53a0eea9b40`, ветка `claude/template-food-appliances`, база — origin/main `a7f7cb6`.

## Что можно открыть

- Preview: `http://127.0.0.1:8850/` (loopback, `noindex, nofollow`, robots `Disallow: /`), запуск — `bin/food-appliances start`.
- Скриншоты 2 вьюпорта × 6 страниц: `docs/screenshots/0dc5e4d/`.
- Артефакт сборки: `var/food-appliances/build/0dc5e4d…/` (29 файлов, tree_sha256 `94b242f2…8569`).

## Проверки (фактически запущены на 0dc5e4d)

| команда | exit | результат / артефакт |
| --- | --- | --- |
| `bin/food-appliances test` | 0 | 11 passed |
| `ruff check .` + `ruff format --check .` (в шаблоне) | 0 | чисто |
| `bin/food-appliances qa --shots docs/screenshots/0dc5e4d --out docs/verification-browser-qa.json` | 0 | axe 4.13.0: 0 нарушений на 10 страницах × 2 вьюпорта; сценарии true; консоль — только ожидаемый 404 |
| `bin/food-appliances build --commit HEAD` | 0 | 29 файлов, все страницы sitemap отдали 200 |
| `pytest tests/unit/test_permission_matrix.py` (корень) | 0 | 192 passed |

Сценарии браузера: ссылка табло ведёт к шагу; поиск по режиму «тушение» дал 2 рецепта; первый Tab — skip-link;
без JS открываются рецепт (6 шагов) и поиск (6 результатов); горизонтального скролла нет на 12 снимках.
Одна найденная проблема исправлена до commit: контраст ссылок 4.4:1 → #0a6863 (≈5.9:1).

## Объём

- 12 полных рецептов: мультиварка 6, аэрогриль 6 (минимум задания ≥12 / ≥2 прибора — выполнен).
- Режимы из источника: «Выпечка» 3, «Жарка» 4, «Тушение» 2, «Крупы» 2 рецепта (страницы режимов от 2 рецептов).
- 25 URL в sitemap; факты: 64 записи, 19 полных; гриль — 0 полных, раздел закрыт 404.
- Аудит: 3 референса, таблица наблюдений, 5 улучшений — `docs/AUDIT.md`.

## Блокеры production

- Домен и `production_authorized` отсутствуют → BLOCKED_INPUT (переключатель проверен тестом).
- Права на исходные рецепты (eda.rambler.ru) не подтверждены → BLOCKED_RIGHTS; в git нет текста шагов источника.
- Тексты — черновики сессии Claude (`manual_standin`, `ai_draft`), не Qwen; нужна редакторская проверка.
- Своих изображений нет (Recipe без `image`).
- CI main красный из-за 20 давних ошибок в tests/unit (вне шаблона, передано).

## Осталось (мелкое)

- Мобильная шапка: placeholder поиска обрезан («Блюдо, продукт, р…»).
- Хлебные крошки на 390 px переносят «/» в начало строки.
- Гриль: нужны источники с полными фактами режима/температуры.

## Обновление на 7575262 (ночь 12–13.10, после вариантов B и C)

Изменения: метатеги варианта `device-panel` (тест). Перезапущено на 7575262: `python3 -m techkitchen.qa --shots docs/screenshots/7575262 --out docs/verification-browser-qa.json` → exit 0, 17 сценариев без провалов, axe 4.13.0 — 0 нарушений, 12 скриншотов;
`python3 qa/viewports.py 8850 /poisk/?q=тушение /nesushchestvuet/` → exit 0, 27 URL × 4 ширины — 0 замечаний (`docs/verification-viewports.json`); `bin/food-appliances test` → 13 passed.
