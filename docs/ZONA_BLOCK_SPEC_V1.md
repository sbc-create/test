ZONA_BLOCK_SPEC_V1

Блочное техническое задание и acceptance contract для Zona

Сайт: zonafilm.space, профиль zona-01.
Стадия на входе: PASS_CONTRACT_NEEDS_TWO_WEEKLY_CYCLES.
Текущий live build: 20260920T092117Z-dbaf9a4d-nova.
Текущий weekly commit: f11df9b.
Текущий режим Popular: WEEKLY_SNAPSHOT.
Задача документа: довести структуру, геометрию, данные, состояния и пользовательские маршруты Zona блок за блоком, а не одним большим изменением.

Главное правило: ни один блок не принимается по словам «выглядит хорошо», по самостоятельно назначенному score или только по green unit tests. Для закрытия нужны:

зафиксированный reference baseline;

паспорт блока и доказанное происхождение данных;

BEFORE;

AFTER_LOCAL;

измеримый DOM/geometry oracle;

отдельный commit;

AFTER_LIVE только после отдельного exact owner deploy approval; без него — immutable artifact и READY_FOR_OWNER_DEPLOY;

отсутствие регрессий маршрутов, плеера, индексации и соседних доменов.

1. Что зафиксировано на live до нового прохода

Проверено на zonafilm.space при viewport 1363×936:

Объект

Фактическое состояние

Document

примерно 1348×3576 px на главной

Header

69 px

Main container

1300 px, x=24 px

Footer

примерно 330 px

Home title card

примерно 180×379 px

Home poster

примерно 178×267 px, 2:3

Title poster

240×360 px

Title player shell

1200×675 px, 16:9 на проверенном маршруте

Catalog total

53 548

Previous frozen catalog report

53 524; delta +24 requires provenance, neither number may be hard-coded

Catalog page size

28

Catalog page count

1 913 for current 53 548

Catalog year facets

92 года

Catalog 2019

2 144 записи

Catalog 2019 page count

77

/new/ total

1 218 записей

/new/ 2019

7 записей только в выборке /new/, не во всём каталоге

Collections

12 зарегистрированных подборок

Current indexability observation

noindex,nofollow; confirm in B00 and preserve exact owner state

Фактическая главная сейчас содержит пять почти одинаковых тяжёлых poster rails:

высокий рейтинг среди недавних фильмов;

высокий рейтинг среди недавних сериалов;

добавленные недавно фильмы;

недавно добавленные сериалы;

высокий рейтинг среди недавней анимации.

После них идут жанры, подборки, SEO/about и footer.

Найденные риски текущей версии

первый экран не имеет сильного пользовательского hero: после header стоит технический H1 и сразу полки;

пять полок одинаковой геометрии делают главную монотонной и слишком длинной;

карточка 180×379 px тяжёлая для объёма метаданных;

freshness и premiere semantics недостаточно явно разделены;

число 7 у 2019 года на /new/ легко принять за полный годовой count, хотя полный catalog count равен 2 144;

текущая подборка показывает title и subtitle почти одинаковыми;

public footer показывает техническую версию и commit/build fragment;

owner contacts/legal всё ещё не заполнены;

recommendations на ширине 1363 могут использовать только четыре карточки по 180 px и оставлять крупную пустую область;

выявлен риск неверных canonical genre links: label и query value должны проверяться независимым oracle;

live alias defect: genre=comedy&year=2019 давал 0, canonical genre=komediya&year=2019 — 616;

/country/velikobritaniya/ на проверенном live возвращал 404: country facet нельзя считать закрытым;

/year/2019/ и query-вариант относятся к одной выдаче, но текущий canonical ведёт на query; две HTTP-200 route families запрещены;

collection detail на ширине 1363 показывал только четыре карточки и оставлял около половины контейнера пустой;

BreadcrumbList на exact episode может содержать технические segments вместо пользовательских названий;

weekly builder ещё не наблюдал два штатных недельных перехода;

proposed timer Mon 04:10 UTC владельцем пока не разрешён.

2. Референс и правило его использования

2.1. Reference target

Базовый внешний пример: zonafilm.ru, если этот URL подтверждён владельцем как требуемый оригинал. Он используется для:

порядка смысловых блоков;

визуальной иерархии;

плотности;

типов карточек;

поведения фильтров;

композиции title page;

структуры footer;

responsive-переходов.

Он не используется для копирования:

текстов;

логотипов и защищённых assets;

пользовательских отзывов;

рейтингов и голосов;

коллекций без собственных данных;

рекламы;

контактов;

ссылок;

аналитики;

функций, для которых у Zona нет backend.

2.2. Обязательный B00 reference freeze

До первой правки исполнитель обязан снять референс сам в своей доступной среде. Если zonafilm.ru недоступен или владелец имел в виду другой URL:

не угадывать;

не выбирать другой сайт самостоятельно;

выставить state=BLOCKED_DEPENDENCY, blocker_owner=reference, blocker_code=REFERENCE_UNAVAILABLE;

указать exact URL/status/error;

запросить один owner value REFERENCE_URL;

не начинать B01–B24 до фиксации reference digest.

Для каждой reference page сохранить:

URL;

captured_at UTC;

browser и version;

viewport и DPR;

full-page screenshot;

screenshots каждого блока;

DOM landmarks;

bounding boxes;

computed typography;

container widths;

gaps;

card dimensions;

responsive behavior;

SHA-256 артефактов.

Минимальные reference routes:

главная;

movies;

series;

animation;

catalog default;

catalog filtered;

year page;

country page;

genre page;

search results;

collections hub;

collection detail;

film title;

one-season series title;

multi-season series title;

exact episode;

valid no-video title;

2.2.1. Приоритет reference и продуктового контракта

У документа два разных слоя, и смешивать их нельзя:

frozen reference управляет presence/order, композицией, geometry, плотностью и responsive-переходами;

этот документ управляет достоверностью данных, безопасностью, доступностью, route semantics и обязательными пользовательскими функциями.

Если reference расходится с продуктовым контрактом, B00 обязан до кода создать immutable REFERENCE_DEVIATION_REGISTRY:

deviation_id
route
block_id
reference_behavior
required_product_behavior
reason
owner
approval_id
acceptance_oracle

Незарегистрированное расхождение является hard failure. Reference не может разрешить выдуманные данные, ложную дату, неверный HTTP status, недоступный control или mutation indexability. Продуктовый контракт не может самовольно переписать geometry/order reference: для этого нужен frozen deviation с owner approval.

2.2.2. Frozen CTA registry

B00 также фиксирует для каждого CTA точный cta_route, query schema, canonical/redirect behavior и fallback при отсутствии destination. Обязательные записи включают Hero CTA, Weekly «Смотреть всё», «Новое в каталоге», Фильмы/Сериалы/Анимацию, «Все жанры», все collection cards, title watch CTA и footer links. Неопределённый CTA скрывается либо блокирует свой блок согласно frozen display policy; исполнитель не придумывает URL.

2.3. Неподвижные tolerances

После B00 расширять допуски запрещено:

Метрика

Максимальное отклонение

Presence/order обязательных блоков

0

Outer container

±8 px

Header/player/card width-height

±4 px

Grid/rail gap и padding

±4 px

Нормализованная vertical position

±12 px

Horizontal overflow

0 px

Overlap

0 px

Unexpected inner scrollbar

0

Missing screenshot/oracle case

0

Динамический контент сравнивается по структуре и geometry, а не по совпадению конкретных названий.

3. Целевая информационная архитектура

3.1. Главная

Shared header.

Hero / главный редакционный акцент.

Weekly popular / weekly ranked block.

Новое в каталоге.

Входы в Фильмы / Сериалы / Анимацию.

Жанры.

Подборки.

Короткий about/SEO.

Footer.

Не выводить подряд пять полноразмерных полок одной формы.

3.2. Каталог и разделы

Breadcrumb при глубоком taxonomy route.

H1.

Краткое описание выборки и точный result count.

Compact filter bar.

Active filter chips.

Sort control.

Grid.

Pagination.

Короткий contextual SEO-text, если он уникален и подтверждён.

Footer.

3.3. Title page

Header.

Breadcrumb.

Title passport / hero.

Description and ratings.

Watch heading and player.

Seasons/episodes для series.

Recommendations.

Footer.

3.4. Exact episode page

Header.

Breadcrumb.

Compact episode identity.

Player сразу после identity.

Prev/next/list navigation.

Episode-specific metadata, только если есть.

Compact parent title context.

Episode list.

Recommendations.

Footer.

3.5. Collections

H1/intro.

Collection cards.

Pagination при необходимости.

Detail: H1, description, count, optional curated note.

Title grid.

Pagination.

Footer.

4. Общие design tokens и responsive

Token

1920

1440

1024

768

390

Container max

1760

1392

984

736

358

Side gutter

32

24

20

16

16

Section gap

48–56

40–48

36–40

28–32

24–28

Grid gap

16–20

16

14–16

12–16

12

Touch target

44

44

44

44

44

Base radius

16–20

14–18

12–16

12–14

10–12

Typography:

Role

Desktop

Tablet

Mobile

H1

36–42 / 44–50

32–36 / 40–44

26–30 / 32–36

H2

26–30 / 32–36

24–28 / 30–34

22–24 / 28–30

Card title

15–17 / 20–23

15–16

14–16

Body

16 / 24–27

16 / 24

15–16 / 22–24

Meta

13–14 / 18–20

13–14

12–13

Общие правила:

одна ширина shell для header/main/footer;

один H1;

poster ratio строго 2:3;

backdrop ratio 16:9 или утверждённый reference ratio;

img имеет width/height или aspect-ratio до загрузки;

object-fit: cover;

optional hidden block занимает 0 px;

explicit empty panel имеет отдельный max-height;

горизонтальный scroll допустим только внутри rail и без visible scrollbar;

body horizontal overflow равен 0;

никакого min-height: 100vh для промежуточных блоков;

DOM, visual и keyboard order совпадают;

focus outline не удаляется;

prefers-reduced-motion поддерживается;

light/dark, если theme есть, не меняют geometry.

5. Контракт достоверности данных

5.1. ProvenanceEnvelope

Каждая публичная дата, rating, count, description, playable flag и ranking position должна ссылаться на versioned envelope:

schema_version
provenance_id
site_id
entity_type
entity_id
fact_semantic
source_code
source_record_id | source_url | artifact_id
source_occurred_at
observed_at
ingested_at
first_seen_at
precision
timezone
mapping_revision
mapping_status = exact | owner_approved
confidence
transformation_revision
rights_status = allowed
checksum
status = verified | quarantined | retracted
supersedes_id
validator_version

Строка «source=...» без проверяемого идентификатора не является provenance.

Обязательность полей зависит от fact_semantic; пустоты нельзя заполнять фиктивными значениями:

Fact class

Обязательные поля

Условные/неприменимые поля

source event/date

source identifier, source_occurred_at, observed_at, precision, timezone, mapping/transform revisions, checksum, status

timezone может быть not_applicable только для date-only с na_reason

description/title/poster

source identifier, observed_at, mapping revision, checksum, status

source_occurred_at/precision/timezone = not_applicable с reason

computed count/facet

artifact/snapshot id, query/filter contract, formula revision, observed_at, checksum, status

occurrence time = snapshot timestamp; не выдумывать source event

rating/ranking

source observation id, observed_at, source period/window, formula revision, mapping revision, checksum, status

голосов/периода нет — это явно absent, не ноль

playable flag

descriptor id/revision, observed_at, title/episode identity, provider state, checksum, status

timeout не превращается в false

Допустимые значения состояния поля различаются и сохраняются end-to-end: absent, null, stale, quarantined, retracted, verified. Frontend не имеет права склеивать их в один false/0/пустую строку.

Запрещено «исправлять» source totals во frontend через неутверждённый recount, dedupe, join, filter или исключение. Если источник и oracle расходятся, фиксируется state=BLOCKED_DEPENDENCY, blocker_owner=core_data, blocker_code=SOURCE_ORACLE_MISMATCH; UI не подгоняет число.

5.2. Временные поля

Семантика

Допустимая подпись

Нельзя заменять

catalog_added_at

Добавлено на сайт

build/deploy/import time

source_premiere_at

Премьера

catalog added

source_release_at

Дата выхода

год title или added

provider_available_at

Стало доступно для просмотра

premiere

episode_released_at

Вышла серия

total episode count

material_updated_at

Обновлено

добавлено

observed_at/ingested_at

audit only

любая публичная дата

mtime/build_at/deployed_at/now

никогда

content date

Если точность date-only, UI не имеет права добавлять выдуманное время.

5.3. Три разные сущности, которые нельзя смешивать

Полный каталог: на baseline наблюдалось 53 548 titles.

Выборка /new/: на baseline наблюдалось 1 218 items по отдельно доказанной policy.

Catalog addition events: отдельный immutable event ledger.

Следствие: baseline 2019=2 144 в полном каталоге и baseline 2019=7 в /new/ могут быть одновременно правильными. UI обязан подписать scope count так, чтобы пользователь не считал 7 полным числом фильмов 2019 года.

5.3.1. Catalog snapshot identity

Ни одно число каталога не зашивается в template как вечная константа.

На входе известны:

frozen report total: 53 524;

current live total: 53 548;

observed delta: +24;

current page size: 28;

current page count: 1 913.

B00 обязан:

записать CATALOG_SNAPSHOT_DIGEST;

объяснить delta через новые source-backed title IDs;

доказать unique ID count;

использовать один snapshot для counts, grid, facets, search и pagination;

не объявлять старый или новый total ошибочным без provenance.

Числа 53548, 1218, 2144, 7, 92, 1913, 77 и 616 являются только наблюдениями конкретного baseline. Они допустимы в acceptance evidence лишь при совпадении CATALOG_SNAPSHOT_DIGEST, /new/ ledger digest и query/formula revision B00. При другом digest oracle пересчитывает значения из source snapshot, публикует drift report и использует вычисленные значения. Несовпадение без объяснённого source delta даёт state=BLOCKED_DEPENDENCY, blocker_owner=core_data, blocker_code=DATA_DRIFT_UNEXPLAINED, а не подгонку UI или hard-code старых чисел.

5.4. Ratings

каждый источник показывается отдельно: КП, IMDb, Shikimori и т. п.;

отсутствующий источник полностью скрывается;

0 не является fallback;

голоса разных источников не суммируются;

число голосов показывается только рядом со своим источником;

sort=rating использует versioned formula и stable tie-breaker;

пользовательский rating отделён от внешних;

stale rating допускается только по утверждённой last-good policy.

5.5. Descriptions

Состояния:

source_available_rendered;

source_available_not_rendered;

true_source_gap;

quarantined;

duplicate_legitimate;

duplicate_unexplained.

Правила:

source_available_not_rendered всегда defect;

true gap нельзя маскировать выдуманным SEO-текстом;

description другого title не используется;

auto-generated copy не публикуется без отдельной editorial policy;

в grid description не обязателен;

на title page true gap получает компактный честный state без большой пустоты.

5.6. Posters и images

source-backed poster preferred;

broken poster заменяется системным placeholder;

placeholder явно не является реальным постером;

нельзя брать изображение другого title;

placeholder сохраняет ratio и не вызывает CLS;

alt равен title;

backdrop fallback строится из собственного poster плюс фон, а не из чужого backdrop.

5.7. Playability

video marker только при проверенном descriptor;

playable title link не гарантирует, что каждая серия playable;

exact episode использует exact episode UUID/descriptor;

unavailable не превращается в false-ready;

provider timeouts не меняют catalog metadata.

6. Weekly Popular: обязательный операционный контракт

Текущая принятая база:

POPULAR_REFRESH_MODE=WEEKLY_SNAPSHOT
POPULAR_REQUEST_TIME_RECOMPUTES=0
POPULAR_MAX_PUBLICATIONS_PER_WEEK=1
POPULAR_MEMBERSHIP_STABLE_WITHIN_WEEK=YES
POPULAR_RANDOM_ROTATION=NO
POPULAR_RECOMPUTE_CADENCE=7d
POPULAR_WEEK_ID=2026-W38
POPULAR_WEEKLY_SNAPSHOT_DIGEST=0d16b8a...

Полки:

pop-films;

pop-series;

pop-anim.

Обязательные правила:

Frontend читает только zona-01-popular-weekly.json.

HTTP request не сканирует 53 548 titles и не пересчитывает ranking.

Snapshot публикуется atomic rename.

Builder защищён flock/lease.

Не более одной обычной публикации на ISO-неделю.

Повторный запуск в ту же неделю idempotent.

Emergency repair может восстановить битый файл без полной ротации membership.

Last-good сохраняется.

При missing current snapshot request-time rebuild запрещён.

В ответах присутствуют X-Popular-Week-Id, X-Popular-Weekly-Digest и ETag.

Cache key включает week_id и digest.

Random shuffle запрещён.

A/B rotation запрещена до отдельного контракта.

Label «Популярное» разрешён только при утверждённом popularity_basis.

Если ranking фактически является rating среди recent pool, честная подпись — «Высокие оценки недели» или утверждённый owner label.

Calendar contract: ISO-8601 week в timezone UTC; смена week_id происходит только на границе ISO-недели UTC.

Frontend сохраняет snapshot membership, порядок, week_id, revision и digest без локальной сортировки, rerank, dedupe, backfill или замены элементов.

Scope этого template-прохода строго read-only относительно weekly pipeline: запрещены manual generate, publish, repair, backfill, timer enable и scheduler mutation. Разрешено только читать и валидировать уже опубликованный snapshot. Если snapshot отсутствует или повреждён, B03 получает state=BLOCKED_DEPENDENCY, blocker_owner=core_data, blocker_code=WEEKLY_SNAPSHOT_UNAVAILABLE; отдельный operational task может выполнить repair только по owner approval.

Операционная метрика различает обычную публикацию и repair:

POPULAR_REGULAR_PUBLICATION_COUNT_PER_ISO_WEEK<=1
POPULAR_REPAIR_PUBLICATION_COUNT=
POPULAR_REPAIR_INCIDENT_ID=
POPULAR_REPAIR_MEMBERSHIP_DIGEST_UNCHANGED=1

Repair не считается штатной weekly публикацией, но требует incident ID, audit evidence и неизменный membership digest. В этом template-проходе оба mutation count должны оставаться 0.

Timer:

proposed cadence: Monday 04:10 UTC;

сейчас OWNER_GATE;

не включать без отдельного owner approval;

после разрешения первый цикл supervised;

второй недельный переход тоже supervised/read-only observed;

cadence закрывается только после двух штатных недельных циклов;

тесты внутри одной недели не заменяют два календарных перехода.

7. Паспорт каждого блока

Перед реализацией каждого блока заполнить:

block_id:
routes:
intent:
ownership: template|core_data|search|player|seo|owner_values|reference
versioned_contract_id:
reference_evidence:
entity_or_event_type:
source_path:
provenance:
eligibility:
sort_key:
tie_breaker:
dedupe_key:
visible_timestamp_semantic:
required_fields:
optional_fields:
freshness_sla:
max_stale:
snapshot_revision:
display_policy_by_state:
  normal:
  empty:
  missing_required:
  missing_optional:
  stale:
  error:
desktop_geometry:
tablet_geometry:
mobile_geometry:
interactions:
cta_route:
seo_contract:
tests:
evidence_paths:
remaining_data_gap:

Все display policies выбираются в B00 и входят в contract digest. После BEFORE нельзя менять hidden на placeholder или grid на rail ради прохождения screenshot.

8. B01 — Shared header, navigation и search entry

Routes: все.
Назначение: постоянная и компактная навигация.

Состав:

logo Zona;

Главная;

Новинки;

Фильмы;

Сериалы;

Анимация;

Подборки;

Каталог;

search;

mobile menu.

Geometry:

Viewport

Высота

Поведение

≥1280

68–72 px

logo, nav, search одной строкой

768–1279

60–64 px

compact nav, search icon/field по reference

≤767

56 px

logo + search button + menu button

Search desktop width: 320–400 px.
Logo width: 110–150 px.
Clickable target: минимум 44×44 px.

Mobile:

drawer/overlay, а не перенос header на несколько строк;

focus trap;

Escape закрывает;

focus возвращается opener;

body scroll locked только пока drawer открыт;

search внутри drawer во всю ширину;

ни одной ссылки вне tab order.

Content rules:

«Главная», а не абстрактный «Обзор», если reference и владелец не требуют обратного;

active route имеет aria-current;

build SHA/version не показываются;

пустой query не отправляется;

query trim/Unicode normalize;

Enter и button эквивалентны.

Gates:

HEADER_HEIGHT_VARIANCE_PX<=4
HEADER_WRAP_COUNT=0
HEADER_OVERLAP_COUNT=0
ACTIVE_NAV_PASS=1
SEARCH_EMPTY_SUBMIT_COUNT=0
MOBILE_DRAWER_FOCUS_PASS=1
PAGE_HORIZONTAL_OVERFLOW_PX=0

9. Главная

B02 — Hero / первый экран

Route: /.
Назначение: визуальный центр и быстрый вход в один доказанный title.

Desktop:

container full-width;

height 340–390 px;

text 42–48%;

image/backdrop 52–58%;

border radius 16–20 px;

H1 максимум 2 строки;

description 2–4 строки;

primary CTA;

optional secondary CTA.

Mobile:

height 300–360 px;

image full-bleed с gradient;

text снизу;

H1 максимум 3 строки;

CTA не выходит за viewport.

Required data:

title_id;

canonical slug;

title;

poster или backdrop;

kind;

year.

Optional:

source description;

source rating;

playable.

Buttons:

«Подробнее» всегда на valid title;

«Смотреть» только playable=true;

нет video descriptor → «Смотреть» отсутствует.

Rotation:

request-time random запрещён;

daily или weekly immutable snapshot;

stable inside period;

last-good fallback;

empty candidate set → hero hidden, компактный H1/intro остаётся.

Gates:

HERO_REQUEST_TIME_RECOMPUTES=0
HERO_MEMBERSHIP_STABLE_WITHIN_PERIOD=1
HERO_CLS_P95<=0.05
HERO_FALSE_PLAY_CTA_COUNT=0
HERO_INVENTED_COPY_COUNT=0

B03 — Weekly popular

Route: /.
Data: weekly contract из раздела 6.

Целевая форма:

один блок;

H2;

tabs Фильмы / Сериалы / Анимация;

link «Смотреть всё» только на cta_route из frozen CTA_ROUTE_REGISTRY B00;

одна активная rail/grid вместо трёх последовательных тяжёлых полок.

Карточки:

Viewport

Видимых карточек

Card width

Poster

1920

10

148–160

148–160 × 222–240

1440

8

148–160

148–160 × 222–240

1024

6

142–150

142–150 × 213–225

768

4

150–164

ratio 2:3

390

2

158–166

ratio 2:3

Card total height ≤320 px.
Gap 12–16 px.

Card content:

poster;

title, clamp 2 lines;

year/country;

kind;

максимум 2 genres;

separately labeled rating;

playable marker only if proven.

Deduplication:

duplicate title_id within tab = 0;

current title irrelevant on home;

duplicate slug/poster checked;

cross-tab overlap allowed only if kind taxonomy legitimately overlaps; иначе 0.

Gates:

POPULAR_REQUEST_TIME_RECOMPUTES=0
POPULAR_MEMBERSHIP_CHANGES_WITHIN_WEEK=0
POPULAR_RANDOM_ROTATION=0
POPULAR_REGULAR_PUBLICATION_COUNT_PER_ISO_WEEK<=1
POPULAR_TEMPLATE_PASS_PUBLICATION_COUNT=0
POPULAR_REPAIR_PUBLICATION_COUNT=0
POPULAR_DUPLICATE_TITLE_IDS=0
POPULAR_CACHE_HEADER_PASS=1
POPULAR_LAST_GOOD_PASS=1
POPULAR_TWO_REAL_WEEKLY_CYCLES_OBSERVED=0|1

Последнее поле остаётся 0 до двух реальных циклов и не маскируется тестом.

B04 — «Новое в каталоге»

Route: /.
Назначение: реальные catalog addition events, а не release year и не общее число серий.

Структура:

H2 «Новое в каталоге»;

tabs Всё / Фильмы / Сериалы / Анимация;

10–12 событий;

desktop 2 columns;

mobile 1 column;

CTA использует только точный canonical route из frozen CTA_ROUTE_REGISTRY B00; выбор между /new/?mode=added и другим адресом после freeze запрещён.

Desktop row:

height 96–104 px;

thumb 60×90;

title до 2 строк;

meta: kind · year · country;

verified catalog_added_at с precision=datetime: «Добавлено DD.MM.YYYY, HH» в timezone из provenance;

verified catalog_added_at с precision=date-only: «Добавлено DD.MM.YYYY» без времени;

rating/playable справа.

Mobile:

thumb 56×84;

row 92–104 px;

rating переносится вниз;

touch target 44 px.

Sort:

catalog_added_at DESC;

title_id ASC.

Запрещено:

использовать year как timestamp;

показывать source premiere как added;

использовать build/deploy/mtime/now;

показывать total episodes как номер добавленной серии;

выдумывать время для date-only.

States:

normal: populated;

fewer than 6 verified events: показывается фактическое число без дублей;

zero: блок hidden, height=0, HOME_CONTENT_GAP фиксируется;

stale: last-good только с telemetry, policy frozen in B00;

error: не заменять weekly/popular.

Gates:

CATALOG_ADDED_EVENTS_RENDERED=
VISIBLE_ADDED_DATES_WITH_VALID_PROVENANCE_EQUALS_TOTAL=1
BUILD_OR_DEPLOY_TIME_USED_AS_CONTENT_TIME=0
DUPLICATE_EVENTS=0
SORT_VIOLATIONS=0
DATE_ONLY_RENDERED_WITH_TIME_COUNT=0
DATETIME_RENDERED_WITH_WRONG_TIMEZONE_COUNT=0
PAGE1_PAGE2_INTERSECTION=0
INVENTED_TIMESTAMPS=0

B05 — Входы в типы контента

Три compact cards:

Фильмы;

Сериалы;

Анимация.

Desktop 3 columns, tablet 3 или 2+1, mobile 1.
Height 150–190 px.

Каждая card:

collage/backdrop из source-backed posters;

title;

короткое системное описание раздела;

full catalog count for kind;

CTA.

Counts:

полный catalog oracle;

не первая страница;

не hard cap;

не /new subset.

B06 — Жанры

H2 «Жанры»;

10–16 жанров;

compact chip/grid;

exact count;

CTA «Все жанры» только на cta_route из frozen CTA_ROUTE_REGISTRY B00.

Chip height 36–40 px.
Gap 8–10 px.

Data:

normalized genre registry;

canonical query/path;

full-scope count;

stable sort policy;

empty genre hidden.

Gates:

GENRE_LABEL_QUERY_MISMATCHES=0
GENRE_COUNT_MISMATCHES=0
GENRE_FOREIGN_ITEMS=0
GENRE_QUERY_LOSSES=0

B07 — Подборки на главной

На главной максимум 8 distinct collections.

Card:

collage 2–4 real posters либо approved graphic;

title;

одна неповторяющая title строка description;

exact count;

whole-card link.

Grid:

1920/1440: 4;

1024/768: 2;

390: 1;

height 140–180 px.

Запрещено:

title=subtitle;

empty collection;

две collections с одинаковым title set;

«Недавно добавленные» как визуальный дубликат B04;

fake counts.

B08 — About/SEO

после пользовательского контента;

max-width 760–860 px;

2–3 коротких абзаца;

mobile collapsible after first paragraph;

16 px, line-height 1.55–1.7.

Можно описывать только существующие:

фильмы/сериалы/анимацию;

каталог;

filters;

поиск;

подборки;

просмотр, если он реально доступен не для всех — без абсолютных обещаний.

Нельзя:

keyword stuffing;

выдумывать «новые серии» без event feed;

заявлять ежедневное обновление без SLA;

копировать один текст на разные домены;

вставлять hidden SEO text.

B08 разрешает менять только видимый about-copy и его presentation. Он не разрешает менять robots.txt, meta robots, X-Robots-Tag, sitemap, canonical host/URL policy, hreflang, schema availability или owner indexability registry. Любое before/after отличие этих объектов — hard gate failure; без отдельного точного owner approval deployment не выполняется, а после уже авторизованной активации запускается scoped rollback в пределах заранее утверждённого change window.

10. B09 — Единый card registry

Все poster cards на home/catalog/search/recommendations используют один data registry и разные presentation profiles.

Required:

title_id
canonical_slug
title
poster_state
kind

Optional:

original_title
year
country
genres
rating_facts
playable
catalog_added_at
source_premiere_at

Profiles:

compact_home;

catalog_grid;

search_result;

recommendation;

collection.

Common behavior:

title clamp 2 lines;

stable caption height;

no last-row stretch;

missing poster placeholder;

missing rating hidden;

source labels preserved;

playable marker source-backed;

broken image fallback;

card link canonical;

keyboard focus visible.

Catalog target columns:

Viewport

Columns

Approx card width

≥1680

8

168–190

1280–1679

7–8

164–184

900–1279

5–6

150–178

600–899

4

140–168

≤599

2

158–174

Do not use a breakpoint at exactly 1440 that makes 1363 show only four cards and a half-empty row. Prefer CSS grid auto-fit/minmax within frozen min/max, then assert actual columns.

Gates:

CARD_HEIGHT_VARIANCE_PX<=4
LAST_ROW_STRETCH_COUNT=0
BROKEN_POSTER_COUNT=0
POSTER_ASPECT_RATIO_VIOLATIONS=0
TITLE_OVERFLOW_COUNT=0
RATING_ZERO_FALLBACK_COUNT=0
UNATTRIBUTED_RATING_COUNT=0
FALSE_PLAYABLE_BADGE_COUNT=0

11. Каталог, Movies, Series, Animation

B10 — Catalog heading and compact filters

Routes:

/catalog/;

/movies/;

/series/;

/animation/;

combined query variants.

Top:

H1;

exact result count;

one-line current scope;

compact filters;

active chips;

reset;

sort.

Desktop filter bar:

one row if possible;

Kind select/chips;

Genre select;

Year select;

Country select;

Sort select;

Apply only if architecture requires;

Reset visible only when active.

Height:

collapsed 52–64 px;

expanded advanced panel max 180–240 px;

mobile accordion, not button wall.

Mobile:

button «Фильтры N»;

sheet/drawer;

fields stacked;

sticky Apply/Reset;

close/escape/focus return.

URL contract:

state serializes to canonical query;

unknown param behavior is validated against the frozen, already approved route policy; этот template-проход его не меняет;

changing one filter preserves others;

reset returns correct base route;

order of query params canonicalized;

canonical/query serialization follows the frozen route registry. Если текущие duplicate URLs, redirects или status codes не соответствуют registry, B10/B12 получают backend/SEO BLOCKED_DEPENDENCY; template не вводит redirect самостоятельно.

B11 — Catalog grid and pagination

Page size fixed and versioned; текущий контракт — 28.
Items stable by sort key and title_id tie-breaker.

Pagination:

previous/next;

current;

nearby pages;

last;

mobile compact;

no huge sequence;

invalid page → real HTTP 404;

empty valid filter → HTTP 200 explicit empty;

page 1 canonical without duplicate page=1.

Gates:

CATALOG_ORACLE_TOTAL=
CATALOG_SNAPSHOT_DIGEST=
CATALOG_TOTAL_PREVIOUS_FROZEN=53524
CATALOG_TOTAL_DELTA_EXPLAINED=1
CATALOG_PAGE_SIZE=28
CATALOG_PAGE_COUNT_EXPECTED=ceil(CATALOG_ORACLE_TOTAL/CATALOG_PAGE_SIZE)
CATALOG_PAGE_COUNT_MATCH_ORACLE=1
CATALOG_RENDERED_COUNT_MATCH=1
PAGINATION_DUPLICATES=0
PAGINATION_MISSING_ITEMS=0
PAGINATION_SORT_VIOLATIONS=0
PAGINATION_QUERY_LOSSES=0
INVALID_PAGE_HTTP_404=1
PAGE1_CANONICAL_PASS=1

B12 — Year/country/genre/type taxonomy

Каждый facet:

H1 с понятным scope;

exact count;

compatible filters;

grid;

pagination;

optional unique explanatory copy;

canonical.

Year:

полный oracle;

baseline observation: 2019 catalog count = 2 144 при frozen digest;

baseline observation: 92 year facets при frozen digest;

никаких [:24] truncation;

редкий год публикуется только при count>0;

foreign year items=0.

year counts, facet count и page count вычисляются oracle из pinned snapshot; baseline 2019 page count при size=28 был 77.

Country:

UI использует только существующий approved canonical destination из frozen route registry;

наблюдавшийся /country/velikobritaniya/=404 — RED dependency evidence, а не разрешение исправлять status/canonical в template;

желаемая legacy Cyrillic → canonical ASCII миграция требует отдельного owner-approved backend/SEO task с точным route set, status matrix и approval ID;

после такой отдельной миграции допускается один 301/308, final 200 и no redirect loop;

label/slug/normalized country mapping one-to-one;

unknown country 404;

query and path variants must not form indexable duplicates по approved route contract.

если approved registry destination не даёт 200, state=BLOCKED_DEPENDENCY, blocker_owner=seo, blocker_code=COUNTRY_ROUTE_CONTRACT_BROKEN; UI не публикует broken link.

Genre:

UI label и query id проверяются независимо;

«драма» не имеет права вести west_content;

«детектив» не имеет права вести action;

genre counts from full catalog.

aliases comedy и комедия должны разрешаться по frozen alias registry; изменение redirect/status policy выполняется только отдельной owner-approved backend/SEO задачей;

baseline intersection для проверенного snapshot: 2019 + komediya = 616; текущее expected значение всегда вычисляется oracle из pinned digest.

Gates:

YEAR_COUNT_MISMATCHES=0
FOREIGN_YEAR_ITEMS=0
COUNTRY_COUNT_MISMATCHES=0
COUNTRY_CANONICAL_DESTINATION_STATUS=200
COUNTRY_REDIRECT_LOOPS=0
GENRE_LABEL_QUERY_MISMATCHES=0
GENRE_ALIAS_COUNT_MISMATCHES=0
COMEDY_2019_CANONICAL_COUNT=
COMEDY_2019_COUNT_MATCH_ORACLE=1
REDUNDANT_TAXONOMY_URLS=0
CANONICAL_MATRIX_PASS=1

COUNTRY_CANONICAL_DESTINATION_STATUS=200 проверяет destination из B00 registry, а не навязывает конкретный path. Любая требуемая 404→200, 200→redirect или canonical mutation остаётся отдельной dependency и не выполняется в presentation-only scope.

12. B13 — /new/ и временные режимы

Нельзя оставлять «Что нового» одной неоднозначной выборкой.

Целевые modes/tabs:

Добавлено на сайт — catalog_added_at;

Премьеры — source_premiere_at;

Стало доступно — provider_available_at;

Новые серии — episode_released_at/provider event, только при реальном feed.

Если конкретного event ledger нет, tab отсутствует, а не заполняется соседней датой.

Каждый mode имеет:

H1;

definition line;

exact count for mode;

filters compatible with mode;

visible timestamp matching sort field;

pagination;

empty/error/stale states.

Current warning:

/new/ total 1 218;

/new/?year=2019 показывает 7;

это не catalog year count;

UI должен явно писать «в этой ленте»/«в выборке нового», иначе вводит в заблуждение.

Future premiere:

допустима только в mode «Премьеры»;

future date получает статус «Ожидается»;

не смешивается с «уже добавлено»;

date/time precision сохраняется.

Gates:

NEW_MODE_COUNT=
NEW_MODE_WITHOUT_LEDGER_COUNT=0
VISIBLE_TIMESTAMP_EQUALS_MODE_SORT_FIELD=1
CATALOG_COUNT_MISLABELED_AS_NEW_COUNT=0
FUTURE_PREMIERE_LABELED_AS_ADDED=0
EPISODE_FALLBACK_TO_TITLE_DATE=0

13. B14 — Search

Routes:

/search/?q=;

canonical page;

pagination;

optional suggestions.

Query handling:

trim;

Unicode normalization;

Cyrillic;

original title;

transliteration;

punctuation/hyphen variants;

case-insensitive;

exact title;

exact original;

prefix/substring only по утверждённому ranker contract.

Result layout:

H1 «Результаты поиска: …»;

exact count;

search field with current query;

compact grid/list;

highlighted match only if safe;

pagination;

no results suggestions.

Ranking:

exact canonical title;

exact original title;

exact normalized alias;

approved transliteration;

other ranker signals.

Template worktree не меняет Search/Ranker semantics. Если ranker contract отсутствует — state=BLOCKED_DEPENDENCY, blocker_owner=search, blocker_code=RANKER_CONTRACT_MISSING; создаётся отдельное ТЗ.

Security:

query escaped;

no reflected HTML;

max query length;

no catastrophic regex;

empty q does not run full-catalog accidental search.

Gates:

EXACT_TITLE_TOP1_PASS=1
EXACT_ORIGINAL_TOP1_PASS=1
TRANSLIT_PASS=1
SEARCH_DUPLICATE_IDS=0
SEARCH_BROKEN_LINKS=0
SEARCH_QUERY_XSS_PASS=1
EMPTY_QUERY_FULL_CATALOG_COUNT=0

14. Title page

B15 — Breadcrumb and title passport

Routes: /title/{slug}/.

Breadcrumb:

film: Zona / Кино / Пользовательское название;

series: Zona / Сериалы / Пользовательское название;

episode: Zona / Сериалы / Название / Сезон N, серия M;

visible breadcrumb и JSON-LD BreadcrumbList совпадают;

технические title, slug, season-1, UUID пользователю не показываются;

каждый промежуточный пункт ведёт на canonical 200.

Desktop geometry:

shell full container;

poster 220–240×330–360;

content remaining width;

gap 24–32;

hero height determined by content, normally 360–440 px;

rating rail top-right or inside metadata, not detached.

Tablet:

poster 180–210×270–315;

metadata 2–3 columns;

no narrow text ribbon.

Mobile:

poster 120–150×180–225 or centered top;

title and core metadata visible before description;

one column;

CTA width auto/full per reference.

Content:

title;

original title;

poster;

year;

kind;

country;

status;

duration for film if proven;

seasons/episodes for series if proven;

genres;

ratings;

playable CTA;

description.

Metadata must be a coherent definition grid, not scattered words.

Series count:

«1 сезон, 3 серии» only if both source-backed;

never infer total from max episode if gaps exist;

unknown count hidden/explicit compact missing state per frozen policy.

B16 — Description and ratings

Description:

desktop 4–6 lines before expand;

mobile 4–8;

expand button only when clamped;

no expand for short text;

true gap compact;

source_available_not_rendered=0.

Ratings:

separate badges/cards by source;

source label required;

votes attached to same source;

0 fallback prohibited;

no decorative large score without source;

precision normalized visually, source raw preserved.

Gates:

DESCRIPTION_SOURCE_AVAILABLE_NOT_RENDERED_COUNT=0
CROSS_TITLE_DESCRIPTION_REUSE_COUNT=0
UNPROVEN_DESCRIPTION_RENDERED_COUNT=0
MISSING_RATING_RENDERED_AS_ZERO=0
CROSS_SOURCE_VOTE_SUMMING=0
UNATTRIBUTED_RATING_COUNT=0
BREADCRUMB_VISIBLE_JSONLD_MATCH=1
BREADCRUMB_TECHNICAL_SEGMENT_COUNT=0

B17 — Watch heading and player

Boundary: B17 consumes and validates an existing versioned player contract; it may change shell/toolbar/status presentation, sizing and lifecycle wiring, but cannot invent or rewrite episode/source selection semantics. B00 records PLAYER_CONTRACT_ID, artifact digest and owner. If it is absent, state=BLOCKED_DEPENDENCY, blocker_owner=player, blocker_code=PLAYER_CONTRACT_MISSING.

Order:

H2 «Смотреть»;

local status;

toolbar/selectors;

media viewport.

Shell:

max practical width 1200–1400 depending reference;

media viewport 16:9;

width 100%;

iframe/video/shadow root fills ≥98% width/height;

toolbar excluded from 16:9 calculation;

black background only inside media viewport;

no fixed provider 640×360;

no global iframe height conflict.

States:

resolving;

ready;

playing;

unavailable;

retryable_error.

Rules:

status «подключение» only during active request;

ready only after provider confirmation;

playing removes loading/error overlay;

unavailable compact, no misleading empty player;

max one instance;

autoplay off;

async provider replacement cannot shrink player;

late previous response cannot replace selected source.

exact route title/season/episode identity is immutable through every async replacement; fallback/default resolution may not overwrite it.

Gates:

PLAYER_WIDTH_FILL_RATIO>=0.98
PLAYER_HEIGHT_FILL_RATIO>=0.98
PLAYER_ASPECT_RATIO_ERROR_PERCENT<=1
PLAYER_INSTANCE_MAX=1
PLAYER_SMALL_RENDER_COUNT=0
AUTOPLAY_COUNT=0
PLAYER_FALSE_READY=0
PLAYER_FALSE_FAILURE=0
PLAYING_AND_ERROR_SIMULTANEOUS=0
ASYNC_REPLACEMENT_FAILURES=0

B18 — Seasons and episodes

visible only for series;

season tabs/select;

episode grid/list;

current selection;

exact route;

playable/unavailable only from descriptor.

Generic title route:

renderer consumes the deterministic selection returned by PLAYER_CONTRACT_ID and verifies its identity;

если versioned policy defines first playable, проверить именно его результат; template не реализует новую policy;

blind episode=1 и max episode запрещены, если они не являются доказанным результатом versioned contract;

source request may occur before click;

playback does not autoplay.

Exact route:

exact season/episode always wins;

missing exact episode → 404;

default selector cannot overwrite;

reload/back/forward stable.

Gates:

GENERIC_SERIES_DEFAULT_SELECTED=1
FIRST_PLAYABLE_SELECTION_PASS=1
EXACT_EPISODE_ROUTE_PASS=1
EXACT_EPISODE_REPLACED_BY_DEFAULT_COUNT=0
PROVIDER_REQUEST_DUPLICATES=0
LATE_RESPONSE_REPLACEMENTS=0
RELOAD_PASS=1
BACK_FORWARD_PASS=1

B19 — Recommendations

H2 «Смотрите также» или reference label.

Rules:

current title excluded;

duplicate title_id=0;

broken links=0;

frozen policy id: playable_preferred_with_explicit_nonplayable_state_v1;

playable candidates rank before non-playable; non-playable допускается только без watch badge/CTA и с обычным переходом на title page;

stable recommendation snapshot;

source/profile recorded;

no duplicate shelf with another name.

Grid:

1920: 8;

1440/1363: 7–8, без half-empty 4-card row;

1024: 5–6;

768: 4;

390: 2.

If <4 items:

use compact row without stretching;

if 0, hidden height=0.

Oracle отдельно считает playable и non-playable candidates. Запрещено помечать non-playable как playable или заполнять ряд нерелевантными карточками ради geometry. Смена на playable_only требует нового frozen policy ID и переснятого baseline.

15. B20 — Exact episode page

Route: /title/{slug}/season-{N}/episode-{M}/.

Target order:

breadcrumb;

compact H1 «Title — N сезон, M серия»;

short context and link back;

player immediately;

prev/list/next;

episode facts if available;

compact parent title;

episode list;

recommendations.

Vertical geometry:

identity to watch heading ≤32 px desktop;

watch heading to player ≤16–24 px;

no empty block >96 px;

no poster hero before player unless reference explicitly requires it.

Episode-specific facts:

official episode title;

episode air date;

duration;

episode description.

Only source-backed. Title description cannot silently become episode description.

Invalid season/episode:

real 404;

no default substitution;

no soft 404;

no provider request.

Structured data Episode/VideoObject only when required real fields exist.

16. Collections

B21 — Hub

Route: /collections/.

Top:

H1;

one short explanation;

optional category/tabs if there are enough distinct groups;

exact total.

Card:

distinct visual;

collage/cover;

title;

non-duplicate subtitle;

exact count;

stable canonical route.

Grid:

1920/1440: 4;

1024/768: 2–3;

390: 1.

B21.1 — Detail

Route: /collection/{slug}/.

breadcrumb;

H1;

source/editorial description;

exact title count;

updated date only if meaningful/proven;

catalog grid;

pagination;

optional related collections, deduped.

Geometry detail grid:

≥1600: 8 columns;

1280–1599: 7 columns;

768–1279: 4 columns;

≤599: 2 columns;

empty rail width = 0;

last row never stretches.

Текущий live-дефект «4 карточки при 1363 и пустая правая половина» фиксируется отдельным RED-test.

Rules:

unknown slug 404;

empty collection does not publish/index unless owner policy says explicit empty;

duplicate title set classified;

dynamic collection policy versioned;

recently added collection uses catalog event ledger;

top rated collection uses rating formula;

video available uses playability snapshot.

Gates:

DISTINCT_COLLECTION_COUNT=
DUPLICATE_COLLECTION_SETS=0
UNCLASSIFIED_DUPLICATE_COLLECTIONS=0
EMPTY_COLLECTIONS_PUBLISHED=0
BROKEN_COLLECTION_LINKS=0
COLLECTION_COUNT_MISMATCHES=0
COLLECTION_GRID_EMPTY_RAIL_WIDTH_PX=0
COLLECTION_GRID_1363_COLUMNS>=7

17. B22 — Footer, legal, contacts и system pages

Footer

Desktop 4–5 columns:

brand/about;

sections;

catalog/taxonomy;

documents;

contacts.

Tablet 2–3 columns.
Mobile 1–2 columns or accessible accordion.

Padding:

desktop 32–40 px;

mobile 24 px 16 px.

Do not show:

commit SHA;

build id;

version;

environment;

internal service name.

Owner values:

contact_email;

telegram_url;

privacy_url;

terms_url;

optional rights/removal contact.

Missing value:

never invent;

hide exact missing item;

do not leave empty column;

OWNER_DATA_REQUIRED records it;

FOOTER_VISUAL_PASS and FOOTER_DATA_PASS separate.

404

real HTTP 404;

header/footer remain;

clear H1;

route not reflected unsafely;

links home/catalog/search;

no soft 404;

canonical policy frozen.

5xx/degraded

500/502/503 have branded safe page where controlled;

retry/home link;

no stack trace;

nginx raw 502 monitored as failure, not accepted as template;

no infinite refresh.

Empty

valid empty filter/search is HTTP 200;

scope explained;

reset link;

compact panel;

not indistinguishable from 404.

Gates:

EXPECTED_404_PASS=1
SOFT_404_COUNT=0
HTTP_5XX_COUNT=0
RAW_PROXY_502_COUNT=0
INTERNAL_LINK_404_COUNT=0
FOOTER_TECHNICAL_MARKER_COUNT=0
FOOTER_CONTACT_GATE_PASS=0|1
FOOTER_DOCUMENTS_GATE_PASS=0|1

18. B23 — Responsive, accessibility и cross-route consistency

Required viewports:

1920×1080;

1440×900;

1363×936;

1280×900;

1024×900;

768×1024;

390×844;

360×800;

mobile landscape.

Required states:

normal;

missing poster;

missing description;

no rating;

no video;

player resolving/ready/playing/unavailable/error;

long title;

one and many seasons;

empty search/filter;

404;

dark/light if supported.

Accessibility:

skip link;

one H1;

heading order;

accessible names;

form labels;

focus visible;

44×44 targets;

keyboard full flow;

dialog focus trap/return;

Esc;

alt;

aria-current;

no color-only state;

contrast AA;

zoom 200% reflow;

reduced motion.

Cross-route:

same header/footer;

same card registry;

same canonical metadata;

same poster fallback;

same rating presentation;

no style injection race;

no hydration mismatch.

19. B24 — SEO/indexability, deploy, rollback и cache safety

Immutable owner indexability rule

Этот проход не меняет indexability.

Перед работой записать для zonafilm.space:

robots.txt bytes/digest;

meta robots per route family;

X-Robots-Tag;

sitemap location/digest;

canonical host;

owner registry state/revision.

После deploy exact state должен совпасть.

Запрещено:

открывать закрытый сайт;

закрывать открытый сайт;

менять robots/meta/X-Robots/sitemap;

менять canonical host;

добавлять noindex как «безопасный default»;

использовать staging default в production;

считать rebuild разрешением на indexability mutation.

Любая mutation требует отдельного явного owner approval с domain, desired state, scope, timestamp и digest. Без него:

INDEXABILITY_MUTATIONS=0
DNS_MUTATIONS=0

Deploy

Production deploy, restart и rollback не разрешены самим этим ТЗ. Сначала всегда выполнить read-only/local часть:

Собрать immutable artifact из final feature head.

Доказать source/manifest/artifact digest match.

Создать rollback bundle и проверить restore только в temp/local drill, не поверх live.

Выпустить OWNER_DEPLOY_PACKET с profile, domain, artifact SHA-256, feature head, exact files, service, rollback digest, route matrix и change-window plan.

Production activation разрешена только если владелец отдельно предоставил все поля:

OWNER_DEPLOY_APPROVAL_ID
OWNER_DEPLOY_APPROVED_DOMAIN=zonafilm.space
OWNER_DEPLOY_APPROVED_PROFILE=zona-01
OWNER_DEPLOY_APPROVED_ARTIFACT_SHA256
OWNER_DEPLOY_CHANGE_WINDOW_START
OWNER_DEPLOY_CHANGE_WINDOW_END
OWNER_DEPLOY_APPROVED_SERVICE
OWNER_DEPLOY_ROLLBACK_AUTHORIZED=YES

Approval должен совпасть с exact artifact и быть действующим в момент операции. Без любого поля: state=BLOCKED_DEPENDENCY, blocker_owner=privileged_restart, blocker_code=OWNER_DEPLOY_APPROVAL_REQUIRED, READY_FOR_OWNER_DEPLOY=YES; production files, service и cache не мутировать.

После валидного approval:

Deploy scope только zona-01 и exact approved files.

Restart только exact approved service существующим workflow; никаких guard bypass.

Доказать live runtime digest match и cache coherence.

Выполнить frozen route/status matrix, AFTER_LIVE screenshot/oracle matrix и два стабильных live runs.

При hard failure выполнить только заранее утверждённый scoped rollback в том же change window и остановиться.

Push и merge остаются запрещены, если они отдельно не перечислены в другом точном owner approval. Разрешение deploy не является разрешением push/merge, DNS, DB, indexing или scheduler mutations.

Не считать файлы на диске deployed, пока runtime не совпадает.

Cache

Popular cache varies by week id/digest;

catalog/new varies by snapshot/revision and query;

title varies by title detail/player descriptor revisions;

no cache bleed across domain/profile;

ETag changes only with payload;

stale content follows declared last-good policy;

purge scoped.

20. Local и live manifests

До B01 создать два immutable manifests.

LOCAL_FIXTURE_MANIFEST

Только test environment:

full;

missing poster;

missing description;

missing rating;

unavailable player;

slow player;

async replacement;

long title;

empty collection;

invalid page;

invalid title;

invalid episode;

invalid taxonomy slug;

valid empty filter;

controlled application 500;

controlled upstream 502;

controlled maintenance 503 with Retry-After;

stale weekly;

missing weekly;

future premiere;

missing added timestamp;

duplicated source row;

wrong genre mapping fixture.

Never deploy local fixtures.

LIVE_ENTITY_MANIFEST

Только реально существующие entities:

home top/middle/bottom;

/movies/;

/series/;

/animation/;

film title;

animation title;

one-season series;

multi-season series;

exact episode;

no-rating;

no-description if exists;

no-video;

catalog default/page2;

invalid catalog page;

filtered genre/year/country;

/new/ each available mode;

search exact/translit/no-result;

collections hub/detail;

invalid title/episode/taxonomy cases;

404;

player resolving/ready/playing/unavailable/error where safely observable;

synthetic 5xx/degraded health check without production fault injection.

Each row:

case_id
domain
route
entity_id
viewport
theme
state
reference_digest
expected_full_screenshot
expected_block_crops
expected_dom_oracle
catalog_revision
weekly_revision
ratings_revision
recommendation_revision

Expected case count comes from manifest before implementation. It cannot be reduced to match captured files.

21. Обязательные gates

LOCAL_GATES

CONTRACT_MUTATED=0
REFERENCE_BASELINE_VALID=1
PASSPORT_MANIFEST_VALID=1
DISPLAY_POLICIES_FROZEN=1
REFERENCE_DEVIATION_REGISTRY_FROZEN=1
CTA_ROUTE_REGISTRY_FROZEN=1
ROUTE_FAMILIES_MAPPED_EQUALS_DISCOVERED=1
UNCOVERED_STATE_BRANCHES=0
LOCAL_MISSING_CASE_COUNT=0
GEOMETRY_OUT_OF_TOLERANCE_COUNT=0
HORIZONTAL_OVERFLOW_COUNT=0
OVERLAP_COUNT=0
UNINTENDED_INNER_SCROLLBARS=0
BROKEN_INTERNAL_LINKS=0
HTTP_5XX_COUNT=0
RAW_PROXY_502_COUNT=0
AMBIGUOUS_TIMESTAMP_RENDER_COUNT=0
BUILD_OR_DEPLOY_TIME_USED_AS_CONTENT_TIME=0
VISIBLE_DATES_WITH_VALID_PROVENANCE_EQUALS_TOTAL=1
RATING_ZERO_FALLBACK_COUNT=0
CROSS_SOURCE_VOTE_SUMMING=0
DESCRIPTION_SOURCE_AVAILABLE_NOT_RENDERED_COUNT=0
UNPROVEN_DESCRIPTION_RENDERED_COUNT=0
POPULAR_REQUEST_TIME_RECOMPUTES=0
POPULAR_MEMBERSHIP_CHANGES_WITHIN_WEEK=0
POPULAR_RANDOM_ROTATION=0
POPULAR_DUPLICATE_TITLE_IDS=0
POPULAR_TEMPLATE_PASS_PUBLICATION_COUNT=0
POPULAR_TEMPLATE_PASS_REPAIR_COUNT=0
YEAR_COUNT_MISMATCHES=0
GENRE_LABEL_QUERY_MISMATCHES=0
PAGINATION_DUPLICATES=0
PAGINATION_MISSING_ITEMS=0
PAGINATION_QUERY_LOSSES=0
PLAYER_WIDTH_FILL_RATIO>=0.98
PLAYER_HEIGHT_FILL_RATIO>=0.98
PLAYER_INSTANCE_MAX=1
PLAYER_SMALL_RENDER_COUNT=0
EXACT_EPISODE_ROUTE_PASS=1
PLAYER_CONTRACT_ID_PRESENT=1
EXACT_EPISODE_IDENTITY_PRESERVED_ASYNC=1
LATE_RESPONSE_REPLACEMENTS=0
FIRST_PARTY_UNCAUGHT_ERROR_COUNT=0
HYDRATION_MISMATCH_COUNT=0
KEYBOARD_NAVIGATION_PASS=1
FOCUS_TRAP_RETURN_PASS=1
CONTRAST_AA_PASS=1
ZOOM_200_REFLOW_PASS=1
LOCAL_STABLE_RUNS>=2

DEPENDENCY_GATES

Эти gates проверяются, но presentation worktree не имеет права чинить их самовольно:

CATALOG_SNAPSHOT_AND_ORACLE_MATCH=1
ROUTE_STATUS_CANONICAL_CONTRACT_PASS=1
SEARCH_RANKER_CONTRACT_PRESENT=1
PLAYER_CONTRACT_PRESENT=1
WEEKLY_SNAPSHOT_CONTRACT_PRESENT=1
OWNER_INDEXABILITY_REGISTRY_PRESENT=1
OWNER_VALUES_COMPLETE=0|1
OWNER_DEPLOY_APPROVAL_VALID=0|1

Если dependency gate красный, затронутый блок может получить PASS_LOCAL_PRESENTATION_BLOCKED_DEPENDENCY, но не PASS_LIVE/CLOSED. Это не принуждает остальные независимые блоки останавливаться и не разрешает executor исправлять чужой слой.

LIVE_DEPLOY_GATES

LIVE_MISSING_CASE_COUNT=0
LIVE_TEST_FIXTURE_MUTATIONS=0
SOURCE_ARTIFACT_RUNTIME_MATCH=1
MANIFEST_RUNTIME_DIGEST_MATCH=1
CACHE_COHERENCE_PASS=1
WRONG_BUILD_RESPONSE_COUNT=0
RESTART_LOOP_COUNT=0
NEW_JOURNAL_ERROR_COUNT=0
ROLLBACK_RESTORE_DRILL_PASS=1
OTHER_DOMAINS_MUTATED=0
INDEXABILITY_STATE_BEFORE_AFTER_MATCH=1
ROBOTS_META_XROBOTS_SITEMAP_DIGEST_UNCHANGED=1
LIVE_STABLE_RUNS>=2

Blank required field is failure. N/A/NOT_RUN needs na_reason, owner, evidence and next action. Для READY_FOR_OWNER_DEPLOY live-only fields имеют NOT_RUN с na_reason=OWNER_DEPLOY_APPROVAL_REQUIRED; это не считается blank, но запрещает любой PASS_LIVE verdict. Иначе поле увеличивает UNJUSTIFIED_NA_COUNT.

22. Блочный порядок исполнения

State model:

PENDING
PENDING_RECERTIFICATION
PASS_LOCAL_PENDING_LIVE
PASS_LOCAL_PRESENTATION_BLOCKED_DEPENDENCY
BLOCKED_DEPENDENCY
READY_FOR_OWNER_DEPLOY
PASS_LIVE
CLOSED

Blockers:

reference;

core_data;

search;

player;

seo;

owner_values;

privileged_restart.

Каждый blocker записывается единообразно:

state=BLOCKED_DEPENDENCY | PASS_LOCAL_PRESENTATION_BLOCKED_DEPENDENCY
blocker_owner=reference|core_data|search|player|seo|owner_values|privileged_restart
blocker_code=<stable machine code>
evidence_path=
next_action=

BLOCKED_REFERENCE и BLOCKED_SEARCH как отдельные состояния не используются.

22.1. Dependency и invalidation policy

B00 блокирует все блоки до frozen contract.

B03 зависит от weekly snapshot contract; B04/B05/B06/B10/B11/B12/B13 — от catalog/event oracle; B14 — от ranker contract; B17/B18/B20 — от player contract; B19 — от recommendation policy; B22 data closure — от owner values.

После dependency blocker разрешено продолжать только блоки, которые не читают этот contract и не используют его shared component. В checkpoint перечислить continued_independent_blocks и blocked_descendants.

Изменение B01 invalidates header/navigation gates всех route families.

Изменение B09 invalidates card/geometry/provenance gates B02–B08, B11–B14, B19 и B21.

Изменение B17/B18 invalidates B20 player/episode gates.

Изменение shared tokens/layout в B23 invalidates все затронутые B01–B22 viewports.

Любая поздняя правка source mapping, route registry, snapshot digest или acceptance oracle invalidates все dependent blocks.

Invalidated block возвращается в PENDING_RECERTIFICATION; старый green evidence не принимается.

B24 возможен только после полной итоговой local recertification всех не заблокированных блоков из final feature head и двух последовательных стабильных runs.

Plan:

Block

Scope

Close condition

B00

reference, passports, manifests, provenance, owner state

frozen digest

B01

header/nav/search entry

responsive+a11y

B02

hero

snapshot/geometry

B03

weekly block

weekly snapshot gates

B04

catalog addition feed

true events only

B05

kind entries

full counts

B06

genres

mapping/count oracle

B07

home collections

distinct/live

B08

about/SEO

honest/collapsed

B09

card registry

profiles and fallbacks

B10

compact filters

URL/state contract

B11

grid/pagination

full oracle

B12

taxonomy

years/countries/genres

B13

/new modes

timestamp semantics

B14

search

existing ranker contract

B15

title passport

metadata geometry

B16

description/ratings

provenance

B17

player

full-fill/single instance

B18

episodes

default/exact contract

B19

recommendations

dedupe/playability

B20

exact episode page

compact/player-first

B21

collections

hub/detail/counts

B22

footer/system states

honest owner gaps

B23

responsive/a11y/matrix

2 stable local runs

B24

immutable artifact; scoped deploy/live only after exact approval

artifact packet, then 2 stable live runs if authorized

One block:

inventory;

passport;

BEFORE;

data/state classification;

minimal implementation;

tests;

AFTER_LOCAL;

fix until gates pass;

functional commit;

evidence commit/checkpoint.

Do not deploy after every block. B00–B23 complete locally, then one immutable artifact in B24.

23. Финальный отчёт

VERDICT=PASS_READY_FOR_OWNER_VISUAL_REVIEW | PASS_TEMPLATE_WITH_OPEN_CADENCE | PRESENTATION_SHELL_PASS_WITH_GAPS | READY_FOR_OWNER_DEPLOY | BLOCKED_DEPENDENCY | NEEDS_OWNER_VALUES | NEEDS_REPAIR
STAGE=ZONA-BLOCKWISE-PARITY-08
BRANCH=
START_HEAD=
FEATURE_HEAD=
REPORT_HEAD=
FINAL_HEAD=
CONTRACT_SHA256=
CONTRACT_MUTATED=0
REFERENCE_URL=
REFERENCE_BASELINE_VALID=
BLOCKS_TOTAL=25
BLOCKS_PASS_LOCAL=
BLOCKS_PASS_LIVE=
BLOCKS_OPEN=
OPEN_BLOCKERS=
DEPENDENCY_GATE_FAILURES=
PRESENTATION_GATE_FAILURES=
BLOCKED_DESCENDANTS=
INVALIDATED_BLOCKS_RECERTIFIED=
TESTS_TOTAL=
TESTS_PASSED=
LOCAL_STABLE_RUNS=
LIVE_STABLE_RUNS=
LIVE_BUILD=
ARTIFACT_SHA256=
SOURCE_ARTIFACT_RUNTIME_MATCH=
CACHE_COHERENCE_PASS=
CATALOG_TOTAL=
CATALOG_ORACLE_TOTAL=
YEAR_FACET_COUNT=
YEAR_2019_COUNT=
NEW_TOTAL=
NEW_2019_COUNT=
NEW_MODE_COUNT=
VISIBLE_DATES_TOTAL=
VISIBLE_DATES_WITH_VALID_PROVENANCE=
VISIBLE_DATES_WITH_VALID_PROVENANCE_EQUALS_TOTAL=
BUILD_TIME_AS_CONTENT_TIME_COUNT=
POPULAR_REFRESH_MODE=
POPULAR_WEEK_ID=
POPULAR_WEEKLY_DIGEST=
POPULAR_REQUEST_TIME_RECOMPUTES=
POPULAR_MEMBERSHIP_CHANGES_WITHIN_WEEK=
POPULAR_REGULAR_PUBLICATION_COUNT_PER_ISO_WEEK=
POPULAR_TEMPLATE_PASS_PUBLICATION_COUNT=
POPULAR_REPAIR_PUBLICATION_COUNT=
POPULAR_REPAIR_INCIDENT_ID=
POPULAR_TWO_REAL_WEEKLY_CYCLES_OBSERVED=
POPULAR_TIMER_ENABLED=
POPULAR_TIMER_OWNER_APPROVAL_ID=
DESCRIPTION_SOURCE_AVAILABLE_COUNT=
DESCRIPTION_SOURCE_AVAILABLE_RENDERED_COUNT=
DESCRIPTION_SOURCE_AVAILABLE_NOT_RENDERED_COUNT=
TRUE_DESCRIPTION_GAP_COUNT=
RATING_FACT_COUNT_BY_SOURCE=
MISSING_RATING_RENDERED_AS_ZERO=
CROSS_SOURCE_VOTE_SUMMING=
PLAYER_GOLDEN_RUNS=
PLAYER_WIDTH_FILL_RATIO=
PLAYER_HEIGHT_FILL_RATIO=
PLAYER_INSTANCE_MAX=
PLAYER_SMALL_RENDER_COUNT=
EXACT_EPISODE_ROUTE_PASS=
RECOMMENDATION_CURRENT_TITLE_COUNT=
RECOMMENDATION_DUPLICATE_IDS=
RECOMMENDATION_BROKEN_LINKS=
SCREENSHOT_MATRIX_EXPECTED_LOCAL=
SCREENSHOT_MATRIX_CAPTURED_LOCAL=
SCREENSHOT_MATRIX_EXPECTED_LIVE=
SCREENSHOT_MATRIX_CAPTURED_LIVE=
DOM_GEOMETRY_ORACLES_EXPECTED=
DOM_GEOMETRY_ORACLES_PASSED=
HORIZONTAL_OVERFLOW_COUNT=
OVERLAP_COUNT=
BROKEN_INTERNAL_LINKS=
INTERNAL_LINK_404_COUNT=
HTTP_5XX_COUNT=
RAW_PROXY_502_COUNT=
FOOTER_VISUAL_PASS=
FOOTER_DATA_PASS=
FOOTER_CONTACT_GATE_PASS=
FOOTER_DOCUMENTS_GATE_PASS=
OWNER_DATA_REQUIRED=
OWNER_DATA_REQUIRED_COUNT=
INDEXABILITY_STATE_BEFORE=
INDEXABILITY_STATE_AFTER=
INDEXABILITY_STATE_BEFORE_AFTER_MATCH=
ROBOTS_META_XROBOTS_SITEMAP_DIGEST_UNCHANGED=
ROLLBACK_PATH=
ROLLBACK_DIGEST=
ROLLBACK_VERIFIED_BEFORE_ACTIVATION=
ROLLBACK_RESTORE_DRILL_PASS=
OWNER_DEPLOY_APPROVAL_ID=
OWNER_DEPLOY_APPROVAL_VALID=
OWNER_DEPLOY_APPROVED_ARTIFACT_SHA256=
OWNER_DEPLOY_CHANGE_WINDOW=
LIVE_EXECUTION_STATUS=
READY_FOR_OWNER_DEPLOY=
READY_FOR_OWNER_VISUAL_REVIEW=
ZONA_TEMPLATE_CAN_BE_CLOSED=
ZONA_VISUAL_FINALIZATION_CAN_BE_CLOSED=
ZONA_POPULAR_CADENCE_CAN_BE_CLOSED=
ZONA_OVERALL_CAN_BE_CLOSED=
OTHER_DOMAINS_MUTATED=0
DNS_MUTATIONS=0
INDEXING_MUTATIONS=0
PRODUCTION_DB_MIGRATIONS=0
PAID_OPERATIONS=0
PUSH_PERFORMED=0
MERGE_PERFORMED=0
SECRETS_EXPOSED=0
HARD_GATE_FAILURE_COUNT=
REQUIRED_GATE_BLANK_COUNT=0
UNJUSTIFIED_NA_COUNT=0

Verdict formulas применяются сверху вниз; первый совпавший verdict побеждает, поэтому они mutually exclusive:

NEEDS_REPAIR, если CONTRACT_MUTATED!=0, есть unauthorized mutation, safety/indexability regression, failed test, failed applicable presentation gate, HARD_GATE_FAILURE_COUNT>0, REQUIRED_GATE_BLANK_COUNT>0 либо UNJUSTIFIED_NA_COUNT>0 и это не объясняется только заранее классифицированной внешней dependency.

BLOCKED_DEPENDENCY, если presentation gates затронутых уже реализованных частей зелёные, но DEPENDENCY_GATE_FAILURES>0 для reference/core_data/search/player/seo и blocker packet заполнен. Owner values, production activation approval и два weekly cycles из этой категории исключены и имеют отдельные verdicts.

NEEDS_OWNER_VALUES, если единственный незакрытый класс — OWNER_DATA_REQUIRED_COUNT>0, технические и dependency gates зелёные, а контакты/legal не выдуманы.

READY_FOR_OWNER_DEPLOY, если B00–B23 полностью recertified локально, LOCAL_STABLE_RUNS>=2, все обязательные owner values и dependency gates зелёные, immutable artifact/rollback packet готовы, но точного OWNER_DEPLOY_APPROVAL_ID для этого artifact/change window нет. LIVE_EXECUTION_STATUS=NOT_AUTHORIZED, production mutations=0.

PRESENTATION_SHELL_PASS_WITH_GAPS, если локальные и, когда отдельно авторизованы, live presentation gates зелёные, contracts присутствуют, но существуют только доказанные source-content gaps (absent description/poster/rating/episode feed), все они отображаются честно и ни один broken contract не маскируется gap-ом.

PASS_TEMPLATE_WITH_OPEN_CADENCE, если выполнены все условия PASS_READY_FOR_OWNER_VISUAL_REVIEW, кроме POPULAR_TWO_REAL_WEEKLY_CYCLES_OBSERVED=1; при этом оно равно 0, weekly contract технически зелёный, READY_FOR_OWNER_VISUAL_REVIEW=YES, ZONA_POPULAR_CADENCE_CAN_BE_CLOSED=NO, ZONA_OVERALL_CAN_BE_CLOSED=NO.

PASS_READY_FOR_OWNER_VISUAL_REVIEW только если одновременно:

CONTRACT_MUTATED=0
BLOCKS_PASS_LIVE=BLOCKS_TOTAL
BLOCKS_OPEN=0
OPEN_BLOCKERS=0
DEPENDENCY_GATE_FAILURES=0
PRESENTATION_GATE_FAILURES=0
TESTS_PASSED=TESTS_TOTAL
LOCAL_STABLE_RUNS>=2
LIVE_STABLE_RUNS>=2
OWNER_DATA_REQUIRED_COUNT=0
FOOTER_DATA_PASS=1
FOOTER_CONTACT_GATE_PASS=1
FOOTER_DOCUMENTS_GATE_PASS=1
POPULAR_TWO_REAL_WEEKLY_CYCLES_OBSERVED=1
OWNER_DEPLOY_APPROVAL_VALID=1
every applicable LOCAL_GATE passes
every applicable DEPENDENCY_GATE passes
every applicable LIVE_DEPLOY_GATE passes
HARD_GATE_FAILURE_COUNT=0
REQUIRED_GATE_BLANK_COUNT=0
UNJUSTIFIED_NA_COUNT=0

Timer не включается автоматически. Два тестовых запуска внутри одной недели не заменяют два реальных ISO-week transitions.

24. Evidence tree

artifacts/evidence/zona-blockwise-YYYY-MM-DD/
  00-baseline/
    reference/
    current-live/
    contract.json
    contract.sha256
    route-registry.json
    local-fixture-manifest.json
    live-entity-manifest.json
  B01-header/
  B02-hero/
  B03-weekly/
  B04-catalog-added/
  B05-kind-entry/
  B06-genres/
  B07-home-collections/
  B08-about/
  B09-card-registry/
  B10-filters/
  B11-grid-pagination/
  B12-taxonomy/
  B13-new/
  B14-search/
  B15-title-passport/
  B16-description-ratings/
  B17-player/
  B18-episodes/
  B19-recommendations/
  B20-episode-page/
  B21-collections/
  B22-footer-system/
  B23-responsive-a11y/
  B24-live/
  FINAL.md
  FINAL.json

Each Bxx:

BEFORE;

AFTER_LOCAL;

AFTER_LIVE if renderable;

DOM_GEOMETRY.json;

DATA_PROVENANCE.json;

TESTS.txt;

BLOCK.md;

screenshot contact sheet.

## 25. Команда для Cursor

Скопировать целиком в поле Goal. Это последний раздел документа намеренно.

/goal
Доведи zonafilm.space (только профиль zona-01) до структурного, геометрического и функционального соответствия утверждённому reference-сайту, работая строго ПО ОДНОМУ БЛОКУ по ZONA_BLOCK_SPEC_V1.

Канонический acceptance contract должен находиться по exact path:
/home/claude/wt-zona-finalization-01/docs/ZONA_BLOCK_SPEC_V1.md

Проверяемая ревизия: ZONA_BLOCK_SPEC_V1, sections 1–24. SHA-256 вычисляется командой `sed '/^## 25\. Команда для Cursor$/,$d' docs/ZONA_BLOCK_SPEC_V1.md | sha256sum`; ожидаемый digest:
01e9db7b27eb6c4bc41160ca6270f25aa7e6352b743dac2b9f09a0493b7b58fb

Если файл отсутствует, получен не из приложенного владельцем документа, digest не совпадает или sections 1–24 изменились — ничего не реконструируй по памяти и не начинай код: `state=BLOCKED_DEPENDENCY`, `blocker_owner=reference`, `blocker_code=ACCEPTANCE_CONTRACT_MISSING_OR_MISMATCH`. Сохрани observed digest и запроси exact file. Sections 1–24 после B00 immutable; section 25 не входит в acceptance digest.

Текущий результат не закрыт. На входе weekly popular уже переведён на immutable WEEKLY_SNAPSHOT: ISO-8601 week в UTC, request-time recompute=0, membership и порядок стабильны внутри недели, random rotation=0, максимум одна regular publication за ISO-неделю. Не ломай этот контракт. Этот проход строго read-only для weekly pipeline: не запускай manual generate/publish/repair/backfill, не включай timer, не создавай scheduler mutation. Frontend не сортирует, не rerank-ит, не dedupe-ит и не дополняет snapshot; сохраняет week_id, revision, digest, membership и order. Два штатных weekly cycles ещё не наблюдены; proposed timer Mon 04:10 UTC остаётся owner-gated.

B00 обязателен до кода. Подтверди exact REFERENCE_URL. Если внешний референс недоступен или не подтверждён владельцем, выставь `state=BLOCKED_DEPENDENCY`, `blocker_owner=reference`, `blocker_code=REFERENCE_UNAVAILABLE` и остановись — не подбирай другой сайт и не назначай себе visual target. Сними reference/current BEFORE на всех обязательных маршрутах и viewport, сохрани DOM geometry, computed styles, screenshots и SHA-256. Заморозь contract, block passports, display policies, `REFERENCE_DEVIATION_REGISTRY`, `CTA_ROUTE_REGISTRY`, LOCAL_FIXTURE_MANIFEST и LIVE_ENTITY_MANIFEST. Reference управляет geometry/order; продуктовый контракт — truth, safety, accessibility, route semantics. Любое расхождение до кода вносится в frozen deviation registry с owner approval. После freeze target/tolerance/matrix менять запрещено.

Работай блоками:
B00 reference/provenance/manifests;
B01 header/nav/search entry;
B02 hero;
B03 weekly popular;
B04 настоящее «Новое в каталоге»;
B05 входы Фильмы/Сериалы/Анимация;
B06 genres;
B07 home collections;
B08 about/SEO;
B09 единый card registry;
B10 compact catalog filters;
B11 catalog grid/pagination;
B12 year/country/genre/type taxonomy;
B13 /new/ с раздельными временными режимами;
B14 search presentation поверх существующего ranker contract;
B15 title passport;
B16 descriptions/ratings;
B17 player;
B18 seasons/episodes;
B19 recommendations;
B20 exact episode page;
B21 collections hub/detail;
B22 footer + 404/empty/5xx;
B23 responsive/accessibility/full local matrix;
B24 immutable artifact + rollback/owner deploy packet; production activation и full live matrix только при отдельном exact owner approval для domain/profile/artifact/service/change window.

Цикл каждого блока:
1. Инвентаризация route, DOM, source fields и ownership.
2. Заполненный паспорт блока.
3. BEFORE screenshots + DOM/data oracle на 1920, 1440, 1363, 1024, 768, 390, 360 и mobile landscape.
4. Классификация normal/empty/missing/stale/error.
5. Минимальная реализация в scope блока.
6. Unit/integration/browser/a11y tests.
7. AFTER_LOCAL и geometry diff против frozen reference.
8. Исправление до прохождения всех LOCAL_GATES блока.
9. Отдельный functional commit вида fix(zona): Bxx ...
10. Evidence checkpoint artifacts/evidence/zona-blockwise-YYYY-MM-DD/Bxx.
11. Только затем следующий блок.

При `BLOCKED_DEPENDENCY` продолжай только независимые блоки согласно разделу 22.1, а dependent descendants перечисли и не закрывай. Любая поздняя правка shared header, card registry, player/episode contract, tokens/layout, route registry, mapping или snapshot invalidates затронутые старые green gates: верни их в `PENDING_RECERTIFICATION` и перезапусти. Перед B24 обязательна полная local recertification final feature head и два стабильных прогона.

Это template/presentation проход. Не меняй Core Data, Search/Ranker semantics, player selection policy, ratings formula, HTTP status/canonical policy, базы данных, event ledgers, global SEO/indexability, DNS или другие домены. Наблюдаемые broken country/alias/canonical routes — dependency evidence, а не разрешение сделать 404→200/redirect. Если обязательного versioned contract нет, выставь `state=BLOCKED_DEPENDENCY` или `PASS_LOCAL_PRESENTATION_BLOCKED_DEPENDENCY` с `blocker_owner=core_data|search|player|seo|owner_values|reference`, stable blocker_code, evidence и next action; собери отдельный task packet и не маскируй gap вычислением во frontend.

Особые требования:
- не выводи подряд пять одинаковых тяжёлых poster rails;
- weekly films/series/animation представь одним блоком с tabs и компактными карточками;
- Popular не пересчитывается на HTTP и не меняет membership внутри ISO-недели;
- если ranking основан только на rating/recent pool, не называй его user popularity без утверждённого popularity_basis;
- числа baseline 53548, 1218, 2144, 7, 92, 1913, 77 и 616 действительны только при совпадении B00 snapshot/ledger/query digest; при другом digest пересчитай oracle, выпусти drift report, ничего не hard-code и не подгоняй UI;
- catalog total и /new/ total — разные scopes; catalog year и /new/ year тоже разные scopes, UI обязан явно подписать scope;
- не «исправляй» totals во frontend через неутверждённый recount/dedupe/join/filter; сохраняй различия absent/null/stale/quarantined/retracted/verified;
- раздели catalog_added_at, source_premiere_at, provider_available_at и episode_released_at; ни одно поле не заменяет другое;
- build/deploy/import/mtime/now никогда не являются публичной content date;
- date-only не получает выдуманное время;
- отсутствующие ratings не показывай как 0 и не суммируй голоса источников;
- source description, доступный в данных, обязан рендериться; true gap не заполняй выдумкой;
- missing poster получает стабильный branded placeholder того же ratio;
- compact filters должны заменить button wall;
- полный вычисляемый year oracle сохраняется; no [:24] cap и никаких вечных acceptance constants;
- проверяй label→query mapping, чтобы «драма» не вела west_content, а «детектив» не вёл action;
- route/status/canonical defects country/year/genre не исправляй в presentation scope: не публикуй broken CTA, зафиксируй blocker и backend/SEO task packet;
- recommendations используют frozen `playable_preferred_with_explicit_nonplayable_state_v1`: current title, duplicates и broken links исключены; non-playable не получает watch badge/CTA; на 1363 нет half-empty растянутого 4-card row;
- player full-width 16:9, iframe/video fill >=98%, single instance, autoplay=0, no 640×360 regression, async replacement safe;
- player presentation только потребляет `PLAYER_CONTRACT_ID`; при его отсутствии BLOCKED_DEPENDENCY. Generic series валидирует selection, возвращённый versioned policy, но не изобретает policy. Exact episode identity никогда не заменяется default даже при async provider replacement;
- invalid page/title/episode/taxonomy slug даёт настоящий HTTP 404; raw 502/5xx=0;
- footer multi-column; build/version/SHA не показывай; контакты/legal не выдумывай;
- optional hidden block height=0; no ad/spacer/min-height voids;
- никакой self-reported visual score вместо screenshot matrix и DOM oracle.

Indexability — жёсткий immutable owner contract. До правок запиши robots.txt, meta robots, X-Robots-Tag, sitemap, canonical host и owner registry revision. После deploy bytes/digests/state должны совпасть. Без отдельного точного owner approval запрещено открывать закрытый сайт или закрывать открытый, менять robots/meta/X-Robots/sitemap/canonical. INDEXING_MUTATIONS=0.

Не деплой после каждого блока. Это Goal само по себе НЕ разрешает production deploy, restart, rollback, push или merge. Заверши B00–B23 локально, получи два последовательных стабильных local runs, собери один immutable artifact, проверь restore только в temp/local drill и подготовь OWNER_DEPLOY_PACKET. Если нет всех точных полей `OWNER_DEPLOY_APPROVAL_ID`, domain=zonafilm.space, profile=zona-01, approved artifact SHA-256, exact service, change-window start/end и rollback authorization — остановись с `READY_FOR_OWNER_DEPLOY=YES`, `LIVE_EXECUTION_STATUS=NOT_AUTHORIZED`, production mutations=0. Только отдельное совпадающее approval разрешает scoped activation. После неё докажи source/artifact/manifest/runtime match, cache coherence, frozen route matrix, full AFTER_LIVE screenshot/oracle matrix и два stable live runs; rollback допустим только если он заранее входит в это же approval/change window. Guard bypass запрещён.

Не включай weekly timer, не запускай manual weekly publish/generate/repair/backfill и не создавай scheduler mutation. Техническую стабильность current-week проверяй read-only; cadence может закрыться только после двух реальных ISO-week UTC transitions.

После каждого блока дай короткий checkpoint: block, commit, tests, geometry, provenance, remaining gap, next block. В финале выдай отчёт строго по разделу 23 ZONA_BLOCK_SPEC_V1 и приложи карту страниц, before/reference/after contact sheets, geometry diffs, provenance всех дат/ratings/descriptions/counts, commits B00–B24, rollback path/digest и owner review URLs.

Verdict не назначай вручную: примени mutually-exclusive priority formulas раздела 23. `NEEDS_REPAIR` побеждает при implementation/safety failure; затем `BLOCKED_DEPENDENCY`; затем `NEEDS_OWNER_VALUES`; затем `READY_FOR_OWNER_DEPLOY`; затем `PRESENTATION_SHELL_PASS_WITH_GAPS`; затем `PASS_TEMPLATE_WITH_OPEN_CADENCE`; полный `PASS_READY_FOR_OWNER_VISUAL_REVIEW` разрешён только при owner data complete, exact authorized live run, всех local/dependency/live gates и `POPULAR_TWO_REAL_WEEKLY_CYCLES_OBSERVED=1`. Два запуска в одной неделе не считаются двумя циклами.
