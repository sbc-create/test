# serverHold у lordserials22.space и lordserials22.site: измеренное и готовое обращение

Составлено 2026-10-10 по данным RDAP реестра и регистратора. Догадок о причине
здесь нет: причина нигде не опубликована, и единственный путь её узнать —
запрос регистратору. Домены не менялись, обход блокировки не делался.

## 1. Что измерено

| факт | lordserials22.space | lordserials22.site |
| --- | --- | --- |
| статус в реестре | `server hold`, `client transfer prohibited` | `server hold`, `client transfer prohibited` |
| регистрация | 2026-09-22T06:57:03.200Z | 2026-09-22T06:57:03.075Z |
| последнее изменение | **2026-09-27T06:58:05.277Z** | **2026-09-27T06:58:05.278Z** |
| срок регистрации до | 2027-09-22 | 2027-09-22 |
| NS в реестре | paris.ns.cloudflare.com, piers.ns.cloudflare.com | те же |
| DNS сейчас | имя не разрешается (A и AAAA) | имя не разрешается (A и AAAA) |

Три вывода из этих чисел, и только они:

* **`serverHold` ставит РЕЕСТР, а не регистратор.** У регистратора в его же
  RDAP (`rdap.namecheap.com`) у обоих домен числится только
  `client transfer prohibited`; `server hold` виден лишь в реестровом RDAP
  (`rdap.radix.host`). Поэтому снять его регистратор может только обращением в
  реестр.
* **Это одно действие по двум доменам.** Метки последнего изменения отличаются
  на одну миллисекунду — 2026-09-27T06:58:05.277Z и .278Z, то есть оба домена
  обработаны одной операцией через пять дней после регистрации.
* **Срок регистрации тут не при чём**: оплачено до 22 сентября 2027 года,
  делегирование в реестре не снято (NS на месте), а недоступность вызвана тем,
  что при `serverHold` реестр не публикует домен в зоне TLD.

## 2. Кому писать

| роль | кто | адрес |
| --- | --- | --- |
| регистратор (точка обращения регистранта) | **NameCheap, Inc.**, IANA ID 1068 | кабинет namecheap.com → Support; почта `support@namecheap.com` |
| служба жалоб регистратора | та же | `abuse@namecheap.com`, +1.9854014545 |
| реестр TLD (ставит и снимает `serverHold`) | Radix — RDAP `rdap.radix.host`; в условиях RDAP назван оператор реестра **Tucows Registry** | напрямую регистранту обычно не отвечает: эскалацию делает регистратор |

Контакты регистранта в RDAP скрыты сервисом приватности
(`withheldforprivacy.com`), поэтому уведомление реестра или регистратора, если
оно было, ушло на адрес владельца в кабинете NameCheap, а не на публичный
адрес сайта. Проверить этот ящик и раздел уведомлений кабинета — то, чего я
сделать не могу: доступа к кабинету у фабрики нет (в `inventory/dns-zones.yaml`
зон и токенов нет вовсе).

## 3. Готовое обращение (одно на оба домена)

Тема: `serverHold on lordserials22.space and lordserials22.site — reason and exact conditions to lift`

```
Hello,

Two domains in my NameCheap account are in registry status serverHold and are
therefore not resolving:

  lordserials22.space
  lordserials22.site

Measured facts (registry RDAP, 2026-10-10):
  - status: serverHold + clientTransferProhibited on both;
  - registered 2026-09-22T06:57:03Z, both domains;
  - last changed 2026-09-27T06:58:05Z, both domains within one millisecond,
    which indicates a single action applied to both;
  - nameservers unchanged (paris.ns.cloudflare.com, piers.ns.cloudflare.com);
  - paid through 2027-09-22, so this is not an expiration issue;
  - registrar RDAP shows only clientTransferProhibited, so the hold is applied
    at the registry level.

I am the registrant and I am not asking you to lift anything without cause. I
am asking for the facts I cannot see:

  1. What is the reason for the serverHold on these two domains, and who
     requested it (registry, registrar, or a third-party complaint)?
  2. Was any notice sent, to which address and on what date? I want to make
     sure it was not lost in the privacy-service forwarding.
  3. What are the exact conditions and steps required to lift the hold, and is
     there a case or ticket number I should reference?
  4. If the cause is registrant data verification or any document request,
     please tell me exactly which data or document is required, and I will
     provide it immediately.
  5. If the cause is a complaint about content, please forward the complaint
     text or its case number so that I can respond to it specifically.

Both domains serve the same project and were set up identically, so the same
answer most likely applies to both. Please answer for each domain explicitly
anyway.

Thank you,
<имя владельца, как в аккаунте NameCheap>
Account: <логин NameCheap>
```

## 4. Чего в этом обращении сознательно нет

* утверждений о причине — ни «жалоба правообладателя», ни «проверка данных»:
  ни одно из этих слов в RDAP и WHOIS не встречается, и писать их означало бы
  подсказывать поддержке вывод вместо вопроса;
* просьбы «снять как можно быстрее» без оснований — снятие `serverHold`
  делает реестр по своей процедуре, и спорить с ней бессмысленно, пока
  неизвестна причина;
* любых попыток обойти блокировку (смена NS, перенос домена, зеркало на другом
  имени) — это запрещено правилами проекта и ухудшило бы положение.

## 5. Что от этого обращения зависит

До снятия `serverHold` оба сайта остаются недоступными ПУБЛИЧНО, но их
внутренняя готовность проверена отдельно (см. журнал за 10 октября): сборка,
проверки ячейки, маршруты карточек и серий, домен и счётчик в разметке. То
есть после снятия ограничения выпуск не упирается ни во что, кроме самой
доступности домена.
