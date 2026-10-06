# Обращение в Namecheap: serverHold на ЧЕТЫРЁХ доменах

Готовый текст. Причину снятия не предполагаем — её должен назвать регистратор.

## Что подтверждено измерением

Запрос WHOIS к реестрам `whois.nic.site` и `whois.nic.space`, 2026-09-28:

```
Domain Name: lordserials22.site        Domain Name: lordserials22.space
Registrar: NameCheap, Inc.             Registrar: NameCheap, Inc.
Creation Date: 2026-09-22T06:57:03Z    Creation Date: 2026-09-22T06:57:03Z
Updated Date:  2026-09-27T06:58:05Z    Updated Date:  2026-09-27T06:58:05Z
Name Server: paris.ns.cloudflare.com   Name Server: paris.ns.cloudflare.com
Name Server: piers.ns.cloudflare.com   Name Server: piers.ns.cloudflare.com
Domain Status: serverHold              Domain Status: serverHold
Domain Status: clientTransferProhibited
```

Разрешение имени у трёх независимых резолверов (системного, `8.8.8.8`,
`1.1.1.1`) — `NXDOMAIN`. `serverHold` исключает домен из зоны TLD, поэтому ни
записи в Cloudflare, ни смена NS на результат не влияют. NS назначены верно и
совпадают с рабочими доменами того же аккаунта — **менять их не нужно**.

## Перепроверка 2026-10-06 — ограничение НЕ снято

Повторный запрос к тем же реестрам (порт 43, прямой сокет), выполнен в ночь
на 6 октября:

```
Domain Name: lordserials22.site        Domain Name: lordserials22.space
Creation Date: 2026-09-22T06:57:03Z    Creation Date: 2026-09-22T06:57:03Z
Updated Date:  2026-09-27T06:58:05Z    Updated Date:  2026-09-27T06:58:05Z
Registry Expiry: 2027-09-22            Registry Expiry: 2027-09-22
Registrar: NameCheap, Inc.             Registrar: NameCheap, Inc.
Name Server: paris.ns.cloudflare.com   Name Server: paris.ns.cloudflare.com
Name Server: piers.ns.cloudflare.com   Name Server: piers.ns.cloudflare.com
Domain Status: serverHold              Domain Status: serverHold
Domain Status: clientTransferProhibited Domain Status: clientTransferProhibited
```

Что из этого следует и чего НЕ следует:

* домены **зарегистрированы**, срок до 2027-09-22, NS назначены верно и
  совпадают с рабочими доменами того же аккаунта;
* `serverHold` на месте, `Updated Date` не менялся с 27 сентября — то есть за
  девять дней ограничение не снималось и не переназначалось;
* `NXDOMAIN` у резолверов — СЛЕДСТВИЕ этого статуса, а не самостоятельный
  факт. Сам по себе NXDOMAIN доказывает только отсутствие доступного
  разрешения имени на момент проверки и статуса регистрации не устанавливает:
  регистрацию подтверждает WHOIS реестра, и он её подтверждает.

Причину `serverHold` реестр не раскрывает — её обязан назвать регистратор.
Обращение ниже готово к отправке; отправка остаётся за владельцем.

## Два НОВЫХ домена ушли под то же ограничение — 2026-10-06

Это не повторение прежней находки, а новые домены и новая дата. WHOIS
`whois.nic.site` (прямой сокет, порт 43), запрос 2026-10-06 около 12:05 UTC:

```
Domain Name: lordserial101.site          Domain Name: lordfilm077.site
Creation Date: 2026-10-05T09:23:30.987Z  Creation Date: 2026-10-05T09:55:51.100Z
Updated Date:  2026-10-05T23:29:34.180Z  Updated Date:  2026-10-05T23:29:37.904Z
Registry Expiry: 2027-10-05              Registry Expiry: 2027-10-05
Registrar: NameCheap, Inc.               Registrar: NameCheap, Inc.
Name Server: paris.ns.cloudflare.com     Name Server: paris.ns.cloudflare.com
Name Server: piers.ns.cloudflare.com     Name Server: piers.ns.cloudflare.com
Domain Status: serverHold                Domain Status: serverHold
Domain Status: clientTransferProhibited   Domain Status: clientTransferProhibited
Domain Status: addPeriod                 Domain Status: addPeriod
```

Чем это измерено, кроме WHOIS: авторитетный сервер зоны `.site`
(`ns.trs-dns.com`) отвечает `NXDOMAIN` по обоим именам — делегирование снято
удержанием, хотя NS в реестре прежние и верные.

**Важное для разговора с регистратором:** утром 2026-10-06 около 02:30 MSK оба
домена разрешались нормально — авторитетный ответ Cloudflare давал
`A 45.131.182.225`, а `www.lordserial101.site` отвечал `CNAME` на apex. То есть
удержание наложено в промежутке, и его отметка (`Updated Date` 23:29 UTC
2026-10-05) совпадает с этим промежутком. Домены зарегистрированы сутками
ранее, 2026-10-05, и оплачены до 2027-10-05.

Итого под `serverHold` **четыре** домена одного аккаунта: lordserials22.site,
lordserials22.space (с 2026-09-27) и lordserial101.site, lordfilm077.site
(с 2026-10-05). Совпадение по регистратору и по статусу — повод спросить о
причине ОДНИМ обращением, а не четырьмя.

## Текст обращения

> Subject: serverHold on four domains (lordserials22.site, lordserials22.space,
> lordserial101.site, lordfilm077.site)
>
> Hello,
>
> Four domains registered with Namecheap are currently in `serverHold` status
> according to the registry WHOIS:
>
> * lordserials22.site  — registered 2026-09-22, hold recorded 2026-09-27
> * lordserials22.space — registered 2026-09-22, hold recorded 2026-09-27
> * lordserial101.site  — registered 2026-10-05, hold recorded 2026-10-05 23:29 UTC
> * lordfilm077.site    — registered 2026-10-05, hold recorded 2026-10-05 23:29 UTC
>
> The last two resolved normally a few hours before the hold was recorded, so
> the change is recent.
>
> All four have the correct Cloudflare name servers assigned
> (paris.ns.cloudflare.com, piers.ns.cloudflare.com), and all four resolve as
> NXDOMAIN because `serverHold` removes them from the TLD zone.
>
> Could you please tell me:
>
> 1. the exact reason the hold was applied to these four domains, and whether
>    it is the same reason for all of them;
> 2. what needs to be done on my side to have it lifted;
> 3. the expected time frame once that is done.
>
> If the hold is related to registrant contact verification, please resend the
> verification message to the registrant address on file and confirm which
> address that is.
>
> Thank you.

## Как проверить результат

```bash
dig NS lordserials22.site   @8.8.8.8 +noall +answer
dig NS lordserials22.space  @8.8.8.8 +noall +answer
dig NS lordserial101.site   @8.8.8.8 +noall +answer
dig NS lordfilm077.site     @8.8.8.8 +noall +answer
```

Ожидаемый ответ после снятия: статус `NOERROR` и та же пара NS. Пока в ответе
`NXDOMAIN`, ограничение не снято.

## Что готово к моменту снятия

| | lordserials22.site | lordserials22.space |
| --- | --- | --- |
| site_id | lords-06 | lords-07 |
| репозиторий | `sbc-create/site-lordserials22-site` | `sbc-create/site-lordserials22-space` |
| выпуск установлен | `fba2912def9a` | `34b034290f8f` |
| проверен локально | главная 200, 113 813 Б, 84 карточки | главная 200, 115 474 Б, 84 карточки |
| метка выпуска | `fba2912def9a-lords-06` | `34b034290f8f-lords-07` |
| индексация | `noindex, nofollow` | `noindex, nofollow` |
| счётчик в разметке | 113109084 | 113109085 |
| проект Topvisor | 33762569 | 33762590 |

Локальная проверка проводилась на КОПИИ дерева выпуска, боевое не изменялось.
В копию добавлялась настройка плеера `config/player.json` — ровно тот файл
`/srv/lords/.frontend/player-lords-0N.json`, который переносит в выпуск штатный
исполнитель. В установленных 28.09 08:36 выпусках его нет, и без него витрина
отказывается стартовать; ближайший выпуск это исправит сам.

После снятия `serverHold` останется: nginx и сертификат (шаг владельца под
root), затем штатный выпуск через очередь и публичная приёмка.

## Что готово к моменту снятия по двум новым доменам

| | lordserial101.site | lordfilm077.site |
| --- | --- | --- |
| site_id | lords-08 | lords-09 |
| репозиторий | `sbc-create/site-lordserial101-site` | `sbc-create/site-lordfilm077-site` |
| ветка и HEAD | `claude/extract-lordserial101-site` → `c47a59c` | `claude/extract-lordfilm077-site` → `25b57a2` |
| профиль и оформление | `lords-serials` / `lords-serials-v2` | `lords-films` / `lords-films-v2` |
| снимки каталога | `lords-08-{catalog,details}.json` опубликованы | `lords-09-…` опубликованы |
| заготовки nginx | `lords-08.conf`, `lords-08-tls.conf` | `lords-09.conf`, `lords-09-tls.conf` |
| сухой прогон подключения | пройден до конца, включая шаг HTTPS | пройден до конца |
| реестр аналитики | объявлен, `counter_state: planned` | объявлен |
| проект Topvisor | описан в манифесте | описан |
| выпуск | **нет**: CI красный — не выдан publisher ID | **нет**: то же |

Порядок после снятия удержания: publisher ID → зелёный CI → `launch-new-site.sh`
под root (юниты, nginx, сертификат) → выпуск через очередь → публичная приёмка.
Пока удержание в силе, ни один из этих шагов смысла не имеет: certbot не
подтвердит владение именем, которого нет в зоне.
