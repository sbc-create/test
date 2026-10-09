# Передача: изменения общих контрактов очереди, моста и доставки

Кому: Архитектор (контракты редакционной очереди, моста MCP, доставки).
От кого: SEO-модуль, ветка `claude/indexing-operation-02`.
Дата: 2026-10-08.

Файлы очереди (`wt-seo-index-audit-20260930`, `seo_engine/content_operator`) и
моста (`factory/qwen/mcp.py`) я НЕ менял: это общие контракты. Ниже — что
найдено на реальных данных, что нужно и как проверить. Обнаружение всех
случаев уже работает в SEO-модуле (`seo_operator/regular.py::queue_hygiene`,
`verify_task_targets`) и попадает в суточный отчёт — после вашего изменения
отчёт сам покажет, что дубли пропали.

## 1. Нормализация адреса при регистрации задания (MOD-08, MOD-09)

**Пример.** `/var/lib/seo-content-operator/registry.json`:

| content_id | canonical_url | статус | ответ сайта |
| --- | --- | --- | --- |
| request-fa190135f85d72c9 | https://yummyani.org/anime/ledyanaya-stena-2 | BLOCKED_INSUFFICIENT_FACTS | 200 |
| request-b74982172ba225a2 | /anime/ledyanaya-stena-2 | READY_VERIFIED | (та же страница) |
| request-61ce6f9a15437cba | https://yummyani.site/anime/neveroyatnoe-priklyudenie-…/season/7/episode/3 | NEEDS_UPDATE | **404** (опечатка) |
| request-d95607c97ecfdd6a | /anime/neveroyatnoe-priklyuchenie-…/season/7/episode/3 | NO_TARGET_PAGE | **200** |
| request-01b4575857beada5 | https://lordfilm47.space/title/specnaz-novobrancy | NEEDS_UPDATE | **308** → форма со слешем |

**Нужно.** `editorial_queue_register` приводит адрес к абсолютной канонической
форме семейства (`factory.qwen.registry.адрес_тайтла`, 308 — заменить целью
редиректа), ищет существующее живое задание по нормализованному ключу и
отклоняет адрес, который не отвечает 200, с названной причиной.

**Проверка.** Повторная регистрация `/anime/ledyanaya-stena-2` для yummyani.org
возвращает `task_register_existing` с `request-fa19…`; регистрация 404-адреса —
отказ. В суточном отчёте SEO: «живых дублей одной страницы: 0».

## 2. Роль владельца при выдаче задания (MOD-10)

**Пример.** `queue_events.jsonl`, сутки до 2026-10-08T11:16Z: 46 выдач
(`task_claimed`) владельцам `seo-analysis-*`, `seo-audit-*`, `seo-analyzer-*`;
18 из 25 адресов брали несколько владельцев. Адрес
`yummyani.site/anime/asy-i-malenkaya-lindan` с 2026-10-06 брали 17 владельцев.

**Нужно.** Распределение принято в `docs/SEO_REGULAR_RUN.md` §3: SEO-исполнитель
регистрирует и ищет, берёт и закрывает только редактор. В контракте —
обязательное поле роли у `editorial_queue_next` (`editor`) с отказом для иной
роли; имя владельца вида `<роль>/<автоматизация>/run-<id>`.

**Проверка.** Суточный отчёт SEO: «заданий, взятых SEO-владельцами: 0».

## 3. task_id в публикации (MOD-11)

**Пример.** animedia.space/title/detektivnoe-agentstvo-li/ опубликован
2026-10-07T09:32:13Z (`/srv/sites/animedia/runtime/overlays/animedia.space/history.jsonl`),
задание на этот адрес зарегистрировано в 09:31; в `registry.json` последний
`published_at` — 2026-09-21. `publish_material`/`publish_post` не принимают
`task_id` и в журнал очереди не пишут.

**Нужно.** Необязательный `task_id` в `publish_material`/`publish_post`; при
наличии — событие `task_published` в `queue_events.jsonl` с адресом, отпечатком
тела и `generation_id`.

**Что уже сделано на стороне SEO.** Каждая публикация, впервые подтверждённая
на сайте, получает исходные показатели из снимка до публикации и оценку через
7 дней по непересекающемуся окну (`state.changes`). Связь с заданием появится,
когда мост начнёт её писать.

## 4. zonafilm.cc: свежий каталог доставляется в каталог, который сайт не читает

**Обнаружено** суточным шагом sitemap (`SITEMAP_LASTMOD_OLD`, MOD-07):
`https://zonafilm.cc/sitemap-1.xml` — 53 916 адресов, самый свежий `lastmod`
2026-09-27; у zonafilm.space и zonafilm12.site — 2026-10-08, 60 707 адресов.

**Источник исправен, устарела копия ячейки.** Измерено 2026-10-08 ~12:00Z
(время изменения, размер, sha256 первых 16 знаков, число позиций `items`):

| файл | изменён | байт | sha256 | позиций |
| --- | --- | --- | --- | --- |
| `/srv/lords/.frontend/zona-02-catalog.json` (источник издателя) | 2026-10-08 04:01 | 18 957 044 | 67d9f0f1b24790e5 | 60 699 |
| `/srv/lords/.frontend/sites/zona-02/data/zona-02-catalog.json` (куда доставляет издатель) | 2026-10-08 04:01 | 18 957 044 | 67d9f0f1b24790e5 | 60 699 |
| `/srv/zonafilm-cc/data/zona-02-catalog.json` (**что читает сайт**) | **2026-09-28 03:56** | 16 836 385 | d0a9caa090318e3d | **53 908** |

На zonafilm.cc не хватает 6 791 позиции.

**Неисправный этап — переключение `runtime.data_dir` при переезде ячейки.**

1. С 2026-09-28 10:47 сайт обслуживает `nova-zonafilm-cc.service`
   (`ExecStart=… run.py --port 9123 --data-dir /srv/zonafilm-cc/data`; ссылка в
   `multi-user.target.wants` от 28.09 10:47; прежний `nova-zona-02.service` не
   включён). `127.0.0.1:9123/healthz` → 200.
2. `config/site-cells.json`, ячейка `zona-02`: `runtime.data_dir =
   /srv/lords/.frontend/sites/zona-02/data`, а
   `runtime.data_dir_after_relocation = /srv/zonafilm-cc/data` так и не перенесён
   в `data_dir`.
3. Издатель `/srv/site-factory/content-pipeline/refresh.py` (`размещение()` →
   `свой_каталог`, `managed_by=cell`, `data_owner=pipeline`) кладёт снимок по
   `data_dir` — то есть в каталог, который никто не читает.

Правило уже записано в `docs/PORTABLE_SITE_CELL.md` («Реестр описывает факт, а
не намерение»: `data_dir` переносится тем же шагом, которым переезжает
витрина) — при переезде 28.09 этот шаг пропущен. Это не новая задача, а
незавершённый шаг переезда zona-02; прежний текст этого раздела («нет
обновлятора, как в D197») был неточен и заменён.

**Нужно.** Штатной операцией ячейки (`factory.cell`) перенести
`data_dir_after_relocation` в `data_dir` у zona-02. Каталог ячейки я не трогал:
это постоянные данные сайта; реестр ячеек меняется только через `factory.cell`.

**Критерий проверки (оба пункта):**

* `sha256` файла `/srv/zonafilm-cc/data/zona-02-catalog.json` совпадает с
  `/srv/lords/.frontend/zona-02-catalog.json` после ближайшего прогона издателя,
  число позиций — 60 699 или больше;
* `https://zonafilm.cc/sitemap-1.xml`: самый свежий `lastmod` не старше суток, а
  суточный отчёт SEO не называет zonafilm.cc в «Остановившихся обновлениях».

## 5. Шаблоны семейств: meta и H1 посещаемых страниц (аудит 2026-10-08)

Аудит `seo_operator/page_audit.py` по 5 самым посещаемым адресам каждого домена
(снимок 2026-10-08). Все находки — шаблонные: страница не правится поштучно,
меняется шаблон выпуска семейства.

| что | примеры (входы+просмотры за неделю) | сейчас |
| --- | --- | --- |
| meta главной Zona | zonafilm12.site/ (98), zonafilm.space/ (54) | «Zona Cinema: фильмы, сериалы и анимация.» — 40 знаков |
| H1 на главной | zonafilm.cc/ (74) | H1 нет |
| meta разделов | zonafilm.cc/movies/ (27) «Фильмы на Zona.» — 15 знаков; lordfilm47.space/movies/ (32); lordserials22.info/anime/ (36); animedia.icu/catalog/ (16) «Весь каталог на Animedia.»; animedia.icu/schedule/ (19) | 15–55 знаков, без содержания раздела |
| meta серий | zonafilm.cc/title/boec-baki/season-1/episode-1/ (54), lordfilm47.space/title/specnaz-novobrancy/season-1/episode-1/ (42), 1lordserials1.online/…/utrachennye-gody/… (27) | «X — 1 сезон, 1 серия: смотреть онлайн на Zona.»; на странице серии Lordfilm 37 слов видимого текста |

**Нужно (предложение, не готовый текст).** meta разделов и главных — из того, что
раздел действительно показывает (число позиций, жанры, свежие добавления — всё
это есть в каталоге выпуска); meta серии — название + сезон/серия + первое
предложение описания тайтла, если оно есть в каталоге. H1 на главной zonafilm.cc.

**Проверка.** Суточный отчёт SEO, раздел «Кандидаты на оптимизацию»: у названных
адресов нет `META_THIN` и `H1_MISSING`.

## 6. Процесс редактора: тупиковые и зацикленные задания (журнал очереди)

С 2026-10-06: 454 выдачи → 153 результата. За сутки до 2026-10-08 ~12:56Z — 149
выдач, 29 результатов. Yummy — 84 из 130 результатов «источника нет / нет
источников / страницы нет»; задание `92436c439b73db26` (yummyani.site) выдано 26
раз. Из 47 написанных текстов ворота пропустили 11 (15 — без происхождения).
8 живых заданий на описание висят у семейств без доставки (Lords, AnimeGo) —
выполнить их нельзя.

**Нужно.** (а) `editorial_queue_next` не выдаёт задание на описание витрине без
`deliver`/`display` и задание, у которого последний исход «источника нет», пока
не появилось новое условие (источник, факты); (б) у Yummy — снимок фактов
каталога для `editorial_facts`, как у Animedia: это снимает главную причину
отказов; (в) регистрация задания на описание у семейства без доставки —
отказ с причиной. SEO-сторона с 2026-10-08 такие задания не регистрирует.

**Проверка.** Раздел «Процесс редактора» суточного отчёта: зацикленных заданий 0,
тупиковых 0, доля выдач без результата ниже половины.

## 7. СРОЧНО: мост пишет описания Yummy не в схеме приложения — ни одна публикация не видна

**Доказательство (2026-10-09 07:13:53Z).** `publish_material` на yummyani.site,
слаг `neveroyatnoe-priklyuchenie-dzhodzho-gonka-stalnoy-shar`, автор
`editor/claude-indexing-operation-02`, `expect_generation 0424547f4c48a5c9`.
Ответ моста `state: written`, `occurrences_in_main_block: 0`. На странице через 6
минут — прежний текст (от 2026-09-30).

**Причина — в формате записи.** Читатель приложения
(`/srv/sites/yummyani-staging/repo/src/modules/editorial/title-overlay.ts`, zod
`itemSchema`) требует у каждой записи `title_id` (непустая строка),
`canonical_path`, `content_id`, `content_type`, `published_at`,
`methodology_version`, `content_digest`. Мост (`factory/qwen/editorial.py::публиковать`)
пишет запись в формате Animedia: `slug, title_id: null, body, provenance,
content_digest`. Одна такая запись делает невалидным весь файл, и приложение
молча берёт `title-overlays.last-good.json` (`loadMap → parseFile → last-good-fallback`).

| файл | generation | записи |
| --- | --- | --- |
| `title-overlays.json` (рабочий, невалиден с 07:13:53Z) | `qwen-neveroyatnoe-…-1791530032` | 3 записи в схеме Yummy + 1 в формате Animedia |
| `title-overlays.last-good.json` (показывается) | `0424547f4c48a5c9` | 4 записи в схеме Yummy — то же, что до правки |

Посетитель потерь не видит: показывается прежнее содержимое. Но любая
публикация на Yummy через мост невидима; на yummyani.org из 1 публикации и 26
снятий моста видимых записей нет.

**Нужно.** `публиковать` для адаптера `yummy` — писать запись в схеме приложения
(`title_id` из каталога Yummy, `canonical_path`, `content_id`, `content_type`
`TITLE_DESCRIPTION`, `published_at`, `methodology_version`), до записи проверять
файл той же схемой и отказывать, а не писать невалидный; подтверждение —
появлением текста на странице. После исправления — переписать текущий рабочий
файл штатно (запись ДжоДжо повторно), я повторю приёмку.

**Проверка.** Новый текст ДжоДжо (начинается «…седьмая часть истории
„Невероятные приключения ДжоДжо“, аниме выходит с марта 2026 года») виден на
https://yummyani.site/anime/neveroyatnoe-priklyuchenie-dzhodzho-gonka-stalnoy-shar
и стоит в meta description. До исправления редактор на Yummy не публикует.

## 8. AnimeGo: описание записано, посетителю не видно

**Доказательство.** `/srv/sites/animego/runtime/overlays/an1meg0.site/history.jsonl`:
`prepare` 2026-10-09T00:44:54Z автор `editor/architect-night-20261009/run-1`,
`publish` 00:45:43Z автор `claude-indexing-operation-02`, generation
`qwen-arknayts-moroznaya-pogibel-1791506743`. Страница
https://an1meg0.site/title/arknayts-moroznaya-pogibel/ отвечает 200, текста
записи («Аркнайтс: Морозная погибель» (Arknights: Perish in Frost) — аниме-сериал
2023 г…) на ней нет; регулярная проверка 2026-10-09: `PUBLICATION_TEXT_NOT_VISIBLE`.
Реестр: у an1mego/animeg0/an1meg0 нет операции `publish`, доставка — «механизм не
установлен: читателя правок в выпущенном рантайме нет (animego)».

**Нужно.** Читатель накладок в рантайме AnimeGo (как у Animedia) — или запрет
записи в хранилище AnimeGo до его появления. Публикация мимо возможностей
реестра — это запись, которую никто не прочтёт.

**Проверка.** Текст виден на странице; регулярная проверка снимает
`PUBLICATION_TEXT_NOT_VISIBLE`.

## 9. yummyani.biz/anime/psayren — посещаемая страница отвечает 404

https://yummyani.biz/anime/psayren — 404 (так же на yummyani.site и .org), при этом в
снимке Метрики 2026-10-08 у неё 6 входов и 12 просмотров за неделю. Карточка
исчезла из каталога Yummy, а ссылки и поисковые входы остались.

**Нужно.** Выяснить причину исчезновения карточки; если тайтл снят намеренно —
301 на ближайшую релевантную страницу, а не 404.

## 10. Пересечение исполнителей очереди (факты, ничего не отменялось)

Сутки до 2026-10-09T07:30Z: задания брали 13 владельцев; 13 адресов из 60 брали
двое и больше. Ряды Qwen после отключения трёх автоматизаций описаний продолжают
брать задания Yummy: `editor-bot-20261008` (13), `seo-analysis-2026-10-08` (8),
`editor-claude-01` (5), `seo-analyzer-2026-10-08` (3), `editor_news_reviewer` (2),
`editor_script` (2), `test_check` (3). Активных аренд в момент проверки нет.
Публикации на AnimeGo (§8) записаны владельцем `claude-indexing-operation-02` из
сессии `architect-night` — имя совпадает с веткой SEO; фоновый редактор работает
под `editor/claude-auto/run-<id>`, сессия SEO — под `editor/claude-indexing-operation-02`.

## 11. Мост падает по памяти на любом чтении фактов Lords/Zona (исправлено в коде, нужен перезапуск)

* Наблюдение: `prepare_material` для `lordfilm47.space` трижды (2026-10-09
  07:22:57, 07:26:26, 07:30:26 UTC) — в журнале моста `started` без исхода, через
  ~50 с новый процесс (PID 3162744 → 2984624 → 2999993 → …). Клиент получает
  `RemoteDisconnected` / `ConnectionRefused`; остальные исполнители — тоже.
* Причина (измерено): `editorial.факты()` делал `json.loads` всего снимка
  `/srv/lords/.frontend/<site_id>-details.json`. lords-01 — 112 МБ, пик RSS 574 МБ;
  у `site-factory-mcp.service` `MemoryMax=512M`. Снимки lords-02…09 и zona-01…03 —
  80–82 МБ. Так же падают `editorial_facts` (со слагом и без) и `publish_material`
  у этих сайтов: все идут через `факты()`.
* Исправление (ветка `claude/indexing-operation-02`): `_обойти_снимок` читает
  `details` по одной записи буфером 4 МБ. На lords-01: пик 52 МБ, 1,7–1,9 с,
  60 699 записей и 16 249 без описания — совпадает с полной загрузкой. Тест
  `tests/unit/test_qwen_details_stream.py`.
* Нужно: перезапуск моста, чтобы он подхватил код:
  `sudo systemctl restart site-factory-mcp.service`. До перезапуска вызывать
  `prepare_material`/`publish_material`/`editorial_facts` для Lords/Zona нельзя —
  каждый вызов роняет мост всем. Я их больше не вызываю.
* Задание `134fb47fc8c2fe7d` (lordfilm47.space, «Ван-Пис: Письмо от поклонника»)
  взято в аренду `editor/claude-indexing-operation-02` до 08:15Z; публикация не
  состоялась, черновик не записан.

### §11 — состояние на 08:15 UTC

Мост перезапущен в 08:12:34/08:12:43 и загрузил исправление: `prepare_material`
для lordfilm47.space прошёл (08:14), мост не упал (healthz 200). Следующий отказ —
`publish_material`: «подготовительный каталог /var/lib/site-cells/editorial
недоступен (PermissionError)». Каталог создаёт владелец:
`sudo bash automation/host/apply-editorial-staging-root.sh` (только mkdir,
claude:root 0730, проверка записи; служб и сайтов не трогает). Задание
`2b20fc0c58ef1902` («Путешествие Кино», lordfilm47.space) в аренде до 08:57Z,
черновик в `/srv/sites/lords/runtime/overlays/lordfilm47.space/drafts.json`.

## 12. Lords: правка описания отвергается контрактом сайта (lords-01, lords-02)

* 2026-10-09 08:19 UTC, после создания `/var/lib/site-cells/editorial` владельцем:
  `publish_material` lordfilm47.space → «исполнитель не применил правку: статус
  'finished', причина lords-01: editorial-overrides.json не объявлен
  `user_writable` в контракте сайта — доставка каталога затирала бы правки».
* Сверено: `config/site.json: data_contract.user_writable` — у lords-01 и lords-02
  поля нет ни в рабочей копии (`var/site-repos/lordfilm47-space`,
  `…/lordserial33-biz`), ни в выпущенном коде (`/srv/<сайт>/current`). У zona-01
  объявлено `['site-data', 'community', 'editorial-overrides.json']` — там та же
  операция прошла: https://zonafilm.space/title/ledyanaya-stena/ подтверждена
  (08:25Z, текст в `<main>` и meta).
* Частичной записи нет: `/srv/lordfilm47-space/data/editorial-overrides.json`
  не создан.
* Нужно: объявить `editorial-overrides.json` в `data_contract.user_writable`
  сайтов lords-01 и lords-02 и выпустить контракт штатным путём. Защиту я не
  обхожу и контракт не правлю: это выпуск сайта.
* Готовые тексты: lordfilm47.space «Путешествие Кино: Прекрасный мир»
  (задание 2b20fc0c58ef1902, черновик подготовлен), lordserial33.biz «Доктор
  Стоун: Научное будущее. Часть 3» — `var/editor-runs/pending-lords-20261009.json`.

### §12 — проверка контракта, читателя и обновления каталога (08:45 UTC)

Одного `data_contract` недостаточно: приложения Lords читают правки не там,
куда их кладёт исполнитель.

| сайт | что читает приложение | куда пишет исполнитель |
| --- | --- | --- |
| zona-01 (работает) | `ZONA_EDITORIAL_OVERRIDES=<data>/editorial-overrides.json`, `/__editorial_status` → «прочитано», 1 запись | `/srv/zonafilm-space/data/editorial-overrides.json` |
| lords-02 | `config/site.json: environment.LORDS_EDITORIAL_OVERRIDES=/srv/sites/lords/runtime/overlays/lordserial33.biz/title-overlays.json` (файла нет), подключение `lords02_editorial.подключить` есть; проверка `checks/editorial_wired.py` требует путь, оканчивающийся на `/title-overlays.json` | `/srv/lordserial33-biz/data/editorial-overrides.json` |
| lords-01 | ни переменной, ни подключения: `src/editorial_overlay.py` — другой, старый модуль (читает `/srv/sites/lords/runtime/overlays/<domain>.json`), точкой входа не вызывается | `/srv/lordfilm47-space/data/editorial-overrides.json` |

Сохранность при обновлении каталога (по коду `factory/cell/privileged.py`):
`stage_snapshot` подключает ссылкой всё из `data_contract.user_writable`, засев
идёт один раз и не перезаписывает существующий файл. При отсутствии
`data_contract` действует умолчание: delivered = `{site}-catalog.json`,
`{site}-details.json`; user_writable = `site-data`.

Нужно для разблокировки (выпуск кода сайтов, а не правка данных):
1. lords-01 и lords-02: `data_contract` = delivered как в умолчании +
   user_writable `["site-data", "editorial-overrides.json"]`;
2. путь читателя — `<data>/editorial-overrides.json`, как у zona-01 (у lords-02
   поменять `LORDS_EDITORIAL_OVERRIDES` и `checks/editorial_wired.py`; у lords-01
   подключить читатель той же формы, что у lords-02/zona-01);
3. выпуск штатной заявкой; в обеих рабочих ветках уже лежит невыпущенный
   коммит 08:30 UTC (lordfilm47 782a605, lordserial33 b0475e7 «плеер…») —
   выпуск с вершины ветки увезёт и его.

SEO не выпускает код сайтов параллельно с сессией, которая сейчас работает в
этих репозиториях; запрос на согласование отправлен ей 08:40 UTC.

## Чего я не делал

Не менял очередь, реестры, журналы и данные сайтов; не снимал аренды. В мосте
изменено только чтение снимка фактов (§11). Задание зарегистрировано и взято
одно — §11.
