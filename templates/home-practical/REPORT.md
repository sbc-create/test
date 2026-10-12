# Отчёт home-practical, вариант B «Удобный дом: чек-листы решений» (problem-checklists)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS** (закрытый preview; production заблокирован).
Проверенный код: `819b9348d1d7dc32c0027e694fb52b346527455f`, ветка `claude/template-home-practical-b` (начата с 19fb887 варианта A).

## Как открыть

- Preview B: `http://127.0.0.1:8852/` (loopback, `noindex, nofollow`). Вариант A для сравнения: `http://127.0.0.1:8851/`.
- Скриншоты (390 и 1440 px): `docs/screenshots/819b934/` — главная, проблема, каталог, инструкция, помещение, пустой фильтр.
- Артефакт: `var/home-practical/build/819b934…/` — 50 файлов, tree_sha256 `0ff24ef3…3b93`.
- Отличия от A: `docs/VARIANTS.md`.

## Проверки на 819b934 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/home-practical test` | 0 | 15 passed |
| `ruff check .` + `ruff format --check .` (шаблон) | 0 | чисто |
| `pytest tests/unit/test_permission_matrix.py` (корень) | 0 | 192 passed |
| `bin/home-practical build --commit HEAD` | 0 | 50 файлов, все URL sitemap 200 |
| `bin/home-practical qa --shots … --out docs/verification-browser-qa.json` | 0 | 34 действия PASS, axe 0 на 20 стр. × 2 |
| `python3 qa/viewports.py 8852 …` | 0 | 49 URL × 320/390/768/1440 — 0 замечаний |

Метрики (лаборатория, loopback, без троттлинга): LCP 44–168 мс, CLS 0. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: проблемы, каталог с фильтрами и сортировкой, шаги-чек-листы с прогрессом, итоговая проверка, сохранённое, печать, поиск, теги, подборки, 404 |
| наполнение | тот же проверенный снимок, что в A: 13 инструкций на фактах 15 страниц; черновики сессии Claude (`manual_standin`), не Qwen, без редакторской проверки |
| внешние интеграции | нет |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT); A и B — варианты одного сайта, публикуется один |
