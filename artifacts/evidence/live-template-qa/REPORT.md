# Live Template QA — закрытые витрины

**Дата:** 2026-09-18T22:00Z–22:07Z  
**Метод:** серверный HTTP (urllib/curl-эквивалент), структурный разбор HTML, Playwright Chromium screenshots  
**Мутации:** нет (DNS / noindex / access / nginx-домены / код не менялись)

## Домены

| Ключ | URL | family / design | source_commit | runtime_commit | profile |
|---|---|---|---|---|---|
| Lords | https://lordserial33.biz/ | lords / `lords-sheet` | `99ec7829…` | `99ec7829…` | lords-new |
| Animedia | https://animedia.space/ | animedia / `animedia-portal` | `b023bd50…` | `99ec7829…` | animedia-general |
| Animedia | https://animedia.icu/ | animedia / `animedia-portal` | `b023bd50…` | `99ec7829…` | animedia-general |
| Zona | https://zonafilm.space/ | zona / `zona-top` | `a10e68b2…` | `99ec7829…` | zona-general |

## Референсы (только из inventory)

Источник: `inventory/reference-sources.yaml`.

| Семейство | ref | URL | Пакет | Доступ в этой сессии |
|---|---|---|---|---|
| Animedia | `amd-online` | https://amd.online/ | `docs/reference-packs/amd-online`, `config/reference-packs/reference-pack.amd-online.json` | HTTP 200 (probe) |
| Zona | `zona-w140` | https://w140.zona.plus/ | `docs/reference-packs/zona-w140`, `config/reference-packs/reference-pack.zona-w140.json` | HTTP 200 (probe) |
| Lords | — | — | нет записи в inventory | `no_reference_in_inventory` |

Политика пакетов: `PAGE_MAP.md` / `ACCEPTANCE.md` прямо говорят, что состав маршрутов снят с нашей структуры, а не с референса; визуальное соответствие **нельзя объявлять**, пока `measurement_plan` не отработал и токены не заполнены. Здесь — структурное сравнение и live-поведение витрин, без объявления pixel-parity.

## Артефакты прогона

| Путь | Содержание |
|---|---|
| `qa-summary.json` | сводка checks/findings (сырой автопрогон; см. корректировку ниже) |
| `checks.json` | 154 автопроверки |
| `raw/*.json` | дампы по доменам |
| `raw/structure-metrics.json` | счётчики a/img/h2 vs референсы |
| `html/*` | HTML-срезы home/catalog/title/search |
| `screenshots/*` | Playwright PNG 1440 / 390 |

> Автопрогон изначально пометил 12×P0 из‑за **некодированных** кириллических `?kind=` в urllib (браузеры кодируют сами → 200). Ниже — **скорректированный** реестр дефектов после ручной перепроверки и скриншотов с `networkidle`.

---

## Сводка проверок (скорректированная)

| Метрика | Значение |
|---|---|
| Автопроверок (raw) | 154 |
| Успешных после коррекции ложных сбоев kind-URL | ~146 |
| Подтверждённых дефектов | см. таблицу ниже |
| **P0** | **0** |
| **P1** | **2** |
| **P2** | **4** |
| **P3** | **5** |
| Ложные срабатывания автопрогона | 12 (некодированный `kind=Фильм` и т.п.) |

---

## Матрица маршрутов (все домены)

| Раздел | Lords | Animedia.space | Animedia.icu | Zona | Комментарий |
|---|---|---|---|---|---|
| `/` home | 200 | 200 | 200 | 200 | OK |
| `/catalog/` | 200 | 200 | 200 | 200 | пагинация `?page=2` OK |
| `/title/{slug}/` | 200 + player | 200 + player | 200 + player | 200 + player | iframe/player-зона есть |
| `/collections/` | 200 | 200 | 200 | 200 | OK |
| `/collection/*` (Animedia CTA) | — | 200×4 | 200×4 | — | new_episodes / recently_added / top_rated / video_available |
| `/search/?q=` | 200 | 200 | 200 | 200 | см. P1 латиница |
| `/genres/`, `/countries/` | 404 | 404 | 404 | 404 | **не в навигации**; фасеты через query (см. P3) |
| `/catalog/?genre=` (Zona) | — | — | — | 200×14 | OK |
| `/catalog/?year=` (Lords) | 200 | — | — | — | OK |
| `/catalog/?kind=` (urlencoded) | 200 | 200 (пусто для Фильм — ожидаемо) | 200 | 200 | OK |
| `/new/`, `/schedule/` | 200 / 308→ | 200 / 200 | 200 / 200 | 200 / 308→ | OK |
| `/robots.txt` | Disallow: / | Disallow: / | Disallow: / | Disallow: / | OK |
| `X-Robots-Tag` | noindex, nofollow | noindex, nofollow | noindex, nofollow | noindex, nofollow | OK |
| meta robots | noindex, nofollow | noindex, nofollow | noindex, nofollow | noindex, nofollow | OK |
| indexing-policy | closed | closed | closed | closed | OK |
| Basic Auth | нет (уже снята) | нет | нет | нет | закрытие = noindex, не пароль |
| 500/502 на проверенных URL | нет | нет | нет | нет | OK |

Поиск (все семейства, выборочно):

| Запрос | Lords | Animedia | Zona |
|---|---|---|---|
| обычный / кириллица (`матрица` / `наруто` / `ван пис`) | hit | hit | hit (по каталогу) |
| частичный (`мат`) | 200 | 200 | 200 |
| пустой `q=` | 200 | 200 | 200 |
| несуществующий | честное «нет» | честное «нет» | честное «нет» |
| латиница (`matrix` / `naruto` / `avatar`) | 0 hits | 0 hits | (аналогично по смыслу) | **P1** |

---

## Дефекты (подтверждённые)

### P1-01 — Поиск не находит латиницу при наличии кириллических карточек

| Поле | Значение |
|---|---|
| Домен | https://animedia.space/ (то же на .icu); также https://lordserial33.biz/ |
| URL | `/search/?q=naruto` → «Совпадений нет»; `/search/?q=наруто` → 2 title |
| Раздел | поиск |
| Шаг | ввести `naruto` / `matrix` / `avatar` латиницей |
| Факт | пустой результат, хотя slug/карточки есть (`/title/naruto-posledniy-film/`, «матрица» находит 8) |
| Ожидание | поиск по slug/алиасам/транслиту или подсказка |
| Severity | **P1** |
| Владелец | `automation/host/lords-frontend.py` (поиск по снимку) |
| Доказательство | `html/animedia_space__search_naruto_latin.html` |

### P1-02 — Animedia: прямые CDN-постеры без `/poster/` proxy (в отличие от Lords)

| Поле | Значение |
|---|---|
| Домен | https://animedia.space/, https://animedia.icu/ |
| URL | главная / каталог |
| Раздел | постеры |
| Шаг | сравнить `<img src>` с Lords |
| Факт | Animedia/Zona → `https://poster.cdnvideohub.com/...`; Lords → `/poster/...` (локальный proxy, 200). На Animedia `/poster/...` отвечает **308**. В быстром screenshot без ожидания виден flash «постер не открылся» (lazy + fallback в разметке). После `networkidle` видимые постеры загружаются. |
| Ожидание | единый proxy `/poster/` на всех семействах (как у Lords) для стабильности и CSP |
| Severity | **P1** (риск деградации/блокировок CDN; UX flash) |
| Владелец | `automation/host/lords-frontend.py` + nginx `yummyani-poster-cache` / lords poster map |
| Доказательство | screenshots `animedia-space-home-1440.png` (ранний) vs `animedia-space-home-1440-wait.png` (после wait); HEAD `/poster/` 308 на animedia/zona, 200 на lords |

### P2-01 — Lords: пустые оценки на карточках главной («КП — IMDb —»)

| Поле | Значение |
|---|---|
| Домен | https://lordserial33.biz/ |
| URL | `/` |
| Раздел | карточки / рейтинги |
| Шаг | открыть главную |
| Факт | на видимых карточках рейтинги отображаются прочерками |
| Ожидание | числа КП/IMDb, когда есть в снимке; иначе не рисовать пустую шкалу |
| Severity | **P2** |
| Владелец | `automation/host/lords-frontend.py` (карточка lords-sheet) |
| Доказательство | `screenshots/lords-home-1440.png` |

### P2-02 — Некодированные кириллические query в `href`

| Поле | Значение |
|---|---|
| Домен | lordserial33.biz, zonafilm.space |
| URL | `/catalog/?kind=Фильм` (в HTML буквально) |
| Раздел | навигация / фильтры |
| Шаг | разобрать HTML; запросить URL без percent-encoding |
| Факт | urllib/некоторые клиенты получают сбой; браузер кодирует → 200 |
| Ожидание | `kind=%D0%A4%D0%B8%D0%BB%D1%8C%D0%BC` в разметке |
| Severity | **P2** |
| Владелец | `automation/host/lords-frontend.py` |
| Доказательство | сырой HTML home; автопрогон `checks.json` nav_link status=None |

### P2-03 — Animedia vs amd.online: плотность и состав главной

| Поле | Значение |
|---|---|
| Домен | https://animedia.space/ vs https://amd.online/ |
| URL | `/` |
| Раздел | главная / IA |
| Шаг | сравнить structure-metrics |
| Факт | live: 107 `<a>`, 96 `<img>`, 6 полок (2 честно пустые). Ref: 333 `<a>`, 180 `<img>`, другие заголовки («Новые серии аниме», …), 3 формы (логин+поиск). Шапка live: `position:relative`, красный акцент `#c50725`, placeholder «Название аниме». |
| Ожидание | по ACCEPTANCE — нельзя заявлять визуальный match без measurement_plan; разрыв плотности/IA зафиксирован как долг |
| Severity | **P2** (продуктовый разрыв с эталоном, не runtime-авария) |
| Владелец | templates Animedia / `docs/reference-packs/amd-online` |
| Доказательство | `raw/structure-metrics.json`, screenshots |

### P2-04 — Zona «Новые трейлеры» всегда пустая полка

| Поле | Значение |
|---|---|
| Домен | https://zonafilm.space/ |
| URL | `/` |
| Раздел | главная / полки |
| Шаг | открыть главную |
| Факт | честное `zempty`: «Трейлеры источником не передаются…» |
| Ожидание | либо скрыть полку (как цель empty-shelf gate), либо иметь данные |
| Severity | **P2** |
| Владелец | `automation/host/lords-frontend.py` (zona shelves) |
| Доказательство | HTML home snippet в прогоне |

### P3-01 — Нет отдельных `/genres/` и `/countries/`

Навигация на них не ссылается. Фасеты: Lords `?year=`, Zona `?genre=`, Animedia `?kind=Аниме`.  
**Severity P3** (ожидание «страница жанров» из чеклиста ≠ фактическая IA).  
Владелец: docs / IA, не hotfix.

### P3-02 — Animedia честные пустые «Онгоинги» / «Сегодня выйдет»

Сообщения объясняют отсутствие полей источника. Это **не** 500 и не ложные карточки. Относительно amd.online (где блок «Сегодня выйдет» заполнен) — data gap.  
**Severity P3** (или accepted debt).  
Доказательство: screenshot wait + HTML `zempty`.

### P3-03 — `alt=""` у постеров на всех семействах

**Severity P3** a11y. Владелец: lords-frontend.

### P3-04 — Пагинация `/catalog/page/3/` → 404

Рабочий путь: `?page=3`. UI ссылается на query.  
**Severity P3**.

### P3-05 — Zona vs w140.zona.plus: тёмная тема live vs светлый эталон-пакет

Live `zona-top` тёмный; пакет `zona-w140` описывает светлый лист 1.1.0 как legacy. Разные design epochs.  
**Severity P3** (документированный dual-design), не регрессия закрытого стенда.

---

## Что работает хорошо

1. **Закрытость:** noindex header+meta, `robots.txt` Disallow:/, indexing-policy closed — на всех четырёх.
2. **Семейства не смешаны:** `lords-sheet` / `animedia-portal` / `zona-top`; animedia.icu ≡ animedia.space по design/build.
3. **Каталог, title, player-зона, collections** — 200, без 502.
4. **Zona жанровые чипы** (14) и **Lords year facets** — живые.
5. **Animedia collection CTA** (`/collection/...`) — 200, ~60 titles.
6. **Честные empty-states** (онгоинги/сегодня/трейлеры) — не выдумывают данные.
7. **Provenance Zona** после фикса: source `a10e68b2`, runtime `99ec7829`.

---

## Сравнение семейств и референсов

### Lords ↔ Animedia ↔ Zona

| Аспект | Lords | Animedia | Zona |
|---|---|---|---|
| Тема | светлая, зелёный акцент | светлая, красный `#c50725` | тёмная, синий акцент |
| Шапка | sticky-like sheet nav | `position:relative` (static) | top bar + pill active |
| Поиск placeholder | «Введите название» | «Название аниме» | «Название фильма или сериала» |
| Постеры | `/poster/` proxy | прямой CDN | прямой CDN |
| Полки главной | grid «Новинки» без h2-списка | 6 секций h2 | 5 секций h2 |
| Оценки на карточках | часто «—» | КП/IMDb числа | IMDb числа |

### Animedia ↔ amd.online (особое внимание)

| | animedia.space | amd.online (ref) |
|---|---|---|
| `<a>` | 107 | 333 |
| `<img>` | 96 | 180 |
| формы | 1 (поиск) | 3 (логин+пароль+поиск) |
| h2 | Онгоинги, Новые эпизоды, Сегодня выйдет, Новые аниме, Топ, С видео | Новые серии аниме, Сегодня выйдет, Новые аниме на сайте |
| Шапка | logo+5 пунктов+поиск | плотнее, иной chrome |
| Онгоинги / Сегодня | честный empty | на референсе блоки заполнены |

Вывод: live Animedia — **узнаваемый** portal (красный акцент, светлый лист, аниме-навигация), но **не** измеренный паритет с amd.online (пакет сам запрещает заявлять match). Главные UX-риски: латиница в поиске, proxy постеров, пустые data-dependent полки.

### Zona ↔ w140.zona.plus

Live тёмный `zona-top` с жанровыми чипами и полками; ref probe 200, ~93 ссылки, мало `<img>` в первом HTML (вероятно lazy/JS). Пакет `zona-w140` — черновик без заполненных токенов. Объявлять visual match нельзя.

### Lords

Отдельного UI-референса в inventory нет. Live стабилен по маршрутам; слабые места — пустые рейтинги на карточках и латинский поиск.

---

## Приоритет исправлений

1. **P1-01** — поиск: транслит / slug / латиница (Animedia + Lords).  
2. **P1-02** — включить `/poster/` proxy для Animedia (и ideally Zona) как у Lords.  
3. **P2-01** — не показывать пустые «КП — IMDb —» на Lords.  
4. **P2-02** — percent-encode `kind`/`genre` в `href`.  
5. **P2-03 / P2-04** — продуктовые: measurement_plan Animedia; скрыть полку трейлеров Zona без данных.  
6. **P3** — a11y alt, IA docs для genres/countries, dual-design Zona.

---

## Итоговая таблица

| | |
|---|---|
| Всего автопроверок | 154 |
| Ложные P0 (kind URL encoding) | 12 |
| Подтверждённые P0 | **0** |
| Подтверждённые P1 | **2** |
| Подтверждённые P2 | **4** |
| Подтверждённые P3 | **5** |
| Отличие от оригинала | Animedia заметно реже/проще amd.online; пустые data-полки; нет login-форм (ожидаемо для закрытой витрины); Zona тёмная vs светлый legacy-пакет; Lords без внешнего UI-ref |
| Делать первыми | поиск латиница → poster proxy Animedia → пустые рейтинги Lords → encode query |

`DEPLOY_PERFORMED` в этой задаче: **нет** (только исследование).  
`DNS_MUTATIONS=0` · `PAID_OPERATIONS=0` · `PRODUCTION_MUTATIONS=0`
