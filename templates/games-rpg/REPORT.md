# Отчёт games-rpg, вариант A «Гайды RPG» (codex-sections)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `2bb97b82f0a667c648d7530ed3c656f2ca66ea18`, ветка `claude/template-games-rpg` (origin/main a7f7cb6).

## Как открыть

- Preview: `http://127.0.0.1:8859/` (loopback, `noindex, nofollow`).
- Скриншоты (390 и 1440 px): `docs/screenshots/2bb97b8/` — главная, игра, раздел, персонаж, билд, квест.
- Артефакт: `var/games-rpg/build/2bb97b8…/` — 40 файлов.

## Проверки на 2bb97b8 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-rpg test` | 0 | 0 — 11 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-rpg build --commit HEAD` | 0 | 0 — 40 файлов, var/games-rpg/build/2bb97b8… |
| `bin/games-rpg qa …` | 0 | 0 — 20 действий PASS; axe 0 |
| `python3 qa/viewports.py 8859 …` | 0 | 0 — 36 URL × 4 ширины, 0 замечаний |
| `bin/games-rpg qa --shots docs/screenshots/2bb97b8 --out docs/verification-browser-qa.json …` | 0 | 20 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8859 …` | 0 | 36 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 44–160 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: игра, разделы (персонажи, билды, квесты, механики, предметы), материал с паспортом/прогрессией/этапами/паспортом предмета, версия игры, поиск, печать, 404 |
| наполнение | Baldurs Gate 3: 9 спутников, 3 основы билдов (у 2 кастеров таблица скрыта), 2 механики, 2 квеста, 8 предметов (без цены), версия Patch 8; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |

## Обновление на 8e3bb49 (13.10.2026)

Meta description: у разделов — из данных (число материалов, вики-источник, версия игры) вместо «Раздел — Игра.» (22–29 символов); у материалов — целые предложения до 160 символов (было до 263 и обрезалось в выдаче посреди фразы). Новый тест проверяет все URL sitemap: 20–160 символов.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-rpg test` | 0 | 12 passed in 0.56s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m quest.qa --shots docs/screenshots/8e3bb49 --out docs/verification-browser-qa.json` | 0 | 20 действий PASS, axe 0 |
| `python3 qa/viewports.py 8859 '/poisk/?q=Gale' /nesushchestvuet/` | 0 | 36 URL × 4 ширины, 0 замечаний |
| `bash bin/games-rpg build --commit HEAD` | 0 | собрано из 8e3bb49 |

Лабораторный LCP (loopback, без троттлинга) — до 136 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 62caae3 (13.10.2026)

Meta description длиннее одного предложения теперь режется по запятой или тире (а не посреди фразы, как «…с которыми нельзя…»); у garden-season описания работ были до 263 символов — теперь ≤160. Тест проверяет все URL sitemap (20–160 символов) и случай с запятой.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-rpg test` | 0 | 12 passed in 0.63s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m quest.qa --shots docs/screenshots/62caae3 --out docs/verification-browser-qa.json` | 0 | 20 действий PASS, axe 0 |
| `python3 qa/viewports.py 8859 '/poisk/?q=Gale' /nesushchestvuet/` | 0 | 36 URL × 4 ширины, 0 замечаний |
| `bash bin/games-rpg build --commit HEAD` | 0 | собрано из 62caae3 |

Лабораторный LCP (loopback, без троттлинга) — до 128 мс. Карта действий — `docs/ACTION-MAP.md`.
