# Отчёт games-story, вариант B «Сюжет пройден: трекер» (progress-tracker)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `423ba88c63c8dda074beff1e27487bcb8d451fc8`, ветка `claude/template-games-story-b` (начата с a45135b варианта A).

## Как открыть

- Preview: `http://127.0.0.1:8858/` (loopback, `noindex, nofollow`). Вариант A — `http://127.0.0.1:8857/`; отличия — `docs/VARIANTS.md`.
- Скриншоты (390 и 1440 px): `docs/screenshots/423ba88/` — главная, трекер, гайд, предметы, вид предмета, видео.
- Артефакт: `var/games-story/build/423ba88…/` — 26 файлов.

## Проверки на 423ba88 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-story test` | 0 | 12 passed |
| `ruff check . + ruff format --check .` | 0 | чисто |
| `bin/games-story build --commit HEAD` | 0 | 26 файлов |
| `bin/games-story qa …` | 0 | 26 действий PASS; axe 0 на 28 стр.×ширин |
| `python3 qa/viewports.py 8858 …` | 0 | 22 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 44–144 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: панель прогресса, трекер с ограничением числом источника, общий трекер в гайде, предметы по видам, видео-фасад, поиск, печать, 404 |
| наполнение | тот же снимок, что в A: Celeste, 11 глав, 2 проверенных видео; тексты — `manual_standin`, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |

## Обновление на e0a9443 (13.10.2026)

Meta description глав ≤160 символов: целые предложения, иначе по запятой или тире (было до 204 символов, обрезалось в выдаче). Тест проверяет все URL sitemap (20–160 символов). Дополнительные URL проверки ширин (поиск и 404) в этой записи заданы заново: прежняя команда в отчёте сокращена «…».

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-story test` | 0 | 13 passed in 0.42s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m saga.qa --shots docs/screenshots/e0a9443 --out docs/verification-browser-qa.json` | 0 | 26 действий PASS, axe 0 |
| `python3 qa/viewports.py 8858 '/poisk/?q=Madeline' /nesushchestvuet/` | 0 | 22 URL × 4 ширины, 0 замечаний |
| `bash bin/games-story build --commit HEAD` | 0 | собрано из e0a9443 |

Лабораторный LCP (loopback, без троттлинга) — до 112 мс. Карта действий — `docs/ACTION-MAP.md`.
