# Обращение в Namecheap: serverHold на двух доменах

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

## Текст обращения

> Subject: serverHold on lordserials22.site and lordserials22.space
>
> Hello,
>
> Two domains registered with Namecheap on 2026-09-22 are currently in
> `serverHold` status according to the registry WHOIS (updated 2026-09-27):
>
> * lordserials22.site
> * lordserials22.space
>
> Both have the correct Cloudflare name servers assigned
> (paris.ns.cloudflare.com, piers.ns.cloudflare.com), and both resolve as
> NXDOMAIN because `serverHold` removes them from the TLD zone.
>
> Could you please tell me:
>
> 1. the exact reason the hold was applied to these two domains;
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
dig NS lordserials22.site  @8.8.8.8 +noall +answer
dig NS lordserials22.space @8.8.8.8 +noall +answer
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
