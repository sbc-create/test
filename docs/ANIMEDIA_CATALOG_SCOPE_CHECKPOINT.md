# CHECKPOINT — ANIMEDIA: состав каталога и согласованность обработчика

Окно «ANIMEDIA — состав каталога». Обновлён 2026-10-05.

## Ветки и коммиты

| Репозиторий | Ветка | Коммит | Состояние |
| --- | --- | --- | --- |
| site-animedia-space | `claude/extract-animedia-space-catalog-scope-01` | `34a1c65` | выложен 16:04 UTC (`animedia-02-code-34a1c656bf9a`) |
| site-animedia-icu | `claude/extract-animedia-icu-catalog-scope-01` | `2bb2091` | выложен 16:20 UTC (`animedia-01-code-2bb209132004`) |
| site-animedia-space | `claude/extract-animedia-space-updater-guard-01` | `f650a57` | CI 37342821705 success; к выпуску |
| site-animedia-icu | `claude/extract-animedia-icu-updater-guard-01` | `d1079bd` | CI 37343042700 success; к выпуску |
| фабрика | `claude/animedia-updater-units-01` | `171a868` (над `05265af`) | к установке исполнителя владельцем |

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

## Осталось / открыто

* Установка исполнителя из `claude/animedia-updater-units-01` — действие
  владельца (root).
* Выпуск `f650a57` (space) и `d1079bd` (icu) очередью после установки.
* `nova_publish.это_аниме` (общий производитель) не менялся: удаление
  admission+origin на источнике убрало бы 230 записей из каталогов и дало
  массовые 404; сайты применяют правило сами. Решение — за Архитектором.
* an1meg0.site (AnimeGo) — сообщить владельцу семейства.
