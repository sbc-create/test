# Отчёт games-story, вариант A «Сюжет пройден» (chapter-guides)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `1b5e5aee5c4d5957c61c5eb6dbdcb61f4bb024be`, ветка `claude/template-games-story` (база origin/main a7f7cb6).

## Как открыть

- Preview: `http://127.0.0.1:8857/` (loopback, `noindex, nofollow`).
- Скриншоты (390 и 1440 px): `docs/screenshots/1b5e5ae/` — главная, игра, гайд главы, предметы, видео, Farewell.
- Артефакт: `var/games-story/build/1b5e5ae…/` — 23 файлов.

## Проверки на 1b5e5ae (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-story test` | 0 | 10 passed |
| `ruff check . + ruff format --check .` | 0 | чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 192 passed |
| `bin/games-story content validate` | 0 | 11/11 |
| `bin/games-story build --commit HEAD` | 0 | 23 файла |
| `bin/games-story qa …` | 0 | 23 действий PASS; axe 0 на 28 стр.×ширин |
| `python3 qa/viewports.py 8857 …` | 0 | 19 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 44–160 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: игра, главы по порядку, маршрут, механики, предметы, сводка предметов, прогресс с сохранением и сводкой, видео-фасад, поиск, печать, 404 |
| наполнение | 1 игра (Celeste), 11 глав по Celeste Wiki; 2 проверенных видео (интервью разработчиков, не прохождение); тексты — `manual_standin`, не Qwen, без редакторской проверки. Вики других сюжетных игр закрыты (403) — ограничение наполнения |
| внешние интеграции | YouTube — только проверка oEmbed и плеер по нажатию; рекламы и счётчиков нет |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |

## Обновление на ff3ed16 (13.10.2026)

Meta description глав ≤160 символов: целые предложения, иначе по запятой или тире (было до 204 символов, обрезалось в выдаче). Тест проверяет все URL sitemap (20–160 символов). Дополнительные URL проверки ширин (поиск и 404) в этой записи заданы заново: прежняя команда в отчёте сокращена «…».

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-story test` | 0 | 11 passed in 0.40s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m saga.qa --shots docs/screenshots/ff3ed16 --out docs/verification-browser-qa.json` | 0 | 23 действий PASS, axe 0 |
| `python3 qa/viewports.py 8857 '/poisk/?q=Madeline' /nesushchestvuet/` | 0 | 19 URL × 4 ширины, 0 замечаний |
| `bash bin/games-story build --commit HEAD` | 0 | собрано из ff3ed16 |

Лабораторный LCP (loopback, без троттлинга) — до 188 мс. Карта действий — `docs/ACTION-MAP.md`.
