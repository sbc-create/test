# Передача Lords writer: порядок пунктов в шапке не следует `type_priority`

Статус: **NEEDS_REPAIR на уровне общего движка**, вне области этой сессии
(`blueprints/lords/profiles/animedia-portal.yaml`, `sites/animedia-preview/**`
только). Правка `factory/lords/**` и `blueprints/lords/blueprint.yaml`
запрещена постановкой TEMPLATE-ANIMEDIA-FINALIZATION-20. Ниже — точная
передача, а не предположение: дефект измерен на локальном стенде.

## Файл и функция

- `factory/lords/plan.py::build_plan()` — порядок `plan.pages` определяется
  проходом `for section, spec in sections.items()`, где `sections` — фиксированный
  словарь `blueprints/lords/blueprint.yaml::sections` (строки 12–25), **один и
  тот же порядок для всех шести профилей Lords**: `catalog_index, movies_index,
  series_index, animation_index, anime_index, dorama_index, collections_index,
  new_index, schedule, genres_index, years_index, countries_index, search`.
- `factory/lords/render.py::_context()` (строка ~2725) строит пункты шапки
  `nav = [(page.section, page.path) for page in site_plan.pages if page.in_menu
  and page.section != "home"]` — прямое наследование порядка из `build_plan()`,
  без участия `profile["layout"]["type_priority"]` и без чтения
  `package["navigation"]["primary"]`.
- Для сравнения: `factory/lords/render.py:2927-2928` строит `kinds` (порядок
  типов для фасета «Тип» на `/catalog/` и для `active_types` на главной) через
  `ct.active_types(site_plan.type_states, order=type_priority)`, где
  `type_priority = profile["layout"]["type_priority"]` — **эта** точка входа
  корректно уважает профиль (см. `knowledge/DECISIONS.md` D139, где её и
  ввели). Разница в поведении между двумя точками входа — сам дефект.
- Поле `navigation.primary` пакета (`schemas/site-package.schema.json:642`,
  обязательное поле) не читается нигде в `factory/lords/*.py` — подтверждено
  `grep -rn "navigation" factory/lords/*.py` (ноль совпадений, кроме schema).
  Поле заполнено (`sites/animedia-preview/package.yaml:140-151`, с явным
  решением владельца «аниме первым»), но не имеет эффекта.

## Воспроизведение

```
.venv/bin/python -m factory lords-preview --site animedia-preview --serve --port 8850
curl -s http://127.0.0.1:8850/ | grep -oE '<nav class="site-nav".*?</nav>'
# … Каталог, Фильмы, Сериалы, Мультфильмы, Аниме, Подборки, Новое, …
curl -s http://127.0.0.1:8850/catalog/ | grep -A1 '<legend>Тип</legend>'
# … Аниме, Сериал, Фильм, Мультфильм …
```

Шапка отдаёт «Фильмы» первым разделом контента и «Аниме» последним. Фасет
«Тип» на той же витрине, той же сборкой — «Аниме» первым. Одна витрина,
два противоречащих порядка на соседних экранах одного перехода.

## Почему это дефект, а не два равноценных решения

`blueprints/lords/profiles/animedia-portal.yaml` содержит прямое решение
владельца («OWNER_DECISION»-уровня по стилю, хоть и не размеченное тегом):

> Портал заведён ради аниме (см. purpose и navigation.primary пакета — там
> аниме тоже идёт первым): свой порядок типов не должен зависеть от общего
> перечня content_types.py, который ведёт фильмами ради Lords.

и

> Аниме первым: витрина заведена ради него, и прятать его за фильмами
> значит спорить с собственным назначением. (`package.yaml`, `navigation.primary`)

Оба места делают явную ставку на то, что «аниме первым» — сквозное свойство
витрины, а не свойство одного блока. `factory/lords/render.py:2927-2928`
(фасет и `active_types`) это свойство держит; `_context()`/`build_plan()`
(шапка) — нет. Пользователь, кликающий по шапке, не видит то же самое
решение, что заявлено профилем и подтверждено на соседней странице того же
сайта.

## Ожидаемый результат

Один резолвер порядка пунктов меню на весь Lords, консультирующийся с тем же
`type_priority`, которым уже пользуется `ct.active_types()` — а не второй,
независимый проход по `blueprint.yaml::sections`. Конкретная реализация —
решение владельца `factory/lords/**`: например, `build_plan()` может
сортировать раздел-страницы контентных типов по `profile["layout"]
["type_priority"]` перед добавлением в `plan.pages`, оставляя служебные
разделы (`genres_index`, `years_index`, `countries_index`, `search`,
`schedule`, `new_index`, `collections_index`) на текущих местах — либо через
отдельный явный маппинг `navigation.primary → рендер` пакета. Оба варианта
требуют правки `factory/lords/plan.py` и/или `factory/lords/render.py` и,
следовательно, теста уровня движка (`tests/unit/test_lords_type_priority.py`
или новый), а не правки одного профиля: `blueprints/lords/blueprint.yaml`
и `factory/lords/*.py` используются `lords-general`, `lords-new`,
`lords-curated`, `lords-genre`, `zona-cinema` и `animedia-portal` одинаково.

## Что НЕ предлагается

Не предлагается автоматически включать `navigation.primary` без решения
владельца движка: `navigation.primary` пакета и `layout.type_priority`
профиля — два разных поля с потенциально разными значениями у разных
пакетов одного профиля, и выбор, какое из них ведущее для шапки, — решение
уровня Lords writer, не Animedia-сессии.

## Затронутые профили

Поскольку `blueprints/lords/blueprint.yaml::sections` и
`factory/lords/plan.py::build_plan()` общие, тот же дефект воспроизводится и
на `zona-cinema` (второй профиль, где `layout.type_priority` объявлен не как
`content_types.py` по умолчанию — не проверялось этой сессией, вне области).
