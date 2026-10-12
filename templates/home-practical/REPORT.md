# Отчёт home-practical, вариант A «Удобный дом» (rooms-cards)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS** (закрытый preview; production заблокирован).
Проверенный код: `06d708c31eb8585df0aa21484546e080bba4ac6a`, ветка `claude/template-home-practical`, база — origin/main `a7f7cb6`.

## Как открыть

- Preview: `http://127.0.0.1:8851/` (только loopback; `noindex, nofollow`; robots `Disallow: /`). Запуск: `bin/home-practical start`.
- Скриншоты (390 и 1440 px): `docs/screenshots/06d708c/` — главная, помещение, каталог с фильтром, инструкция, подборка, пустой фильтр.
- Артефакт: `var/home-practical/build/06d708c…/` — 49 файлов, tree_sha256 `692f5d8d…a27e`.

## Проверки на 06d708c (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/home-practical test` | 0 | 12 passed |
| `ruff check .` + `ruff format --check .` (шаблон) | 0 | чисто |
| `pytest tests/unit/test_permission_matrix.py` (корень) | 0 | 192 passed |
| `bin/home-practical content validate` | 0 | 13/13 ok |
| `bin/home-practical build --commit HEAD` | 0 | 49 файлов, все URL sitemap 200 |
| `bin/home-practical qa --shots … --out docs/verification-browser-qa.json` | 0 | 32 действия PASS, axe 0 на 18 стр. × 2, консоль — только ожидаемый 404 |
| `python3 qa/viewports.py 8851 …` | 0 | 41 URL × 320/390/768/1440 — 0 замечаний |

Карта действий с PASS/NOT_RUN — `docs/ACTION-MAP.md`. Метрики (лаборатория, loopback, без троттлинга, headless Chromium):
LCP 52–172 мс, CLS 0 на 6 типах страниц × 2 ширины; самая тяжёлая инструкция — 21 КБ HTML.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: все типы страниц из ТЗ, поиск, фильтры, сброс, пустые состояния, теги, оглавление, чек-лист, сохранённое, печать, мобильное меню, клавиатура |
| наполнение | 13 инструкций в 6 помещениях и 4 задачах на фактах 15 открытых страниц; тексты — черновики сессии Claude (`manual_standin`), не Qwen, редакцией не проверены; на кухне 1 инструкция, на рабочем месте 1 |
| изображения | своих фото нет; используются собственные SVG-пиктограммы помещений |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT); права на использование фактов и ссылок на товары — на решение владельца |

## Изменения в общих файлах

`inventory/network-allowlist.yaml` (+4 хоста, только GET) и `tests/unit/test_permission_matrix.py` (точный состав allowlist).
