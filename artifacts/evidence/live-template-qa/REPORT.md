# Live Template QA — закрытые витрины (полный прогон)

**Дата:** 2026-09-18T22:00Z–22:20Z
**Метод:** серверный HTTP (urllib), структурный разбор HTML, Playwright Chromium (screenshots + CSS metrics + scroll-check постеров)
**Мутации:** нет (`DNS_MUTATIONS=0`, `PRODUCTION_MUTATIONS=0`, код/nginx/noindex/access не менялись)
**Provenance Zona (подтверждено live):** `source_commit=a10e68b2350a020a2f7d5efe28cd98ef2fc89edd`, `runtime_commit=99ec78291141de9f350f03298edabd6e89b3a9d6`, `profile=zona-general`

## Домены

| Ключ | URL | template_family / design | source_commit | runtime_commit | profile | build_id |
|---|---|---|---|---|---|---|
| Lords | https://lordserial33.biz/ | lords / `lords-sheet` | `99ec7829…` | — (поле отсутствует) | lords-new | `20260918T215044Z-99ec7829-nova` |
| Animedia | https://animedia.space/ | animedia / `animedia-portal` | `b023bd50…` | — | animedia-general | `20260918T215044Z-b023bd50-nova` |
| Animedia | https://animedia.icu/ | animedia / `animedia-portal` | `b023bd50…` | — | animedia-general | `20260918T215044Z-b023bd50-nova` |
| Zona | https://zonafilm.space/ | zona / `zona-top` | `a10e68b2…` | `99ec7829…` | zona-general | `20260918T215756Z-a10e68b2-nova` |

Источник provenance: `GET /__template_version` на каждом домене → `raw/*_deep.json`.

## Референсы (только из inventory)

Источник: `inventory/reference-sources.yaml` (allowed_paths: `/` only).

| Семейство | ref | URL | Пакет | Live probe |
|---|---|---|---|---|
| Animedia | `amd-online` | https://amd.online/ | `docs/reference-packs/amd-online`, `config/reference-packs/reference-pack.amd-online.json` | HTTP 200 |
| Zona | `zona-w140` | https://w140.zona.plus/ | `docs/reference-packs/zona-w140`, `config/reference-packs/reference-pack.zona-w140.json` | HTTP 200 |
| Lords | — | — | нет записи в inventory | `no_reference_in_inventory` |

Политика пакетов (`PAGE_MAP.md` / `ACCEPTANCE.md`): состав маршрутов снят с **нашей** структуры; визуальный match **нельзя объявлять** без отработанного `measurement_plan`. Ниже — структурное и поведенческое сравнение, не pixel-parity.

## Артефакты

| Путь | Содержание |
|---|---|
| `checks.json` / `checks-deep.json` | автопроверки (базовый + расширенный прогон) |
| `qa-summary.json` / `raw/deep-summary.json` | сводки |
| `raw/*_deep.json` | дампы по доменам (home/catalog/title/search/nav/images/manifest) |
| `raw/refs_home.json` | метрики home референсов |
| `raw/playwright-metrics.json` | CSS/DOM метрики после `networkidle` |
| `html/*` | HTML-срезы |
| `screenshots/*` | PNG 1440 / 390 (+ search/catalog/title/refs) |

---

## Сводка дефектов

| Severity | Кол-во | ID |
|---|---|---|
| **P0** | **0** | — |
| **P1** | **2** | P1-01, P1-02 |
| **P2** | **4** | P2-01 … P2-04 |
| **P3** | **6** | P3-01 … P3-06 |
| Ложные срабатывания | — | некодированный `kind=` в сыром urllib; lazy-img `naturalWidth=0` до scroll (Animedia 68→0 после прокрутки) |

Расширенный автопрогон: **170** checks, **164** ok после коррекции ложных кодировок/lazy.

---

## Матрица маршрутов

| Раздел | Lords | Animedia.space | Animedia.icu | Zona |
|---|---|---|---|---|
| `/` home | 200 | 200 | 200 | 200 |
| `/catalog/` + `?page=2` + sort | 200 | 200 | 200 | 200 |
| `/catalog/?kind=` (urlencoded) | 200 | 200 | 200 | 200 |
| `/catalog/?year=` / `?genre=` | year 200 | — | — | genre 200×14 |
| `/collections/` | 200 (facet hub) | 200 | 200 | 200 |
| `/collection/{slug}/` | нет в IA | 200×5 (~60 titles) | 200×5 | 200×6 |
| `/title/{slug}/` + `[data-player]` | 200 playable | 200 playable | 200 playable | 200 playable |
| `/search/?q=` | 200 | 200 | 200 | 200 |
| `/new/` | 200 | 200 | 200 | 200 |
| `/schedule/` | 308 | 200 (дни недели) | 200 | 308 |
| `/genres/`, `/countries/` | 404 | 404 | 404 | 404 |
| `/catalog/page/2\|3/` | 404 | 404 | 404 | 404 |
| `/robots.txt` | `Disallow: /` | `Disallow: /` | `Disallow: /` | `Disallow: /` |
| `X-Robots-Tag` | noindex, nofollow | noindex, nofollow | noindex, nofollow | noindex, nofollow |
| meta robots | noindex, nofollow | noindex, nofollow | noindex, nofollow | noindex, nofollow |
| 500/502 на проверенных URL | нет | нет | нет | нет |
| Basic Auth | нет | нет | нет | нет |
| Битые внутренние ссылки (≤40, encoded) | 0 | 0 | 0 | 0 |
| Битые постеры (HEAD sample / после scroll) | 0 | 0 | 0 | 0 |

### Поиск

| Запрос | Lords | Animedia | Zona |
|---|---|---|---|
| точное кириллица (`матрица` / `наруто` / `аватар`) | 8 hits | 2 hits | 17 hits |
| частичный (`мат` / `нару` / `ават`) | 200, много | 200 | 200 |
| латиница (`matrix` / `naruto` / `avatar`) | **0** | **0** | **0** |
| смешанный (`naruto наруто`) | **0** | **0** | **0** |
| пустой `q=` | 200, пусто | 200 | 200 |
| несуществующий | честное «нет» | честное «нет» | честное «нет» |
| очистка / mobile search UI | форма на home 390px есть | форма есть, header↑128px | форма есть |

---

## Проверки по чеклисту

### 1. Главная

| Аспект | Lords | Animedia | Zona |
|---|---|---|---|
| Шапка | `.hd`, height 63, `position:static`, белая | `.zhd`, height 92, `position:relative`, border-bottom `#c50725` | `.zhd`, height 69, **`position:fixed`**, bg `#546778` |
| Логотип | «Lordserial» 19px/800 | «Animedia» 22px/800, цвет `#c50725` | «Zona» 19px/700, белый |
| Навигация | Новинки · Фильмы · Сериалы · Мультфильмы · Каталог | Главная · Каталог аниме · Новые эпизоды · Расписание · Подборки | Обзор · Что нового · Кино · Сериалы · Анимация · Весь каталог + жанровые чипы |
| Мобильная (390) | nav+search умещаются | header 128px, nav сохранена | fixed header + search |
| Hero / верх | lead h1, tabs «Новинки» | h1 портала + 6 секций | h1 + genre strip + 5 полок |
| Полки / карусели | grid карточек | `.zrl` карусели; 2× `zempty` | `.zrl`; 1× `zempty` (трейлеры) |
| Футер | служебные ссылки | служебные | служебные |

Доказательства: `screenshots/*-home-*.png`, `raw/playwright-metrics.json`.

### 2. Каталог

- Заголовки: Lords «Каталог: 52793 записей»; Animedia/Zona «Весь каталог».
- Карточки с постерами, годом, типом; ссылки `/title/…` 200.
- Пагинация через `?page=`; path-style `/catalog/page/N/` → 404 (P3).
- Сортировка `sort=year|rating|title` → 200.
- Фильтры: Lords year facets; Zona genre chips; kind-фильтры на всех.

### 3. Поиск

См. таблицу выше. Критичный разрыв — латиница/смешанный запрос (P1-01). Дубликатов title-href в выдаче кириллицы не замечено.

### 4. Разделы

Все ссылки основной навигации (encoded) → 200.
Animedia/Zona: живые `/collection/*`. Lords: `/collections/` как facet-каталог (year/kind), без `/collection/{slug}/` — иная IA, не 500.

### 5. Страница тайтла

| Поле | Lords `007-doroga-k-millionu` | Animedia `009-1` / `naruto-posledniy-film` | Zona `007-doroga-k-millionu` |
|---|---|---|---|
| h1 / URL | OK | OK | OK |
| постер | `/poster/…` 200 | прямой CDN 200 | прямой CDN 200 |
| описание | **пустое** («источник пока не передал») на этом slug | есть/зависит от записи | есть/зависит |
| год / страна / жанры | OK | OK | OK |
| КП / IMDb | блок оценок есть | есть | IMDb; КП в HTML не найден на этом slug |
| серии | «2 сезон(ов), 16 серий» | OK | OK |
| player | `[data-player] data-state="playable"` + `video-player` | то же | то же |
| похожие | есть | есть | есть |
| «0 минут» | нет | нет | нет |

Доказательства: `html/*__title*.html`, `screenshots/*-title*.png`.

### 6. Технические

- HTTP 200 на основных маршрутах; 404 только на ожидаемых IA-пробелах и path-pagination.
- noindex header+meta+robots — все 4 домена.
- Закрытый доступ = indexing closed (Basic Auth снят) — сохранено.
- Manifest/profile соответствуют рендеру (`data-design`, семейства не смешаны; animedia.icu ≡ animedia.space).
- Zona provenance после фикса корректна (source ≠ runtime).

### 7. Сравнение с референсами

См. разделы ниже «Что уже соответствует» / «Что особенно далеко».

---

## Дефекты (подтверждённые)

### P1-01 — Поиск не находит латиницу / смешанный запрос

| Поле | Значение |
|---|---|
| Домен | lordserial33.biz, animedia.space, animedia.icu, zonafilm.space |
| URL | напр. `https://animedia.space/search/?q=naruto` → 0; `…?q=наруто` → 2; `…?q=naruto%20наруто` → 0 |
| Раздел | поиск |
| Шаг | ввести латиницу или смесь при наличии кириллической карточки / slug |
| Факт | 0 title-hits |
| Ожидание | поиск по slug / транслиту / алиасам или осмысленная подсказка |
| Severity | **P1** |
| Владелец | `automation/host/lords-frontend.py` (search over snapshot) |
| Доказательство | HTTP 200 + HTML `html/*__search_lat.html`; screenshots `*-search-lat.png` / `*-search-cyr.png` |

### P1-02 — Animedia/Zona: нет рабочего `/poster/` proxy (в отличие от Lords)

| Поле | Значение |
|---|---|
| Домен | animedia.space, animedia.icu, zonafilm.space |
| URL | img → `https://poster.cdnvideohub.com/…`; probe `/poster/test` → **308**, `/poster/` → **404**. Lords `/poster/…` → **200** |
| Раздел | постеры |
| Шаг | сравнить `src` карточек; HEAD proxy; screenshot до/после wait/scroll |
| Факт | прямой CDN; до загрузки в DOM виден fallback «постер не открылся»; после scroll все 96 Animedia img `naturalWidth>0`, HEAD CDN 25/25 = 200 |
| Ожидание | единый `/poster/` proxy на всех семействах |
| Severity | **P1** (риск CDN/CSP + UX flash) |
| Владелец | `automation/host/lords-frontend.py` + nginx poster map |
| Доказательство | `raw/*_deep.json` poster_probe/images; screenshots `animedia-space-home-1440-wait.png`, `animedia-space-home-scrolled.png` |

### P2-01 — Lords: пустые «КП — / IMDb —» на карточках главной

| Поле | Значение |
|---|---|
| Домен | https://lordserial33.biz/ |
| URL | `/` |
| Раздел | карточки / рейтинги |
| Шаг | открыть главную |
| Факт | Playwright: `kpDashes=42` на видимых карточках |
| Ожидание | числа при наличии в снимке; иначе не рисовать пустую шкалу |
| Severity | **P2** |
| Владелец | lords-sheet card renderer |
| Доказательство | `screenshots/lords-home-1440.png`, `playwright-metrics.json` |

### P2-02 — Некодированные кириллические query в `href`

| Поле | Значение |
|---|---|
| Домен | lordserial33.biz (6), zonafilm.space (7) |
| URL | литерал `/catalog/?kind=Фильм` в HTML |
| Раздел | навигация / фильтры |
| Шаг | разобрать HTML; запросить без percent-encoding |
| Факт | браузер кодирует → 200; не-браузерные клиенты могут ломаться |
| Ожидание | `kind=%D0%A4%D0%B8%D0%BB%D1%8C%D0%BC` в разметке |
| Severity | **P2** |
| Владелец | `automation/host/lords-frontend.py` |
| Доказательство | `raw/lords_deep.json` / `zona_deep.json` → `nav.unencoded_cyrillic_hrefs` |

### P2-03 — Animedia vs amd.online: плотность, IA, chrome

| Поле | Значение |
|---|---|
| Домен | https://animedia.space/ vs https://amd.online/ |
| URL | `/` |
| Раздел | главная / IA / визуал |
| Шаг | structure + Playwright metrics |
| Факт | live ≈107 `<a>` / 96 `<img>` / 1 форма; ref ≈328 `<a>` / 179 `<img>` / 3 формы (логин+поиск). Live nav: 5 пунктов; ref: Premium/AMDейлик/мегаменю жанров. Шрифт live system-ui; ref Circe. Акцент live `#c50725`. Шапка live `relative` (не sticky) — у ref тоже `relative`. |
| Ожидание | measurement_plan + токены; не silent “готово как оригинал” |
| Severity | **P2** |
| Владелец | Animedia templates / `docs/reference-packs/amd-online` |
| Доказательство | `raw/refs_home.json`, `playwright-metrics.json`, screenshots `animedia-space-home-*` vs `amd-online-home.png` |

### P2-04 — Zona: полка «Новые трейлеры» всегда empty

| Поле | Значение |
|---|---|
| Домен | https://zonafilm.space/ |
| URL | `/` |
| Раздел | главная / полки |
| Шаг | открыть главную |
| Факт | честный `zempty`: трейлеры источником не передаются |
| Ожидание | скрыть полку без данных **или** иметь данные |
| Severity | **P2** |
| Владелец | zona shelves in lords-frontend |
| Доказательство | HTML home + `playwright-metrics.json` emptyShelves |

### P3-01 — Нет `/genres/` и `/countries/` как отдельных страниц

404 на всех доменах; в основной навигации ссылок нет. Фасеты через query.
**Severity P3.** Доказательство: route matrix.

### P3-02 — Animedia: честные empty «Онгоинги» / «Сегодня выйдет»

Data gap относительно amd.online (там блоки заполнены). Не 500.
**Severity P3.**

### P3-03 — `alt=""` у постеров

На всех семействах. **P3** a11y.

### P3-04 — Path-pagination `/catalog/page/N/` → 404

UI использует `?page=`. **P3**.

### P3-05 — Lords: пустой plot на части title pages

Пример: `/title/007-doroga-k-millionu/` — «Описание… источник пока не передал». Честный empty, но UX-дыра. **P3**.

### P3-06 — `runtime_commit` только у Zona

Lords/Animedia отдают `source_commit` без `runtime_commit` в `/__template_version`. После provenance-фикса это ожидаемо асимметрично; для аудита единообразия — долг документации/API. **P3**.

---

## Что уже соответствует оригиналу

1. **Закрытость стенда:** `X-Robots-Tag` + meta noindex + `robots.txt Disallow: /` на всех четырёх доменах.
2. **Семейства не смешаны:** `lords-sheet` / `animedia-portal` / `zona-top`; animedia.icu ≡ animedia.space по design/build/source.
3. **Zona ↔ w140.zona.plus (структурно близко):** тёмная тема `rgb(30,37,43)`, fixed header `rgb(84,103,120)` height 69, те же заголовки полок («Популярные новинки фильмов», «Популярные сериалы», «Добавленные недавно фильмы», «Новые серии», «Новые трейлеры»), genre/kind навигация узнаваема. Provenance source=`a10e68b2`, runtime=`99ec7829` корректны.
4. **Animedia ↔ amd.online (узнаваемость):** светлый лист, красный акцент, секции «Сегодня выйдет» / «Новые аниме*», карточки с рейтингами, поиск в шапке, portal-IA без login на закрытом стенде — ожидаемо.
5. **Каталог / title / player-зона / collections:** 200, player `data-state="playable"`, без 502; внутренние ссылки (encoded sample) без 4xx.
6. **Честные empty-states** вместо выдуманных данных (онгоинги, сегодня, трейлеры, plot).
7. **Постеры после догрузки:** CDN/proxy отдают 200; «битые» в Playwright до scroll — lazy, не 404.

## Что особенно далеко от оригинала

1. **Animedia vs amd.online:** плотность (~3× меньше ссылок), нет login/social chrome, нет жанрового мегаменю, шрифт не Circe, другие названия/набор полок («Онгоинги» vs заполненные блоки ref), две пустые data-полки, placeholder «Название аниме» vs «Поиск аниме».
2. **Поиск латиница** на всех витринах — функциональный разрыв с ожиданиями пользователя (slug часто латиницей).
3. **Poster pipeline:** только Lords на `/poster/`; Animedia/Zona на прямом CDN.
4. **Lords:** нет UI-референса в inventory; пустые рейтинги на карточках; collections = facet hub, не curated `/collection/*`.
5. **Zona package dual-design:** live `zona-top` тёмный совпадает с live w140; светлый legacy в `docs/reference-packs/zona-w140` — не целевой epoch для этого стенда (не регрессия, но путаница в docs).

## Следующий цикл исправлений

1. **P1-01** — поиск: транслит / slug / latin aliases (+ mixed query) для всех семейств.
2. **P1-02** — включить `/poster/` proxy для Animedia и Zona по образцу Lords.
3. **P2-01** — не рендерить пустые КП/IMDb на Lords-карточках.
4. **P2-02** — percent-encode `kind`/`genre` в `href`.
5. **P2-04** — скрыть полку «Новые трейлеры» без данных.
6. **P2-03** — Animedia: measurement_plan против amd.online (nav order, typography Circe/tokens, shelf set, header density) — без заявления match до измерений.
7. **P3** — alt-тексты; docs IA genres/countries; единообразие `runtime_commit` в manifest; path-pagination или явный отказ в docs.

---

## Итоговая таблица по доменам

| Домен | HTTP/noindex | Profile / commits | Критичные находки | Вердикт стенда |
|---|---|---|---|---|
| lordserial33.biz | OK / closed | lords-new · source `99ec7829` | P1 search latin; P2 empty ratings; P2 unencoded kind | **GO for closed QA**, fix search/ratings next |
| animedia.space | OK / closed | animedia-general · source `b023bd50` | P1 search latin; P1 no poster proxy; P2 density vs amd.online; P3 empty shelves | **GO closed**, furthest from amd.online IA |
| animedia.icu | OK / closed | ≡ space | те же, что space | **GO closed**, parity with .space |
| zonafilm.space | OK / closed | zona-general · source `a10e68b2` · runtime `99ec7829` | P1 search latin; P1 no poster proxy; P2 empty trailers; P2 unencoded kind | **GO closed**, closest structural match to w140 |

| Метрика | Значение |
|---|---|
| Всего автопроверок (deep) | 170 |
| Подтверждённые P0 / P1 / P2 / P3 | **0 / 2 / 4 / 6** |
| Делать первыми | latin/slug search → poster proxy Animedia/Zona → Lords empty ratings → encode query → hide Zona trailers shelf |

`DEPLOY_PERFORMED` в этой задаче: **нет** (только аудит и отчёт).


## Deep pass

**Дата:** 2026-09-18T22:20Z–22:30Z
**Метод:** BFS same-origin crawl (nav/footer/home/catalog/title/collections/search/filters/pagination + robots.txt + sitemap.xml), повторная проверка известных дефектов, Playwright desktop/mobile screenshots
**Лимит:** до 100 HTTP-страниц на домен (очередь discovery больше)
**Мутации:** нет
**Артефакты:** `raw/*_crawl.json`, `raw/deep-pass-summary.json`, `raw/deep-pass-title-probe.json`, `raw/refs_deep.json`, `screenshots/deep-pass/*.png` (40 шт.)

> Предыдущие разделы отчёта сохранены. Ниже — второй проход и уточнения severity.

### Discovery / crawl coverage

| Домен | Discovered URLs | Visited | HTTP hist | Unexpected ≥400 | Unencoded cyrillic hrefs | Poster HEAD ok/bad |
|---|---|---|---|---|---|---|
| lordserial33.biz | 1341 | 100 | 200×93, 308×2, 404×5 | **0** | 59 | 15/0 |
| animedia.space | 2789 | 100 | 200×93, 308×1, 404×6 | **0** | 7 | 15/0 |
| animedia.icu | 2789 | 100 | 200×93, 308×1, 404×6 | **0** | 7 | 15/0 |
| zonafilm.space | 1398 | 100 | 200×93, 308×2, 404×5 | **0** | 64 | 15/0 |

Ожидаемые 404 в hist: `/genres/`, `/countries/`, `/catalog/page/N/`, probe `no_such`, Animedia `/poster/`, `/sitemap.xml` (Animedia). 308 — редиректы schedule/poster.

Источники discovery: основная навигация, футер, все `<a>` home, каталог, карточки, title (до 8 шт.), подборки, query filters/pagination, `robots.txt`, `sitemap.xml` (+ child locs где есть).

### Checklist deep-pass (все домены)

| # | Проверка | Lords | Animedia.space | Animedia.icu | Zona |
|---|---|---|---|---|---|
| 1 | Home | 200 | 200 | 200 | 200 |
| 2 | Все пункты основной nav | 200 | 200 | 200 | 200 |
| 3 | Каталог kind Фильм/Сериал/Аниме/… | 200 | 200 | 200 | 200 |
| 4 | Фильтры year/genre | year 200 | kind query | kind query | genre chips 200 |
| 5 | Сортировка | 200 | 200 | 200 | 200 |
| 6 | Пагинация `?page=` | 200 | 200 | 200 | 200 |
| 7 | Поиск RU / Latin | RU hit / Lat **0** | RU hit / Lat **0** | RU hit / Lat **0** | RU hit / Lat **0** |
| 8 | Поиск по slug | **0** (`007-doroga-k-millionu`) | **0** (`naruto-posledniy-film`) | **0** | **0** |
| 9 | Частичный | hit | hit | hit | hit |
| 10–11 | Пустой / несуществующий | честный empty | честный | честный | честный |
| 12–13 | `/genres/` `/countries/` | 404 | 404 | 404 | 404 |
| 14 | Подборки | `/collections/` facet hub 200 | `/collection/*` 200 | 200 | `/collection/*` 200 |
| 15–18 | Title / серии / player / похожие | player playable; plot empty на sample; similar ok | playable; plot ok; similar зависит от slug | ≡ | playable; similar ok |
| 19 | Постеры + lazy | `/poster/` 200; broken 0 | CDN 200; lazy ok after scroll | ≡ | CDN 200 |
| 20 | Рейтинги КП/IMDb | карточки **«—»**; title IMDb badge | числа на карточках; title IMDb | ≡ | IMDb на карточках |
| 21 | Даты / серии | ok | ok | ok | ok |
| 22 | Ссылки КП / IMDb / Смотреть | **нет outbound** kinopoisk/imdb URL; badges + «Смотреть…» текст/player | то же | ≡ | то же |
| 23 | Unknown route 404 | 404 | 404 | 404 | 404 |
| 24 | robots / meta / X-Robots-Tag | Disallow:/ + noindex | Disallow:/ + noindex | Disallow:/ + noindex | Disallow:/ + noindex |
| 25 | Закрытый доступ | closed indexing | closed | closed | closed |

### Повтор известных дефектов

| Дефект | Результат deep-pass |
|---|---|
| `naruto` / `matrix` Latin | подтверждён 0 hits на всех 4 доменах |
| Кириллица тех же тайтлов | hit (наруто 2 / матрица 8 / аватар 17) |
| Поиск по slug | **новый акцент:** 0 hits при живом `/title/{slug}/` → усиливает P1-01 |
| Animedia `/poster/` | `/poster/` 404, `/poster/test` 308; CDN sample 200 |
| Lords пустые «КП —» | home `dash_count=42` КП, `37` IMDb |
| percent-encode `kind` | Lords 59 / Zona 64 raw cyrillic hrefs; raw UTF-8 request-line не проходит ASCII HTTP client |
| Битые изображения | 0 в HEAD sample; lazy false-positive снят scroll-check |
| Пустые карточки | не обнаружены |
| Пустые секции без honest empty | не обнаружены (Animedia Онгоинги/Сегодня + Zona Трейлеры — `zempty`) |

### Sitemap на закрытых стендах (новый P3)

| Домен | `/sitemap.xml` | Child | X-Robots-Tag на sitemap |
|---|---|---|---|
| lordserial33.biz | 200 → 2 child | sitemap-1.xml **45000** URL | noindex, nofollow |
| zonafilm.space | 200 → 2 child | 45000 URL | noindex, nofollow |
| animedia.space / .icu | **404** | — | noindex на 404 |

Не индексируется (header+robots), но URL-инвентарь торчит наружу — гигиена closed-стенда.

### Animedia ↔ amd.online (deep)

| Аспект | animedia.space | amd.online |
|---|---|---|
| `<a>` / `<img>` home | ~107 / 96 | ~334 / 182 |
| Nav order | Главная → Каталог аниме → Новые эпизоды → Расписание → Подборки | Premium / AMDейлик / Жанр mega-menu + auth |
| Шапка | `.zhd` relative, height 92, border `#c50725` | `.header` relative, height 90, logo 225×90 |
| Карточки | `.zt` ~352×484 (desktop) | `.poster` ~163×256 |
| Постеры | CDN direct | (ref own CDN/paths) |
| Поиск | 1 form, placeholder «Название аниме»; latin/slug fail | «Поиск аниме» + login forms |
| Фильтры | kind/collections; нет жанрового дерева как у ref | `/anime/ghanr/…` дерево |
| Типографика | system-ui / Segoe UI | Circe |
| Пустые состояния | Онгоинги, Сегодня выйдет — honest | блоки заполнены |
| Mobile 390 | header 128px, nav сохранена | плотнее chrome |
| Title | player playable, IMDb badge, plot обычно есть | (не crawl’или beyond / per inventory) |

Screenshots: `screenshots/deep-pass/animedia-space-*` vs `amd-online-home-1440.png` / `390`.

### Zona ↔ w140.zona.plus + reference-pack

Inventory URL `https://w140.zona.plus/` подтверждён. Live structural match сильнее, чем у Animedia:

- те же h2 полок; fixed header ~69px `#546778`; тёмный bg `#1e252b`;
- live «Новые трейлеры» = honest empty; на ref полка присутствует (JS-heavy, 1 img в первом HTML);
- pack `docs/reference-packs/zona-w140` — маршруты нашей структуры; visual tokens не заполнены → match не объявляем.

Screenshots: `screenshots/deep-pass/zona-*` vs `zona-ref-home-*.png`.

---

### Deep-pass defects (новые и подтверждённые)

#### DP-P1-01 — Поиск: латиница, mixed и slug → 0 hits

| Поле | Значение |
|---|---|
| Домен | все 4 |
| URL | `/search/?q=naruto\|matrix\|avatar`; `/search/?q={slug}`; mixed `naruto наруто` |
| Раздел | поиск |
| Шаг | ввести латиницу / slug страницы тайтла / смесь |
| Факт | 0 title-hits; кириллические эквиваленты находят |
| Ожидание | slug + translit + latin aliases |
| Severity | **P1** (подтверждение/расширение P1-01) |
| Файл | `automation/host/lords-frontend.py` |
| Evidence | `raw/*_crawl.json` → search; `screenshots/deep-pass/*-search-lat-1440.png` |

#### DP-P1-02 — Animedia/Zona без `/poster/` proxy

| Поле | Значение |
|---|---|
| Домен | animedia.space, animedia.icu, zonafilm.space |
| URL | `/poster/` → 404; `/poster/test` → 308; img → `poster.cdnvideohub.com` 200 |
| Раздел | постеры |
| Шаг | сравнить с Lords `/poster/{id}.webp` → 200 |
| Факт | proxy отсутствует; CDN жив; lazy OK после scroll |
| Ожидание | единый proxy |
| Severity | **P1** (= P1-02) |
| Файл | lords-frontend + nginx poster map |
| Evidence | `raw/deep-pass-summary.json` poster_proxy; screenshots deep-pass home |

#### DP-P2-01 — Lords: пустые КП/IMDb на карточках

| Поле | Значение |
|---|---|
| Домен | lordserial33.biz |
| URL | `/` и similar-блоки title |
| Раздел | карточки / рейтинги |
| Шаг | открыть home |
| Факт | 42× «КП —», 37× «IMDb —»; это текст внутри card `<a>`, не отдельные outbound «КП →» |
| Ожидание | числа или скрыть блок |
| Severity | **P2** (= P2-01) |
| Файл | lords-sheet card renderer |
| Evidence | `raw/deep-pass-title-probe.json` lords_home_ratings; `screenshots/deep-pass/lords-home-1440.png` |

#### DP-P2-02 — Unencoded cyrillic в href (`kind=`)

| Поле | Значение |
|---|---|
| Домен | lordserial33.biz (59), zonafilm.space (64); Animedia 7 |
| URL | `/catalog/?kind=Фильм` литералом в HTML |
| Раздел | nav / filters |
| Шаг | извлечь href; raw UTF-8 request-line |
| Факт | браузер ок; non-browser ASCII client → encode error |
| Ожидание | percent-encoding в разметке |
| Severity | **P2** (= P2-02) |
| Файл | `automation/host/lords-frontend.py` |
| Evidence | crawl `unencoded_sample`; `raw_kind_urls` errors |

#### DP-P2-03 / DP-P2-04 — Animedia density vs amd; Zona empty trailers

Без изменений vs первый проход. Evidence: deep-pass screenshots + refs.

#### DP-P3-07 — Sitemap с десятками тысяч URL на closed Lords/Zona

| Поле | Значение |
|---|---|
| Домен | lordserial33.biz, zonafilm.space |
| URL | `/sitemap.xml` → child `sitemap-1.xml` (45000 `<loc>`) |
| Раздел | tech / closed hygiene |
| Шаг | GET sitemap; проверить X-Robots-Tag |
| Факт | 200 + noindex header; URL inventory публично читается. Animedia — 404 (расхождение семейств) |
| Ожидание | для closed-стенда — не отдавать полный sitemap **или** явное documented exception |
| Severity | **P3** |
| Файл | nginx/sitemap generator / deploy nova closed policy |
| Evidence | `raw/deep-pass-title-probe.json` → sitemap |

#### DP-P3-08 — Нет outbound ссылок на kinopoisk.ru / imdb.com

| Поле | Значение |
|---|---|
| Домен | все 4 (title pages) |
| URL | title samples |
| Раздел | title / рейтинги |
| Шаг | искать `href` на kinopoisk/imdb |
| Факт | только UI-badges `data-source=imdb` (иногда kp); «Смотреть» = player section, не внешняя ссылка |
| Ожидание | если продукт требует внешние «КП»/«IMDb» — добавить; иначе задокументировать badge-only |
| Severity | **P3** (уточнение чеклиста, не авария) |
| Файл | title template / product IA |
| Evidence | `html/*title*`; title-probe kp/imdb href lists empty for external |

---

### Deep-pass: обновлённая сводка severity

| Severity | Было (pass 1) | Deep-pass | Итого уникальных |
|---|---|---|---|
| P0 | 0 | +0 | **0** |
| P1 | 2 | подтверждены + slug в P1-01 | **2** |
| P2 | 4 | подтверждены | **4** |
| P3 | 6 | +2 (sitemap, outbound ratings) | **8** |

### Deep-pass: что не сломано

- 0 unexpected broken same-origin links на 400 visited pages.
- 0 битых постеров в samples; lazy-load корректен.
- noindex/robots/closed сохранены на HTML и sitemap responses.
- Player `data-state="playable"` на title samples всех семейств.
- animedia.icu ≡ animedia.space по поведению crawl/search/proxy.
- Zona provenance и structural близость к w140 подтверждены скриншотами.

### Приоритет после deep-pass (без изменений кода здесь)

1. P1 search latin+slug+mixed
2. P1 poster proxy Animedia/Zona
3. P2 Lords empty ratings
4. P2 percent-encode href
5. P2 hide Zona trailers / Animedia measurement_plan
6. P3 sitemap hygiene on closed + docs outbound ratings
