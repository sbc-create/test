# animedia-portal — финализация профиля/пакета (TEMPLATE-ANIMEDIA-FINALIZATION-20)

Свидетельства этого каталога измерены в текущей сессии на локальном
loopback-стенде (`.venv/bin/python -m factory lords-preview --site
animedia-preview --serve --port 8850`, синтетический каталог `fixture/test`).
Инструмент измерения — `tests/tools/measure_reference.js` (штатный инструмент
репозитория, без изменений). Задача сессии — не ремонт (предыдущий ремонт
зафиксирован в `../visual-candidate-repair/`), а финализация: проверить, что
уже сделанное не разошлось с профилем, и явно назвать то, что чинить нельзя
в границах Animedia.

## Что проверено

Пять поверхностей (`/`, `/catalog/`, `/collections/`, `/title/<slug>/`,
несуществующий адрес) × три вьюпорта (390/768/1440) — числа в
`geometry-{home,catalog,collection_hub,title,not_found}.json`.

- **Геометрия.** `outer_gutter` = 1px на всех 15 комбинациях (совпадает с
  `theme.tokens.gutter` профиля). Горизонтальной прокрутки нет ни на одной
  комбинации (`horizontal_overflow: false` везде). Единственное отступление —
  `geometry-not_found.json` показывает `outer_gutter: 0` — это тот же
  известный артефакт эвристики инструмента, что описан в
  `../visual-candidate-repair/README.md`: страница `not_found` слишком
  минимальна для эвристики «вложенный блок уже вьюпорта». Перепроверено
  напрямую через `getComputedStyle('.container').paddingLeft` на всех трёх
  вьюпортах отдельным разовым скриптом — везде `1px`, `left: 0`, ширина
  контейнера равна ширине документа. Реального дефекта нет.
- **Типографика.** `h1` = 22.4px (`1.4rem` от базовых 16px) и `h2` = 18.4px
  (`1.15rem`) на `home`/`title` — совпадает с токенами профиля `h1_size`/
  `h2_size`. На `catalog` первый `<h2>` в документе — заголовок блока фильтров
  «Фильтры» (15.2px = `.95rem`), у него отдельное, не завязанное на токен
  правило в общей теме (`factory/lords/theme.py:687`, `.facets h2`) —
  одинаково для всех профилей Lords, не дефект профиля.
- **Карточки.** `card_aspect_ratios` = `0.67` (≈ `2/3`, профильный
  `layout.card_ratio`) на всех поверхностях с карточками — совпадение точное.
- **Колонки.** `grid_columns` содержит `2` (390), `4` (768), `6` (1440) на
  `home`/`catalog`/`collection_hub` — совпадает с `layout.columns`
  (`mobile: 2, tablet: 4, desktop: 6`).
- **Изображения.** `home`: 18/18 карточек с `<img>` (см. также
  `tests/unit/test_animedia_preview_content.py::TestПостерыНаГлавной`,
  проходит). `catalog`: 24/24, `title`: 7/7. `collection_hub`: 0 — ожидаемо:
  `layout.show_collection_cards: false` в профиле, карточки подборок —
  текстовые (`card__body` без `card__poster`), подтверждено разметкой
  (`/collections/` отдаёт 4 реальные подборки фикстуры, не заглушку).
- **facet_position: top.** На `/catalog/` форма `.facets.facets--row`
  расположена в DOM до `.grid` — совпадает с профилем.
- **hero: timeline.** Главная отдаёт `<section data-block="hero"
  class="hero hero--timeline">` — совпадает.
- **type_priority.** `/catalog/` фасет «Тип» отдаёт порядок Аниме → Сериал →
  Фильм → Мультфильм — совпадает с `layout.type_priority`
  (`[anime, series, movies, animation, dorama]`). Отчёт `build_preview(...)
  .report["active_types"][0] == "anime"` — тест
  `test_animedia_preview_content.py::test_аниме_первым_типом_на_главной`
  проходит.
- **JSON-LD / XSS guard.** `/title/…/` отдаёт два корректных
  `<script type="application/ld+json">` (`TVSeries`/`Movie` + `BreadcrumbList`),
  сериализация — штатная `_jsonld()` (`factory/lords/render.py:105-127`,
  экранирование `</script>` в значении не ослаблено — код не менялся).
- **Контент.** Ни «Анонсы», ни «Появилось видео» нигде не введены — эти
  названия не существуют в блюпринте `lords` (см. `knowledge/DECISIONS.md`
  D139) и в этой сессии не добавлялись.

## Что НЕ починено и почему (передано Lords writer)

Один воспроизводимый дефект найден и НЕ исправлен: он живёт в общем движке
(`blueprints/lords/blueprint.yaml`, `factory/lords/render.py`,
`factory/lords/plan.py`) — вне разрешённой для этой сессии области
(`blueprints/lords/profiles/animedia-portal.yaml`,
`sites/animedia-preview/**`). Полная передача — `CORE-HANDOFF-nav-order.md` в
этом каталоге.

## Целевые тесты (прогон этой сессией)

```
.venv/bin/python -m pytest tests/unit/test_animedia_preview_content.py \
  tests/unit/test_lords_type_priority.py \
  tests/unit/test_lords_poster_and_banner_layers.py \
  tests/unit/test_lords_ongoing_episodes.py \
  tests/test_collection_contract.py -q
# 80 passed, 3 skipped (skip — не про Animedia: у этого оформления нет
# крупного постера/баннера страницы тайтла)

PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node_modules/.bin/playwright test \
  --config=playwright.templates.config.js --grep "animedia-portal"
# 24 passed — families-routes, template-contract (390/768/1440, три вьюпорта
# каждый: блоки на месте, нет горизонтальной прокрутки, колонки совпадают с
# манифестом, порядок блоков совпадает с манифестом), template-a11y (axe,
# три вьюпорта), template-perf (раскладка не прыгает, документ не раздут)
```

Полный `bash tests/run-all.sh` этой сессией не запускался — задание требует
только целевых Animedia/profile/render/evidence тестов.

## Что НЕ покрыто

Как и в `../visual-candidate-repair/`, полный scoring по контракту PR #81
(`contracts/visual-scoring/1.0.0`) этой сессией не выполнен и не может: этот
контракт и его схема (`schemas/visual-scoring-result.schema.json`) в этой
ветке отсутствуют (принадлежат PR #80/#81, изменять и переносить их сюда
запрещено постановкой). Сертификация `VISUAL_CERTIFIED` — задача отдельного
независимого checker-прогона (`checker_identity != candidate_author_identity`
контракта PR #81), а не этой сессии.
