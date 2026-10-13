# Отчёт garden-season, вариант A «Дача по сезону» (month-calendar)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `2ba827da6c51f32a4ff785cb47025068138d05df`, ветка `claude/template-garden-season` (origin/main a7f7cb6).

## Как открыть

- Preview: `http://127.0.0.1:8853/` (loopback, `noindex, nofollow`).
- Скриншоты (390 и 1440 px): `docs/screenshots/2ba827d/` — главная, месяц, декабрь, работа, культура, регион.
- Артефакт: `var/garden-season/build/2ba827d…/` — 65 файлов.

## Проверки на 2ba827d (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/garden-season test` | 0 | 0 — 12 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/garden-season build --commit HEAD` | 0 | 0 — var/garden-season/build/2ba827d… |
| `python3 -m sezon.qa …` | 0 | 0 — 29 действий PASS; axe 0 |
| `python3 qa/viewports.py 8853 …` | 0 | 0 — 61 URL × 4 ширины, 0 замечаний |
| `python3 -m sezon.qa --shots docs/screenshots/2ba827d --out docs/verification-browser-qa.json …` | 0 | 29 действий PASS; axe 0 на 46 стр.×ширин |
| `python3 qa/viewports.py 8853 …` | 0 | 61 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 44–472 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: год по месяцам, месяц с группами по регионам, работа со сроками и регионом, культуры с сеткой регион × месяц, регионы, подборки, поиск, 404 |
| наполнение | 18 работ по календарям OSU Extension (Орегон) и RHS (Великобритания), 4 добавлены ночью 13.10; сроков для России в источниках нет — не придуманы; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |

## Обновление на b4e32db (13.10.2026)

Meta description длиннее одного предложения теперь режется по запятой или тире (а не посреди фразы, как «…с которыми нельзя…»); у garden-season описания работ были до 263 символов — теперь ≤160. Тест проверяет все URL sitemap (20–160 символов) и случай с запятой.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/garden-season test` | 0 | 13 passed in 0.72s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m sezon.qa --shots docs/screenshots/b4e32db --out docs/verification-browser-qa.json` | 0 | 29 действий PASS, axe 0 |
| `python3 qa/viewports.py 8853 '/poisk/?q=газон' /nesushchestvuet/` | 0 | 61 URL × 4 ширины, 0 замечаний |
| `bash bin/garden-season build --commit HEAD` | 0 | собрано из b4e32db |

Лабораторный LCP (loopback, без троттлинга) — до 140 мс. Карта действий — `docs/ACTION-MAP.md`.
