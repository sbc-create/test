# Шаблоны: как добавить шаблон

> **Что в этом файле.** Только раздел «как добавить шаблон» и описание
> шаблонного контракта. Описательная часть — как устроен рендер Lords, как
> устроен Yummy, что стоит над обоими, — написана в ветке
> `claude/sprint06-docs`, коммит `c478b8b`, в файле с тем же именем. Здесь она
> не повторяется: при слиянии этот текст встаёт отдельным разделом в конец того
> файла, а не заменяет его.

> **Как читать ссылки.** `файл:строка` — по `/srv/site-factory/repo`, ветка
> `claude/sprint06-templates`.

---

## Что такое шаблон и чем он не является

Шаблон направления Lords — это **манифест**: один YAML в
`blueprints/lords/profiles/`. Он решает четыре вещи и больше ничего:

| Что решает шаблон | Ключ манифеста | Кто читает |
|---|---|---|
| какие разделы витрина индексирует | `owns`, `owns_title_page` | `factory/lords/plan.py:144 owners()`, `:238` |
| из чего собрана главная | `layout.home_blocks` | `factory/lords/render.py:846 _home()` |
| как это выглядит | `theme.tokens`, `layout` | `factory/lords/theme.py:76 stylesheet()` |
| что написано на страницах | `sections`, `title_page` | `factory/lords/plan.py:249-252` |

Шаблон **не** владеет источником данных, Content API, плеером, аналитикой,
пагинацией и приёмкой: они одинаковы у всех витрин направления и живут в
`factory/lords/`. Новый шаблон ничего из этого не копирует.

Второе семейство, Yummy, манифеста не имеет: его витрины — TypeScript-модули
(`src/site-profiles/profiles.ts`, `src/site-blueprint/yami.ts`), собираемые в
образ. Контракт это признаёт прямо: `family` в схеме принимает единственное
значение `lords`. Общее у двух семейств — токены оформления, три ширины
(390/768/1440) и правило «пустой раздел со статусом 200 запрещён»; общего
шаблонного слоя нет, и делать вид, что он есть, было бы неправдой.

## Контракт

| Часть контракта | Где | Исполняется |
|---|---|---|
| форма манифеста | `schemas/template-manifest.schema.json` | JSON Schema Draft 2020-12, `additionalProperties: false` |
| реестр блоков главной | `factory/templates/contract.py` `BLOCKS` | сверяется с рендерером разбором AST |
| смысловые правила | `factory/templates/contract.py` `validate_manifest()` | `python3 -m factory template-check` |
| правила между шаблонами | `validate_repository()` | один владелец на раздел, один владелец страниц произведений |
| fixture-данные | `factory/templates/fixture.py` `contract_catalog()` | каталог, на котором каждый блок может появиться |
| проверка в браузере | `tests/e2e-templates/`, `playwright.templates.config.js` | 390, 768 и 1440 px |

**Перечень блоков не выдуман, а вычитан из кода.** `renderer_blocks()`
разбирает `factory/lords/render.py` и возвращает блоки, у которых есть ветка в
`_home()`. Поэтому шаблон, объявивший блок, которого рендерер не рисует,
отвергается — а раньше такой блок молча пропадал: у цепочки `elif` нет ветки
`else`. Так в направлении и жили `hero_timeline` (`lords-new`) и
`hero_editorial` (`lords-curated`) — объявленные и не рисуемые ничем.

Тринадцать блоков: `hero_search`, `hero_facets`, `top_carousel`, `latest_grid`,
`type_rows`, `top_rated`, `genre_chips`, `year_grid`, `country_grid`,
`calendar`, `fresh_episodes`, `collection_cards`, `editor_note`.

**Обязательное в составе главной — одно правило, и оно не про красоту.**
Приёмка боевого обновления ищет на главной `class="card` и страницу больше 4000
байт (`automation/host/lords-content-refresh.sh:233`); не найдя, возвращает
прежний релиз. Шаблон без блока с карточками не пройдёт эту приёмку никогда, и
контракт отвергает его заранее.

**Порядок блоков первого экрана задан структурой, а не списком.** `hero_search`
и `hero_facets` рисуются внутри первого экрана, до цикла по `home_blocks`
(`render.py:846 _home()`), поэтому в манифесте они обязаны стоять первыми.
Иначе манифест обещает расстановку, которой на странице не будет: у
`lords-general` карусель была объявлена выше поиска, а на странице поиск всё
равно шёл первым.

**Флаг, выключающий блок, — тоже отказ.** `calendar` без `show_calendar` и
`collection_cards` без `show_collection_cards` не рисуются и не сообщают об
этом (`render.py:921`, `:930`). Контракт требует, чтобы объявленное было
включено.

## Как добавить шаблон

1. **Заготовка манифеста.**
   ```bash
   python3 -m factory template-new --example lords-<имя> > /tmp/lords-<имя>.yaml
   ```
2. **Заполнить.** Обязательны `purpose` (зачем витрина отличается от соседних),
   `owns` (разделы во владении — они не должны пересекаться с чужими),
   `theme.tokens`, `layout`, тексты `sections` для `home`, `search` и каждого
   раздела во владении. Тема указывается по имени из `blueprint.yaml: themes`;
   новая тема добавляется в этот список scaffold'ом.
3. **Проверить манифест до записи.**
   ```bash
   python3 -m factory template-check --manifest /tmp/lords-<имя>.yaml
   ```
4. **Посмотреть в браузере — до того, как шаблон куда-либо записан.**
   ```bash
   .venv/bin/python tests/tools/template_stand.py --manifest /tmp/lords-<имя>.yaml
   # шаблоны направления и новый: порты 8811 и далее
   ```
   Стенд поднимает **шаблоны**, а не сайты: пакета в `sites/`, домена, счётчика
   и решения об индексации для этого не требуется.
5. **Создать.**
   ```bash
   python3 -m factory template-new --manifest /tmp/lords-<имя>.yaml --dry-run
   python3 -m factory template-new --manifest /tmp/lords-<имя>.yaml
   ```
   Меняются ровно три файла: сам шаблон в `blueprints/lords/profiles/`,
   `blueprints/lords/blueprint.yaml` (списки `profiles` и `themes`) и
   `schemas/site-package.schema.json` (перечисления `tenant.seo_profile` и
   `tenant.theme`). Последнее — не формальность: без записи в перечисление
   пакет сайта не проходит собственную схему, и именно это раньше делало
   «добавить шаблон одним файлом» невозможным.
6. **Прогнать проверки.**
   ```bash
   .venv/bin/python -m pytest tests/unit/test_template_contract.py -q
   npx playwright test --config=playwright.templates.config.js
   ```
7. **Сайт — отдельное решение.** Scaffold не создаёт `sites/<id>/package.yaml`:
   домен, права на контент, счётчик и индексация — решения владельца, а не
   следствие появления шаблона. Пакет заводится обычным путём, в нём
   указывается `tenant.seo_profile: lords-<имя>`.

## Если шаблону нужен блок, которого нет

Scaffold в этом случае отказывает, и это правильный отказ: обещать блок,
которого никто не рисует, хуже, чем не иметь шаблона. Порядок такой:

1. ветка в `factory/lords/render.py` `_home()` — блок обязан помечать свой
   корневой тег через `_mark(block, html)`, иначе его нельзя проверить снаружи;
2. правила оформления в `factory/lords/theme.py`, если блоку нужна своя вёрстка;
3. запись в `BLOCKS` (`factory/templates/contract.py`) и в перечисление
   `home_block` схемы манифеста;
4. `pytest tests/unit/test_template_contract.py` — три источника (код, реестр,
   схема) обязаны совпасть, и тест падает, если совпали не все три.

Если блок трогает SEO-поверхность (title, description, canonical, robots,
sitemap, разметку пагинации, JSON-LD, внутренние ссылки), сначала правится
`knowledge/SEO_INDEXABILITY_MATRIX.yaml` с поднятием `policy_version`, и только
потом код: матрица — вход рендера, а не отчёт.

## Что проверяется и чем

| Проверка | Команда | Что доказывает |
|---|---|---|
| контракт шаблонов | `python3 -m factory template-check` | манифесты валидны, владение не пересекается, реестр блоков совпадает с рендерером |
| контракт в тестах | `pytest tests/unit/test_template_contract.py -q` | то же плюс scaffold, fixture-каталог и разметка блоков |
| схемы репозитория | `pytest tests/test_schemas.py -q` | схема манифеста легальна, валидная фикстура проходит, невалидная отвергается |
| блоки в браузере | `npx playwright test --config=playwright.templates.config.js` | каждый объявленный блок виден на 390, 768 и 1440 px, порядок совпадает с манифестом, колонок столько, сколько обещано, горизонтальной прокрутки нет |
| витрины направления | `npx playwright test --config=playwright.lords.config.js` | четыре сайта с пакетами — прежняя приёмка, она не заменяется |

## Адаптивные правила, общие для шаблонов

Три ширины проверки — 390, 768, 1440 — не выбраны, а взяты из системы: их же
объявляют пакеты сайтов (`sites/lords-01/package.yaml`
`acceptance.accessibility.viewports`) и манифест Yummy
(`src/site-blueprint/yami.ts` `design.breakpoints`). Медиазапросы Lords
переключаются на 640px и 1024px (`factory/lords/theme.py`), поэтому эти три
ширины попадают ровно в три разные ветки и одна за другую не отвечает.

Из этого следуют два правила, которые контракт проверяет сам:

* `layout.columns` обязан расти с шириной — убывающий ряд означает, что на
  широком экране карточек меньше, чем на узком;
* горизонтальной прокрутки нет ни на одной из трёх ширин.

Остальные требования к вёрстке (клавиатура, фокус, контраст, один `h1`,
настоящие `<a href>`) остаются в `.claude/rules/frontend.md` и контрактом не
дублируются.

## Что контракт нашёл в работающем направлении

Первый же прогон на неправленом коде (коммит `0512b10`) дал четыре расхождения,
и все четыре — настоящие:

| Шаблон | Что нашлось | Как исправлено |
|---|---|---|
| `lords-new` | объявлен блок `hero_timeline`, которого рендерер не рисует | убран из `home_blocks`; первый экран задаёт `hero: timeline` |
| `lords-curated` | то же с `hero_editorial` | убран; первый экран задаёт `hero: editorial` |
| `lords-genre` | на главной нет ни одного блока с карточками — приёмка боевого обновления вернула бы прежний релиз на каждом обновлении каталога | добавлен `latest_grid` под плашками |
| `lords-general` | `top_carousel` объявлен выше `hero_search`, а рисуется ниже | `hero_search` переставлен первым; разметка не менялась |

Воспроизвести отказ на неправленом коде:

```bash
mkdir -p /tmp/orig/blueprints/lords/profiles /tmp/orig/schemas
git show 0512b10:blueprints/lords/blueprint.yaml > /tmp/orig/blueprints/lords/blueprint.yaml
for f in lords-general lords-new lords-curated lords-genre; do
  git show 0512b10:blueprints/lords/profiles/$f.yaml > /tmp/orig/blueprints/lords/profiles/$f.yaml
done
cp schemas/template-manifest.schema.json /tmp/orig/schemas/
ln -s "$PWD/factory" /tmp/orig/factory
.venv/bin/python -c 'from pathlib import Path
from factory.templates import contract
for p in contract.validate_repository(Path("/tmp/orig")): print("-", p)'
```

## Что контракт сегодня не описывает

* **Yummy.** Манифестной формы у витрин Yummy нет; `homepageEmphasis` в
  `src/site-profiles/profiles.ts:70,131,192` объявлен и не читается ни одним
  потребителем — полки главной прибиты в JSX `src/app/(portal)/page.tsx`.
  Контракт это фиксирует, но не чинит: это чужое дерево и чужой цикл выката.
* **Декоративные поля.** `blueprint.yaml` → `profiles`, `ownership_rule`,
  `detail_routes` не читает ни один модуль Python; `theme.name` не влияет на
  CSS (стили строят токены); `editorial_rules` в `lords-curated` не читает
  никто. Контракт описывает их как есть и помечает как инертные — но не удаляет.
* **Порог «главная больше 4000 байт»** проверяется на fixture-каталоге, а не на
  живом: живой каталог в проверку не ходит и ходить не должен.
