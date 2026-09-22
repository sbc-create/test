# Owner canary packet — lords-02 только

```text
RELEASE_ID=rel-owner-canary-lords02-20260921-01
MANIFEST_DIGEST=8accb344ae5a20f9e9d629818ab94252c7409a4446f8ae7c0001afbc297331c4
SCOPE=lords-02 (lordserial33.biz) — одна витрина
STATE=PREPARED_NOT_EXECUTED
LIVE_DEPLOY_PERFORMED=0
RESTART_PERFORMED=0
OWNER_CANARY_APPROVAL_ID=<отсутствует — пакет не исполним без него>
```

Пакет подготовлен, но **не исполнен**. Исполнение требует отдельного
`OWNER_CANARY_APPROVAL_ID` и снятия блокирующих условий ниже.

## Почему именно lords-02

Из трёх витрин Lords только у неё объявленное, назначенное и исполняемое
совпадают — `b32438c9…`. lords-03 объявляет `5dd817fe…`, а исполняет
`b32438c9…`; lords-01 исполняет образ, загруженный до миграции рантайма, и по
файлу на диске не определяется. lords-01 и lords-03 этим пакетом не
затрагиваются.

## Что именно выкатывается

Те же байты, что витрина исполняет сейчас: `b32438c9…`, релиз
`20260921T114007Z-89003bb-clean`. Это сознательный выбор. Canary проверяет
**путь выкладки** — preflight, backup, rollback-репетицию, ровно один
перезапуск, постусловия и smoke ×2 — не меняя того, что получает посетитель.
Если путь сломан, это видно без риска для содержимого витрины.

DNS и индексация не меняются: `dns_mutations_allowed=false`,
`indexability_mutations_allowed=false`, `CLOSED → CLOSED`.

## Состав пакета

| Файл | Что доказывает | Состояние |
| --- | --- | --- |
| `manifest.json` | неизменяемый манифест одной витрины | digest `8accb344…`, привязка обязательна |
| `preflight.json` | структура, домен, профиль, артефакт на диске | `ok=true` |
| `service-binding.json` | домен → порт → юнит по nginx и unit-файлам | **`ok=false`** — см. блокер RO-01 |
| `rollback.json` | backup снят, digest сошёлся, восстановление отрепетировано | `1/1/1` |
| `postconditions.json` | ровно один перезапуск, новый PID, `NRestarts+1` | `PASS`, `DUPLICATE_RESTART_COUNT=0` |
| `smoke-1.json`, `smoke-2.json` | два независимых прогона, расхождение = отказ | пройдены в репетиции |
| `LIVE_STATE.json` | измеренное состояние трёх витрин | хост **не в покое** |
| `DEPENDENCY_CHECK.json` | проверка LORDS-CURSOR-WORK-RECONCILIATION-01 | `DEPENDENCY_NOT_CLOSED` |

Репетиция проведена в теневом режиме: `BATCH_PASS`, `lords-02 =
POST_DEPLOY_PASS`, ноль живых мутаций.

## Блокирующие условия — все должны быть сняты владельцем

**BLOCK-1 — зависимость не закрыта.** `P1_DEFECTS_OPEN=1` (не 0), совпадение
по доменам `1 из 3` (не 3), `READY_FOR_LORDS_50_FACTORY=false`. Требуется
решение по OA-1 зависимости.

**BLOCK-2 (RO-01) — реестр называет не тот юнит.** `config/release-registry.json`
объявляет `lords-02.service` (порт 9102), а `lordserial33.biz` маршрутизируется
на порт 9111, который слушает `nova-lords-02.service`. Оба юнита живы, поэтому
ошибка не проявляется отказом: canary перезапустил бы не ту службу, витрина
осталась бы нетронутой, а smoke по домену всё равно бы прошёл — ложный PASS.
Ворота `BLOCKED_SERVICE_BINDING` останавливают прогон до первого перезапуска.
Расширять реестр по своей инициативе запрещено — нужен выбор владельца.

**BLOCK-3 (RO-02) — хост не в покое.** Во время подготовки пакета другой поток
работ мигрировал общий рантайм на по-доменный диспетчер; lords-02
перезапускался дважды. Canary сейчас гонялся бы с чужой выкладкой.

**BLOCK-4 (RO-03) — smoke ×2 по живому домену неисполним.** HTTP к трём доменам
закрыт guard'ом (B-01 зависимости). Поэтому `expected_catalog_revision` и
`expected_details_revision` помечены `UNMEASURED_REQUIRES_HTTP`, а не заполнены
догадкой. Постусловие smoke ×2 на живом домене без этого не выполнимо.

## Порядок исполнения, когда блокеры сняты

1. Подтвердить покой хоста и завершение миграции диспетчера.
2. Привести `config/release-registry.json` к канонической привязке юнитов;
   `service-binding.json` должен дать `ok=true`.
3. Внести три домена Lords в `inventory/network-allowlist.yaml`; перемерить
   `catalog_revision` и `details_revision` и перевыпустить манифест — digest
   изменится, это ожидаемо.
4. Выдать `OWNER_CANARY_APPROVAL_ID`, привязанный к новому digest манифеста и
   ровно к `exact_site_ids=["lords-02"]`.
5. Запустить: `bin/site-factory-release canary --release-id
   rel-owner-canary-lords02-<дата> --manifest … --approval … --live`.
6. При любом отказе — `ROLLBACK_CURRENT_SITE_AND_STOP_BATCH`: восстановление из
   снятого backup и остановка партии. lords-01 и lords-03 не затрагиваются.

## Что этот пакет не утверждает

Он не утверждает, что живой canary прошёл. Он не исполнялся. Все приведённые
`PASS` получены в теневой репетиции и помечены как таковые.
