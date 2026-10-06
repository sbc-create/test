# CHECKPOINT — ANIMEDIA: состав каталога и согласованность обработчика

Окно «ANIMEDIA — состав каталога». Обновлён 2026-10-05.

## Ветки, коммиты и что выложено (2026-10-06)

| Что | Ветка / пакет | Коммит | Выложено |
| --- | --- | --- | --- |
| исполнитель ячеек | `claude/animedia-updater-units-01`, пакет `pkg-d0bd0d25a702` | `fcadbbb` | 07:38:06 UTC узкой установкой (`automation/host/install-executor-narrow.sh`, `1d2d96b`) |
| animedia.space: допуск каталога | `claude/extract-animedia-space-catalog-scope-01` | `34a1c65` | 2026-10-05 16:04 |
| animedia.icu: допуск каталога | `claude/extract-animedia-icu-catalog-scope-01` | `2bb2091` | 2026-10-05 16:20 |
| animedia.space: обработчик | `claude/extract-animedia-space-updater-guard-01` | `b7cbd95` | 07:41 (`animedia-02-code-b7cbd958d5b1`) |
| animedia.icu: обработчик | `claude/extract-animedia-icu-updater-guard-01` | `d1079bd` | 07:58 (`animedia-01-code-d1079bd4b4b5`) |
| animedia.icu: скорость (окно СКОРОСТЬ) | `claude/extract-animedia-icu-perf-01` | `d6622bc` | 08:15 (`animedia-01-code-d6622bc3adae`) |
| animedia.space: скорость (окно СКОРОСТЬ) | `claude/extract-animedia-space-perf-01` | `857cf8c` | 08:38 (`animedia-02-code-857cf8c44700`) |

Установка исполнителя: check-installed 274/0/0, `site_repos_root` =
`/home/claude/wt-portable-site-cell-01`, поля indexing/owner_consent/release
корневого реестра сверены с пакетом (0 расхождений). Резервная копия и откат:
`/var/backups/site-factory-cell/20261006T073805Z/{before.tgz,ROLLBACK.txt}`.

Юниты обработчиков поставил исполнитель при выпусках (не руками):
`animedia-space-update.service.bak.20261006T074110Z`,
`animedia-icu-update.service.bak.20261006T075816Z` — прежние файлы.

## Доказанная причина

### Первоначальное попадание (импорт)

`/srv/site-factory/repo/factory/lords/nova_publish.py`, `это_аниме`: третий
признак `animation+origin` = жанр «мультфильм» + страна из {Япония, Китай,
Южная Корея}. Публикация 2026-10-05: myanimelist_id 7355, genre_anime 280,
animation+origin 255. Всем допущенным ставится `kind: "Аниме"`; витрина
отбирала по `kind` и не отсекала ничего. Пример: «Хитклифф»
`01a0f283-f3d5-7233-9b5f-665e0e108052`, КП 392520, IMDb 0285371 — США/Франция/
Канада/Япония, жанры «мультфильм», «западный контент», MAL нет.

### Повторное появление (каждый ввоз)

Поставщик догружал серии старых сериалов; обработчик сравнивал снимки и писал
событие «новые серии» на каждую догрузку (Хитклифф s1 e31–33, Капитан Планета
e7…e26, На замену e2…e21 — реестр `animedia-02-episode-events.json`). Правило
отбора действовало только на выводе (через `kind`), а на импорте, в реестре
серий, популярном, расписании и карте сайта — не действовало вовсе.

### Рассинхрон сайта и обработчика (animedia.icu)

* `/etc/systemd/system/animedia-icu-update.service` (27.09 16:20:40, root)
  исполняет `/srv/animedia-icu/app/automation/animedia-data-update.py`,
  sha 3374a18b…, 1527 строк; витрина — `current` → `releases/2bb209132004`,
  sha e8c9b966…, 1767 строк.
* В исполняемом файле нет `шаг_карты`, `шаг_допуска`, `РАЗДЕЛЫ_КАРТЫ`. Отчёт
  прогона 16:29 UTC: ключей `sitemap` и `admission` нет, `problems: 0`.
  `/sitemap.xml` 404, строки Sitemap в robots.txt нет; индексация ОТКРЫТА
  (X-Robots-Tag и meta `index, follow`, `Allow: /`).
* Почему юнит остался: исполнитель ячейки (`factory/cell/privileged.py`,
  `promote`) переписывал только юнит витрины (`ЮНИТ_ШАБЛОН`). Юнит обработчика
  не входил ни в один этап выпуска — шаги activate: protected_data, prepare,
  seed_data, install_release, warm_up, switch_route, promote, verify.
  Комментарий в `deploy/*-update.service` требовал `sudo cp` от владельца.
  У space владелец заменил юнит 02.10 08:11 (есть `.bak.20261002T081130Z`),
  у icu — нет. Исправленный юнит лежал в выпуске icu с `378e7b6` (01.10).
* Почему «проблем: 0»: обработчик не знал о шагах, которых в нём нет, а юнит
  считал успехом и код 1 (`SuccessExitStatus=0 1`).

## Затронутые сайты (замер 2026-10-05 ~16:45 UTC)

| Сайт | Выпуск | Обработчик | Карта | Индексация | Допуск |
| --- | --- | --- | --- | --- | --- |
| animedia.space (animedia-02) | 34a1c65 | current, sha = выпуску | 200, 7573 тайтла | open | действует |
| animedia.icu (animedia-01) | 2bb2091 | **app**, sha ≠ выпуску | **404** | open | витрина — да, обработчик — нет |
| an1meg0.site (animego-04, семейство AnimeGo) | — | своё | — | — | каталог — симлинк на снимок animedia-02; поиск «соник» отдаёт «Соник Прайм». Не менялся: другое семейство |

Прочие источники запуска: `animedia-01.service`/`animedia-02.service`
(`/srv/lords/animedia-0X/current/serve.py`, порты 9105/9106) живы, nginx на них
не ведёт (ссылки только в `.bak` 10.09), данные сайтов не пишут. `nova-daily-
refresh` имеет право записи в `/srv/animedia-space/data` (drop-in), код туда не
пишет. cron не используется.

## Постоянное исправление

* Сайт: `src/anime_admission.py` — одно правило (admit 7573 / review 87 /
  exclude 230 на снимке 2026-10-05) на импорте (обработчик), в реестре серий,
  популярном, расписании, карте и на витрине (каталог, поиск, «похожее»,
  топ, лента). Перечень review/exclude с причиной — `<site>-admission.json`.
  Ничего не удаляется; страницы вне допуска — 200 + `noindex, follow`.
* Обработчик: допуск и карта — обязательные шаги (код 3), запуск не из
  `current` — код 4, замок `.update.lock` — код 75; отчёт несёт `updater`,
  `required_steps`, `result`, `admission.counts`. `/healthz` — блок `updater`.
* Фабрика: `factory/cell/updater_units.py`; `promote` ставит юнит и таймер
  обработчика из `current/deploy/` (белый список, `.bak`, `enable --now`);
  предпроверка до прогрева; этап `updater_failed`; `factory cell
  updater-check`. Реестр: `runtime.updater` у animedia-01/02.
* Новый сайт: `docs/NEW_ANIMEDIA_SITE.md`.

## Результаты проверки

* Первый прогон обработчика на новом коде: space 07:50–07:56, icu 08:03–08:10 —
  `result: ok`, `required_steps` admission/sitemap `ok`, `matches_current: true`,
  admit 7738 / review 89 / exclude 238. icu: карта сайта впервые 200 (7743 адреса),
  строка Sitemap в robots.txt, файл допуска. Повторные прогоны (space 08:00,
  icu 08:03, 08:23) — то же, дублей событий нет (147/147, 2690/2690), событий
  вне допуска нет. За окно наблюдения поставщик серий не догружал: случай
  «серии выросли у постороннего» на живых данных НЕ ВСТРЕТИЛСЯ, держится
  проверкой `checks/updater_conformity.py`.
* `/healthz` различает прогон старым кодом: сразу после выпуска
  `result: legacy` / `same_release: false`, после первого прогона — `consistent: true`.
* Публичная приёмка (главная, лента, каталог, поиск, карточки, «похожее»,
  редакционные тексты, индексация, карта, Метрика, healthz): space 20/20 на
  b7cbd95; icu 19/19 на d1079bd и на d6622bc. Плеер (браузер, REAL_PLAYBACK):
  3/3 на каждом выпуске.
* Скорость space, медиана из 5: главная 0.31 → 0.25 с, подборки 0.49 → 0.10,
  карточка 0.23 → 0.12, серия 0.17 → 0.10; приёмка 20/20, плеер 3/3 на 857cf8c.
* Скорость icu, медиана из 5 через домен: главная 1.63 → 0.91 с, каталог 1.58 →
  0.31, подборки 1.53 → 0.30, карточка 2.59 → 0.19, серия 1.06 → 0.13.

## Осталось / открыто

* Корневой реестр исполнителя не знает lords-08/09 (заведены ночью после
  fcadbbb); следующий пакет собирать из коммита, где они есть.
* `freeze-package.py` пишет в опись ветку общего дерева, а не ветку коммита
  (`branch: claude/indexing-operation-02` при коммите из другой ветки).
* `tools/relock.py --write` (icu) стирает verified_against/repo_path/origin/note.
* `factory cell updater-check` установленной копии 2026-10-06 08:5x: обе
  Animedia согласованы, код 0.
* Ветка фабрики `claude/animedia-updater-units-01` не влита в общую линию:
  следующая переустановка исполнителя из общего дерева без неё снимет
  установку обработчиков. Влить — решение Архитектора/фабричной сессии.
* animedia.space: release-manifest объявляет `…-animedia-02`, рантайм отдаёт
  `…-animedia-space` в build-id; приёмка исполнителя проходит.
* `nova_publish.это_аниме` (общий производитель) не менялся: удаление
  admission+origin на источнике убрало бы 230 записей из каталогов и дало
  массовые 404; сайты применяют правило сами. Решение — за Архитектором.
* an1meg0.site (AnimeGo) — сообщить владельцу семейства.
