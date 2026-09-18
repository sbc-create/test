# Lords shared template — третий цикл ремонта (PR #76, слой factory/lords/**)

Продолжение `visual-repair-cycle-2` со стороны владельца общего слоя
(`factory/lords/**`). Задача этого цикла — CORE-HANDOFF от Animedia writer:
`artifacts/evidence/templates/animedia-portal/finalization-01/
CORE-HANDOFF-nav-order.md` (`git show
b023bd50cced8d281cb3814a75bf72b429afee0b`, ветка
`origin/claude/animedia-template-finalization-01`, только чтение — без
checkout и без merge).

Кандидат для измерения — снова `sites/animedia-preview`
(`blueprints/lords/profiles/animedia-portal.yaml`), не изменён: read-only
тестовый стенд, как и в первых двух проходах.

## Что найдено

CORE-HANDOFF описывал дефект как «два противоречащих порядка на соседних
экранах одной витрины»: шапка отдаёт «Фильмы» первым и «Аниме» последним, а
фасет «Тип» на `/catalog/` (в другой, ещё не смерженной в эту ветку версии
`factory/lords/content_types.py::active_types`) якобы уже уважает профильный
порядок. Проверка на этой ветке (`git diff` между
`origin/claude/animedia-template-finalization-01` и `35c0383` по
`factory/lords/render.py`/`content_types.py`/`plan.py`) показала, что в
текущем common-baseline **ни один** из двух компонентов не уважает какой-либо
порядок, объявленный пакетом или профилем: и шапка, и фасет «Тип» шли
фиксированным порядком `blueprints/lords/blueprint.yaml::sections` /
`content_types.CONTENT_TYPES`, одинаковым для всех шести профилей Lords.
`layout.type_priority`, предложенный хендоффом, не существует нигде в этой
ветке (`grep -rn "type_priority"` — ноль совпадений) — это было собственное,
не смерженное расширение профиля/движка на ветке Animedia, а не часть общего
контракта.

Вместо переноса этого чужого поля в общий слой использован **уже
существующий обязательный контракт**: `navigation.primary`
(`schemas/site-package.schema.json`, `required`). Каждый пакет Lords уже
объявляет его осмысленно — `sites/animedia-preview/package.yaml` прямо
говорит «Аниме первым: витрина заведена ради него» — и то же поле уже
служит единственным источником шапки в другом blueprint фабрики
(`factory/render.py:217`, `payload-next-multisite`). Только
`factory/lords/render.py` его никогда не читал — ни для шапки, ни для
фасета.

Живая проверка на этой ветке (`python3 -m factory lords-preview --site
animedia-preview --serve`) подтвердила дефект напрямую:

```
шапка:  Главная, Каталог, Фильмы, Сериалы, Мультфильмы, Аниме, Подборки, …
фасет:                     Фильм,  Сериал,  Мультфильм, Аниме
package.yaml.navigation.primary:  Аниме, Сериалы, Фильмы, Мультфильмы
```

## Что исправлено

`factory/lords/render.py`:

- Новая функция `_navigation_primary_paths(package)` — читает
  `package.navigation.primary` (уже обязательное поле схемы, ничего нового
  не добавлено).
- Новая функция `_priority_reorder(items, key_of, priority)` — переставляет
  только те элементы списка, чей ключ владелец назвал явно, строго в
  объявленном порядке; всё остальное остаётся на своём текущем месте. Это не
  замена состава меню на `navigation.primary` (короткий курируемый список у
  каждого сайта — 3–4 пункта из 13), а точечная перестановка: раздел, о
  котором пакет не высказался (Каталог, Подборки, Новое, Расписание, Жанры,
  Годы, Страны, Поиск), не двигается — иначе сломалась бы кросс-сайтовая
  noindex-навигация, которую блюпринт держит намеренно («остальные сайты
  держат раздел как навигацию с noindex», `blueprints/lords/blueprint.yaml`).
- `_context()`: порядок `nav` теперь идёт через `_priority_reorder` по
  `page.path`.
- `render()`: порядок `kinds` (фасет «Тип», используется и на `/catalog/`, и
  на главной через `ctx["active_types"]`) идёт через тот же
  `_priority_reorder` по пути раздела типа (`SECTION_TYPE`), тем же ключом
  `navigation.primary` — один резолвер на оба места, как и просил
  CORE-HANDOFF, без хардкода конкретных имён типов.

Ни `blueprints/lords/blueprint.yaml`, ни `factory/lords/plan.py`, ни схема
(`schemas/site-package.schema.json`, `navigation` там уже `required`) не
менялись: правка обошлась без изменения контракта.

### Обратная совместимость

`navigation.primary` каждого «обычного» профиля (`lords-01/02/03/04`,
`zona-cinema-preview`) уже перечисляет те же разделы в том же порядке, что и
`blueprints/lords/blueprint.yaml` — перестановка для них холостая.
Подтверждено тестом (`test_lords_01_header_nav_is_unchanged`,
`test_zona_cinema_preview_header_nav_is_unchanged`): рендер этих сайтов
побитово не изменился. Меняется только `animedia-preview`, чей
`navigation.primary` реально расходится с порядком блюпринта — именно то
расхождение, которое и было дефектом.

## Регрессионный тест

`tests/unit/test_lords_navigation_priority.py` — 5 тестов:

- 2 доказывают исправленный дефект (шапка и фасет следуют
  `navigation.primary`) — **падали на START_HEAD** (`2 failed, 3 passed`),
  **проходят после правки** (`5 passed`);
- 1 доказывает, что служебные разделы не сдвинулись;
- 2 доказывают обратную совместимость на `lords-01`/`zona-cinema-preview`.

## Почему `overall_score` не изменился (33.19 → 33.19, 0.0 разницы)

Правка переставляет `<li>` внутри уже существующего `<nav>`/`<fieldset>` —
ни один из 639 токенов `tests/tools/measure_candidate_tokens.js` не
чувствителен к порядку ссылок внутри уже присутствующего блока (сам
`data-visual-role="primary-nav"` не сдвинулся). Эмпирически подтверждено:
свежий замер после правки — 639/639 токенов побитово идентичны замеру
cycle-2 (0 расхождений по значению). Пересчёт `factory/visual_scoring.compare()`
(contract 1.0.3, read-only) на обоих наборах токенов даёт одинаковый
`overall_score=33.186630083599`. Подробности и код — `scoring-summary.json`.

Отдельно установлен точный источник обнуления `structure_order` (30% веса,
0.0 на всех 15 ячейках и до, и после): эталонный pack `amd.online` (PR #80,
508 токенов) не содержит ни одного токена `block_order`/
`required_block_*_present` — инструмент замера эталона не способен снять
такие токены с чужого сайта, у которого нет `data-visual-role`. Это не
дефект кандидата (кандидат структурно готов на всех 15 ячейках) и не
`factory/lords/**` — контракт/инструмент замера эталона вне scope этой
ветки. Подробности — `scoring-summary.json.structure_order_zero_root_cause`.

## Итог

- **Дефект исправлен и подтверждён тестом** — реальный общий дефект
  Lords/Core, категория A.
- **`overall_score` = 33.19/100, порог 80 не достигнут** — доминирующие
  потери (`structure_order`=0 из-за пробела в эталонном паке/инструменте,
  `cards_media`≈24, `geometry`≈31 из-за `header_sticky`, `colors`≈41,
  `typography`≈69 из-за font-size/weight карточки) не относятся к
  `factory/lords/**`: часть принадлежит профилю Animedia (осознанные
  расхождения, не подгоняются под один эталон), часть — владельцу
  visual-scoring контракта/инструмента замера эталона. Полный список с
  владельцами — `remaining-blockers.md`.
- **Финальный статус: NEEDS_REPAIR.** Не READY_FOR_INDEPENDENT_REVIEW: порог
  80 не достигнут (критерий 1 не выполнен). Остаточные дефекты не
  фальсифицированы под зелёный результат и не оставлены немыми — каждый
  привязан к владельцу вне `factory/lords/**`.
