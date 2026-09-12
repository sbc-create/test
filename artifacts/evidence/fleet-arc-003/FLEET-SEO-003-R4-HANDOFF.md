# FLEET-SEO-003.R4 — что готово со стороны Архитектора

Блокер `ARCHITECTURE_CAPABILITY_MISSING` закрыт. Канонический вид ресурса
существует, адаптер исполним, путь от снимка фактов до набора изменений
пройден целиком на эфемерных хранилищах.

## Ответ на запрос R3

Вы просили выбрать между вариантом А (новый вид ресурса) и вариантом Б
(`seo.audit`). **Принят вариант А без изменения имени.**

`seo.audit` не перегружен намеренно: он описывает результат обследования, а
поле `proposals` внутри него — вложенный список без собственного
идентификатора, версии схемы, ключа идемпотентности и владельца записи.
Повесить на него жизненный цикл значило бы получить сущность, которую нельзя
ни адресовать, ни отклонить отдельно от обследования, внутри которого она
оказалась. Обоснование целиком — `docs/adr/ADR-008-seo-content-proposal.md`.

## Что появилось

| | |
|---|---|
| вид ресурса | `seo.content.proposal` |
| версия схемы | `seo.content.proposal/1.0.0` |
| набор контрактов | `1.3.2` (было `1.3.1`), аддитивно внутри major `v1` |
| `changeset.adapter.seo` | `AVAILABLE` — **вычислено исполнением**, не вписано |
| строгая схема | `contracts/control-plane/1.3.2/schemas/SeoContentProposal.v1.json`, закрыта для неизвестных полей |
| события | `seo.changeset.proposed.v1` (переведён в AVAILABLE), `seo.content.proposal.accepted.v1`, `seo.content.proposal.rejected.v1` |
| соответствие адаптеру | `contracts/control-plane/1.3.2/changeset-resource-map.json` |

## Роли — ровно то разделение, о котором вы просили

| роль | кто |
|---|---|
| владелец домена | `seo` |
| автор содержимого | `qwen`, `actor_type=MODEL` |
| канонический заказчик | `seo` |
| единственный устойчивый писатель | `control-plane` |
| одобряющий | `human_owner` (не совпадает с заказчиком) |
| исполнитель | `control-plane` |
| производитель событий | контур `control-plane`, публикующая личность `changeset-worker` |

Противоречие матрицы устранено: `qwen.proposal.single_writer` изменён с
`qwen` на `control-plane`. Qwen остаётся автором содержимого в новом поле
`content_author`. Это исправление объявления, а не отъём права: политика
`QWEN_PERSISTENT_WRITER=NO` действовала и в 1.3.1.

## Как подавать предложение

Поверхность **внутренняя**: отдельного HTTP-маршрута нет намеренно, и
`NOT_APPLICABLE` здесь — честный ответ, а не пропуск. Предложение подаётся
служебным контуром:

```python
from factory.site_engine.seo_authoring.service import (
    ArtifactStore, SeoProposalService)
from factory.site_engine.changeset import store as CS
from factory.site_engine.changeset.registry_client import RegistryClient

соед = CS.открыть()                     # каноническое хранилище наборов
служба = SeoProposalService(соед, реестр=RegistryClient(),
                            артефакты=ArtifactStore())
итог = служба.принять(заявка, requester_service="seo",
                      actor_id="service:seo", actor_type="SERVICE")
# -> {"proposal_id": ..., "changeset_id": ..., "idempotent_replay": False}
```

Обязательные поля заявки — 19; перечень и правила в
`factory/site_engine/seo_authoring/schema.py` и в схеме набора.

**Четыре поля сервер выводит сам** и присланные значения только сверяет:
`target_environment`, `owner_service`, `audience`, `site_kind`. Расхождение —
отказ `DERIVED_FIELD_MISMATCH`, а не переопределение. Назначить себе
окружение или владельца нельзя.

**Три поля сервер вычисляет** и в запросе не принимает вовсе:
`proposal_id`, `changeset_id`, `accepted_at`, `resource_version`.

## Что отказывает и с каким кодом

Восемнадцать кодов в `error-catalog.json`. Самые вероятные у вас:

| код | когда |
|---|---|
| `SOURCE_SNAPSHOT_STALE` | факты реестра изменились после составления текста |
| `ARTIFACT_DIGEST_MISMATCH` | отпечаток содержимого не совпал с заявленным |
| `SITE_ID_UNKNOWN` | витрина неизвестна; домен ключом не является |
| `ACTOR_SPOOFED` | `requested_by` не совпал с опознанной службой |
| `DERIVED_FIELD_MISMATCH` | попытка назначить выводимое поле |
| `PRODUCTION_TARGET_DENIED` | цель вне `test` и `non-production` |
| `MODEL_DURABLE_WRITE_DENIED` | подача от имени модели |
| `IDEMPOTENCY_CONFLICT` | тот же ключ с другим содержимым |
| `PAYLOAD_REJECTED` | в свободном поле путь, команда, адрес или SQL |

Повтор с тем же ключом и тем же содержимым возвращает те же
`proposal_id` и `changeset_id` с `idempotent_replay: true`.

## Точные сведения

```
source_repository   https://github.com/sbc-create/test.git
source_branch       claude/arc-seo-canonical-proposal-003
source_commit       529ada7cc15ee44973a7c8793e0072d3bce182de
contract_version    1.3.2
contract_artifact   e9a22609bd98528187df129bf5a5a92a4f5bc4a81fbab101a9c9606f604c6fa7
resource_kind       seo.content.proposal
adapter_status      AVAILABLE
evidence_path       artifacts/evidence/fleet-arc-003/
```

## Воспроизведение

```
PYTHONPATH=. python3 contracts/control-plane/build_132.py
python3 contracts/control-plane/validate_bundle.py 1.3.2 1.3.1
ARC003_RELEASE=$PWD PYTHONPATH=$PWD python3 tests/arc_seo/run_arc003.py
ARC003_RELEASE=$PWD PYTHONPATH=$PWD python3 tests/arc_seo/rollback_cycle.py
```

Прогон поднимает свой экземпляр Control API на кандидатском наборе, работает
на эфемерных хранилищах и сверяет канонические Registry, ChangeSet Store и
Audit Ledger до и после.

## Что осталось ограниченным

* **Применение в production выключено.** `AUTONOMOUS_PRODUCTION_APPLY`
  остаётся `DISABLED`; разрешены `test` и `non-production`. Предложение на
  production-витрину отвергается до эффекта.
* **Набор 1.3.2 не выложен.** Обслуживаемым остаётся 1.3.1; кандидат
  существует в ветке и проверен на эфемерном рантайме. Выкладка — отдельное
  решение владельца.
* **Одобрение требует службы подписи**, которая читает каноническое
  состояние. В эфемерном контуре она не участвует, поэтому стадии
  `approve`/`apply` в наших прогонах доказаны как *заблокированные без
  одобрения*, а исполнимость адаптера — его собственным полным циклом
  (наблюдение, план, сухой прогон, применение, проверка, откат).
* **Живой Qwen не вызывался ни разу.** Черновик порождает детерминированная
  модель; счётчики живых обращений и загрузок модели равны нулю и
  проверяются.
