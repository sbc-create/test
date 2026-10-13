# Отчёт games-survival, вариант C «База выживания» (inventory-first)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `1a43a003fcc02f76f46f808900e94a72b026097e`, ветка `claude/template-games-survival-c` (вариант B 978d803).

## Как открыть

- Preview: `http://127.0.0.1:8872/` (loopback, `noindex, nofollow`).
- Отличие от A (8861) и B (8862): главная — отметки инвентаря; итог — «можно сделать сейчас» и «не хватает одного» с количествами по слотам сетки; планировщик B сохранён. Свои CSS/JS, ключи gsv-inv:*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/1a43a00/` — инвентарь (доски, палка, уголь), главная, планировщик, игра, раздел, предмет, ресурс, биом.
- Артефакт: `var/games-survival/build/1a43a00…/` — 43 файлов.

## Проверки на 1a43a00 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-survival test` | 0 | 0 — 21 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-survival build --commit HEAD` | 0 | 0 — 43 файла, var/games-survival/build/1a43a00… |
| `bin/games-survival qa …` | 0 | 0 — 36 действий PASS; axe 0 |
| `python3 qa/viewports.py 8872 …` | 0 | 0 — 41 URL × 4 ширины, 0 замечаний |
| `bin/games-survival qa --shots docs/screenshots/1a43a00 --out docs/verification-browser-qa.json …` | 0 | 36 действий PASS; axe 0 на 38 стр.×ширин |
| `python3 qa/viewports.py 8872 …` | 0 | 41 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 44–304 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: инвентарь (память выбора, блок пустой отправки, 400), «можно сейчас» и «не хватает одного», планировщик из B, каталог, предметы, постройки, поиск, 404 |
| наполнение | как в A/B: Minecraft (Java Edition 26.3), 14 предметов/блоков (из досок и палок — деревянные инструменты), 4 постройки, 4 ресурса, 4 биома; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |

## Обновление на e0f9abf (13.10.2026)

Meta description: у разделов — из данных (число материалов, вики-источник, версия игры) вместо «Раздел — Игра.» (22–29 символов); у материалов — целые предложения до 160 символов (было до 263 и обрезалось в выдаче посреди фразы). Новый тест проверяет все URL sitemap: 20–160 символов.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-survival test` | 0 | 22 passed in 0.82s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m craft.qa --shots docs/screenshots/e0f9abf --out docs/verification-browser-qa.json` | 0 | 36 действий PASS, axe 0 |
| `python3 qa/viewports.py 8872 '/iz-togo-chto-est/?est=doski&est=palka&est=ugol' '/iz-togo-chto-est/?est=almaz' '/planirovshchik/?item=zabor&n=64' /nesushchestvuet/` | 0 | 41 URL × 4 ширины, 0 замечаний |
| `bash bin/games-survival build --commit HEAD` | 0 | собрано из e0f9abf |

Лабораторный LCP (loopback, без троттлинга) — до 280 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 31c0a92 (13.10.2026)

Основной вариант (решение владельца 13.10.2026). По рекомендации проверены связи «из чего → во что»: 5 страниц (кирка, лопата, меч, топор, кровать — рецепт планировщик не считает) не ссылались на материалы рецепта источника (13 связей) — добавлено. Тесты на все 27 страниц: каждый материал продукта связан ссылкой, каждая связь «куда идёт» — в обе стороны; браузерные сценарии связей — как в A.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-survival test` | 0 | 24 passed in 0.85s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m craft.qa --shots docs/screenshots/31c0a92 --out docs/verification-browser-qa.json` | 0 | 40 действий PASS, axe 0 |
| `python3 qa/viewports.py 8872 '/iz-togo-chto-est/?est=doski&est=palka&est=ugol' '/iz-togo-chto-est/?est=almaz' '/planirovshchik/?item=zabor&n=64' /nesushchestvuet/` | 0 | 41 URL × 4 ширины, 0 замечаний |
| `bash bin/games-survival build --commit HEAD` | 0 | собрано из 31c0a92 |

Лабораторный LCP (loopback, без троттлинга) — до 524 мс. Карта действий — `docs/ACTION-MAP.md`.
