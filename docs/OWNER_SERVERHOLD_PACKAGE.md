# Пакет владельцу: четыре домена под `serverHold`

Одна страница: что измерено, что отправить, что требуется от владельца. Полный
разбор и история перепроверок — `docs/NAMECHEAP_SERVERHOLD.md`.

**Обращение НЕ отправлено.** Отправка — действие владельца.

## 1. Статус, подтверждённый реестром

Прямой запрос WHOIS на порт 43 реестра зоны, **2026-10-06 14:08:20 UTC**
(17:08 МСК). Статус домена устанавливает реестр; `NXDOMAIN` у резолверов —
следствие статуса, а не самостоятельный факт.

| домен | site_id | регистратор | статусы реестра | удержание записано | срок регистрации |
| --- | --- | --- | --- | --- | --- |
| lordserials22.site | lords-06 | NameCheap, Inc. | `serverHold`, `clientTransferProhibited` | 2026-09-27T06:58:05Z | до 2027-09-22 |
| lordserials22.space | lords-07 | NameCheap, Inc. | `serverHold`, `clientTransferProhibited` | 2026-09-27T06:58:05Z | до 2027-09-22 |
| lordserial101.site | lords-08 | NameCheap, Inc. | `serverHold`, `clientTransferProhibited`, `addPeriod` | 2026-10-05T23:29:34Z | до 2027-10-05 |
| lordfilm077.site | lords-09 | NameCheap, Inc. | `serverHold`, `clientTransferProhibited`, `addPeriod` | 2026-10-05T23:29:37Z | до 2027-10-05 |

У всех четырёх NS в реестре — `paris.ns.cloudflare.com` и
`piers.ns.cloudflare.com`, те же, что у работающих доменов аккаунта. **NS верны
и менять их не нужно.** `Updated Date` у первых двух не менялся с 27 сентября:
за девять дней удержание не снималось и не переназначалось.

Причину `serverHold` реестр не раскрывает. Назвать её обязан регистратор —
поэтому обращение спрашивает причину, а не предполагает её.

## 2. Готовый текст обращения

Отправлять одним обращением на все четыре домена: совпадают и регистратор, и
статус, и характер (два домена ушли под удержание в один час).

> Subject: serverHold on four domains (lordserials22.site, lordserials22.space,
> lordserial101.site, lordfilm077.site)
>
> Hello,
>
> Four domains registered with Namecheap are in `serverHold` status according to
> the registry WHOIS (checked 2026-10-06 14:08 UTC):
>
> * lordserials22.site — registered 2026-09-22, hold recorded 2026-09-27 06:58 UTC
> * lordserials22.space — registered 2026-09-22, hold recorded 2026-09-27 06:58 UTC
> * lordserial101.site — registered 2026-10-05, hold recorded 2026-10-05 23:29 UTC
> * lordfilm077.site — registered 2026-10-05, hold recorded 2026-10-05 23:29 UTC
>
> All four have the correct Cloudflare name servers assigned
> (paris.ns.cloudflare.com, piers.ns.cloudflare.com) and all four resolve as
> NXDOMAIN, which follows from `serverHold` removing them from the TLD zone.
> The last two resolved normally a few hours before the hold was recorded.
>
> Could you please tell me:
>
> 1. the exact reason the hold was applied to these four domains, and whether it
>    is the same reason for all of them;
> 2. what is required on my side to have it lifted;
> 3. the expected time frame once that is done.
>
> If the hold relates to registrant contact verification, please resend the
> verification message and confirm which registrant address it goes to.
>
> Thank you.

## 3. Что требуется от владельца

| № | действие | почему только владелец |
| --- | --- | --- |
| 1 | **Отправить обращение** регистратору от учётной записи, на которой зарегистрированы домены | обращение к внешней стороне и действие от имени владельца аккаунта |
| 2 | **Ответить регистратору** на запрос подтверждения, если удержание связано с проверкой контактов регистранта | письмо приходит на адрес регистранта, доступа к нему у фабрики нет |
| 3 | **Выдать publisher ID** для lordserial101.site и lordfilm077.site (см. раздел 4) | значение выдаёт поставщик плеера по запросу владельца |
| 4 | После снятия удержания — одна команда под root на каждый домен (раздел 5) | нужен root: юниты, nginx, сертификат |

Фабрика сделать ничего из этого не может и не пытается: список SSH-хостов, зон и
доменов не расширяется по инициативе агента, а обращение к внешней стороне —
решение владельца.

## 4. Publisher ID: у двух новых доменов его НЕТ

Проверено в репозиториях и в хранилище настроек плеера, 2026-10-06:

| домен | `publisher_id_expected` в пакете | `config/player.json` в репозитории | `/srv/lords/.frontend/player-<site_id>.json` |
| --- | --- | --- | --- |
| lordserial101.site (lords-08) | **не объявлен** | нет | нет |
| lordfilm077.site (lords-09) | **не объявлен** | нет | нет |

Пакеты обоих сайтов ссылаются на `secret://cdnvideohub/lords/publisher-id` —
то есть на значение, которое должен выдать поставщик. Пока его нет, CI остаётся
красным и выпуска не будет.

**Значения других площадок сюда не переносятся.** Подтверждённые владельцем ID
принадлежат конкретным доменам и остаются при них:

| домен | publisher ID | статус |
| --- | --- | --- |
| zonafilm.cc | 10374 | подтверждён владельцем, не переносить |
| zonafilm12.site | 10261 | подтверждён владельцем, не переносить |
| lordserials22.info | 10238 | подтверждён владельцем, не переносить |

Один идентификатор на двух витринах уже встречается в сети (`10252` у
animedia.space и zonafilm.space; `10238` у 1lordserials1.online и
lordserials22.info) — это может быть устройством поставщика, а может быть
ошибкой. Пока владелец не сказал, что так и задумано, подставлять чужое
значение новому домену нельзя: при ошибке статистика и права на поток уедут не
туда. Пустое поле — `BLOCKED_INPUT`, а не повод взять соседнее значение.

## 5. Что готово к моменту снятия

| | lords-06 | lords-07 | lords-08 | lords-09 |
| --- | --- | --- | --- | --- |
| выпуск установлен | `fba2912def9a` | `34b034290f8f` | нет | нет |
| заготовки nginx | есть | есть | `lords-08.conf`, `-tls.conf` | `lords-09.conf`, `-tls.conf` |
| снимки каталога | опубликованы | опубликованы | опубликованы | опубликованы |
| сухой прогон подключения | — | — | пройден до конца | пройден до конца |
| что мешает | только удержание | только удержание | удержание **и** publisher ID | удержание **и** publisher ID |

Команда владельца после снятия удержания и выдачи publisher ID:

```bash
sudo bash /home/claude/wt-portable-site-cell-01/automation/host/launch-new-site.sh --site lords-08
sudo bash /home/claude/wt-portable-site-cell-01/automation/host/launch-new-site.sh --site lords-09
```

Порядок обязателен: без имени в зоне `certbot` не подтвердит владение, без
publisher ID CI остаётся красным. Для lords-06 и lords-07 после снятия
удержания нужны nginx и сертификат, затем штатный выпуск через очередь.

## 6. Как проверить, что удержание снято

```bash
python3 /tmp/whois4.py lordserials22.site lordserials22.space lordserial101.site lordfilm077.site
dig NS lordserial101.site @8.8.8.8 +noall +answer
```

Снятие подтверждает ОТСУТСТВИЕ `serverHold` в ответе реестра и `NOERROR` с той
же парой NS у резолвера. Пока в ответе `serverHold` — ограничение в силе, и ни
один шаг запуска смысла не имеет.
