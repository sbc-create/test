"""Модель ChangeSet: состояния, переходы, роли, классы риска.

Машина состояний описана таблицей, а не расставленными по коду проверками.
Разница принципиальная: таблицу можно прочитать целиком и увидеть, какие
переходы существуют, а рассыпанные по обработчикам `if` создают ощущение
полноты, которого нет — запрещённый переход обнаруживается только тогда,
когда кто-то его совершит.

Клиент никогда не записывает состояние напрямую. Он просит выполнить
ДЕЙСТВИЕ, а состояние — следствие, вычисленное сервером.
"""
from __future__ import annotations

from typing import NamedTuple

SCHEMA_VERSION = "fleet-changeset/1.0.0"

# --- состояния ---------------------------------------------------------------

#: Основная цепочка.
PROPOSED = "PROPOSED"
VALIDATING = "VALIDATING"
VALIDATED = "VALIDATED"
AWAITING_APPROVAL = "AWAITING_APPROVAL"
APPROVED = "APPROVED"
APPLYING = "APPLYING"
VERIFYING = "VERIFYING"
SUCCEEDED = "SUCCEEDED"

#: Боковые состояния.
VALIDATION_FAILED = "VALIDATION_FAILED"
REJECTED = "REJECTED"
STALE = "STALE"
EXPIRED = "EXPIRED"
CANCELLED = "CANCELLED"
APPLY_FAILED = "APPLY_FAILED"
ROLLING_BACK = "ROLLING_BACK"
ROLLED_BACK = "ROLLED_BACK"
ROLLBACK_FAILED = "ROLLBACK_FAILED"
MANUAL_INTERVENTION_REQUIRED = "MANUAL_INTERVENTION_REQUIRED"

СОСТОЯНИЯ = (
    PROPOSED, VALIDATING, VALIDATED, AWAITING_APPROVAL, APPROVED, APPLYING,
    VERIFYING, SUCCEEDED, VALIDATION_FAILED, REJECTED, STALE, EXPIRED,
    CANCELLED, APPLY_FAILED, ROLLING_BACK, ROLLED_BACK, ROLLBACK_FAILED,
    MANUAL_INTERVENTION_REQUIRED,
)

#: Состояния, из которых выхода нет. Попытка продолжить из терминального —
#: не ошибка клиента, а признак того, что кто-то держит устаревшую картину.
ТЕРМИНАЛЬНЫЕ = frozenset({
    SUCCEEDED, REJECTED, CANCELLED, ROLLED_BACK, EXPIRED,
    MANUAL_INTERVENTION_REQUIRED,
})

#: Состояния, в которых набор изменений занимает замок целей.
АКТИВНЫЕ = frozenset({
    VALIDATING, VALIDATED, AWAITING_APPROVAL, APPROVED, APPLYING, VERIFYING,
    ROLLING_BACK,
})

# --- роли --------------------------------------------------------------------

PROPOSER = "proposer"
VALIDATOR = "validator"
APPROVER = "approver"
EXECUTOR = "executor"
OPERATOR = "operator"

#: Единственный владелец записи по ресурсу. Ни одна служба не меняет чужой
#: ресурс напрямую — она предлагает изменение, а применяет владелец.
ЕДИНСТВЕННЫЙ_ПИСАТЕЛЬ = {
    "site.identity": "architect",
    "changeset": "control-plane",
    "template.structure": "templates",
    "template.build": "templates",
    "content.catalog": "content",
    "content.ratings": "content",
    "seo.text": "seo",
    "seo.fields": "seo",
    "monitoring.observation": "monitoring",
    "backup.snapshot": "backup",
    "integration.provisioning": "architect",
    # Внешние ресурсы провайдеров. Единственный писатель — Integration
    # Provisioner на стороне архитектора: два писателя одной DNS-зоны или
    # одного счётчика означают гонку, в которой побеждает последний
    # записавший, а узнают об этом по расхождению статистики.
    "dns.record_set": "architect",
    "tls.certificate": "architect",
    "analytics.counter": "architect",
    "seo.project": "architect",
    # Ресурс существует только для испытаний механизма.
    "fake.resource": "control-plane",
}

#: Что каждая служба вправе делать в контуре изменений. Qwen — только
#: наблюдение и предложение: он модель, и исполнительных полномочий не
#: получает ни при каких условиях этой версии.
ПРАВА = {
    "architect": {PROPOSER, VALIDATOR, APPROVER, EXECUTOR, OPERATOR},
    "control-plane": {VALIDATOR, EXECUTOR},
    "templates": {PROPOSER},
    "content": {PROPOSER},
    "seo": {PROPOSER},
    "monitoring": {PROPOSER},
    "backup": {PROPOSER, EXECUTOR},
    "human_owner": {APPROVER, OPERATOR},
    "qwen": {PROPOSER},
}

#: Действия, недоступные актору типа MODEL ни при какой роли.
ЗАПРЕЩЕНО_МОДЕЛИ = frozenset({"approve", "apply", "rollback", "grant_authority"})

# --- классы риска ------------------------------------------------------------

RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
КЛАССЫ_РИСКА = (RISK_LOW, RISK_MEDIUM, RISK_HIGH)

#: Какие операции считаются необратимыми. В первой версии они блокируются:
#: механизм отката ещё не проверен на них, а необратимое изменение без
#: доказанного отката — это изменение, которое некому отменить.
НЕОБРАТИМЫЕ_ОПЕРАЦИИ = frozenset({"delete", "purge", "destroy", "truncate"})

ОПЕРАЦИИ = frozenset({"create", "update", "patch", "publish", "rollback"})


# --- таблица переходов -------------------------------------------------------

class Переход(NamedTuple):
    """Одно разрешённое изменение состояния.

    `роли` — кто вправе его инициировать. `таймаут` — сколько состояние
    вправе длиться до вмешательства (0 означает «не ограничено временем»).
    `компенсируемо` отвечает на вопрос, можно ли отменить последствия.
    """
    действие: str
    из_состояния: str
    в_состояние: str
    роли: frozenset[str]
    предусловия: tuple[str, ...]
    постусловия: tuple[str, ...]
    таймаут: int
    повторов: int
    событие: str
    компенсируемо: bool


def _п(действие, откуда, куда, роли, пред=(), пост=(), таймаут=0, повторов=0,
       событие="", компенсируемо=False) -> Переход:
    return Переход(действие, откуда, куда, frozenset(роли), пред, пост,
                   таймаут, повторов, событие, компенсируемо)


ПЕРЕХОДЫ: tuple[Переход, ...] = (
    _п("validate", PROPOSED, VALIDATING, {VALIDATOR},
       пред=("changeset существует", "не истёк"),
       пост=("захвачен замок целей",),
       таймаут=120, повторов=2, событие="changeset.validating.v1",
       компенсируемо=True),
    _п("validate_ok", VALIDATING, VALIDATED, {VALIDATOR},
       пред=("схема payload верна", "все site_id известны реестру",
             "операция обратима", "plan_hash вычислен",
             "план проверки и план отката построены", "dry-run без эффектов"),
       пост=("plan_hash зафиксирован", "base_registry_version зафиксирована"),
       таймаут=0, событие="changeset.validated.v1", компенсируемо=True),
    _п("validate_fail", VALIDATING, VALIDATION_FAILED, {VALIDATOR},
       пред=("нарушено хотя бы одно правило валидации",),
       пост=("замок освобождён", "причина записана"),
       событие="changeset.validation_failed.v1"),
    _п("request_approval", VALIDATED, AWAITING_APPROVAL, {PROPOSER, VALIDATOR},
       пред=("состояние VALIDATED",),
       пост=("срок действия одобрения назначен",),
       таймаут=86400, событие="changeset.approval_requested.v1",
       компенсируемо=True),
    _п("approve", AWAITING_APPROVAL, APPROVED, {APPROVER},
       пред=("одобряющий не совпадает с предложившим",
             "plan_hash совпадает с одобряемым",
             "цели совпадают", "policy_version актуальна", "не истёк"),
       пост=("одобрение связано хэшем с планом и целями",),
       таймаут=0, событие="changeset.approved.v1", компенсируемо=True),
    _п("reject", AWAITING_APPROVAL, REJECTED, {APPROVER},
       пред=("одобряющий вправе отклонять",),
       пост=("замок освобождён",),
       событие="changeset.rejected.v1"),
    _п("apply", APPROVED, APPLYING, {EXECUTOR},
       пред=("одобрение действительно", "план не устарел",
             "реестр той же версии", "отпечаток цели совпадает",
             "аренда получена", "журнал аудита доступен"),
       пост=("отпечаток до изменения сохранён", "намерение записано в журнал"),
       таймаут=600, повторов=0, событие="changeset.applying.v1",
       компенсируемо=True),
    _п("applied", APPLYING, VERIFYING, {EXECUTOR},
       пред=("адаптер сообщил о завершении",),
       пост=("результат применения сохранён",),
       таймаут=300, повторов=2, событие="changeset.applied.v1",
       компенсируемо=True),
    _п("apply_fail", APPLYING, APPLY_FAILED, {EXECUTOR},
       пред=("адаптер отказал",), пост=("причина записана",),
       событие="changeset.apply_failed.v1", компенсируемо=True),
    _п("verify_ok", VERIFYING, SUCCEEDED, {EXECUTOR},
       пред=("наблюдаемое состояние совпало с ожидаемым",),
       пост=("замок освобождён", "отпечаток после изменения сохранён"),
       событие="changeset.succeeded.v1"),
    _п("verify_fail", VERIFYING, ROLLING_BACK, {EXECUTOR},
       пред=("наблюдаемое состояние не совпало",),
       пост=("запущена компенсация",),
       таймаут=600, повторов=2, событие="changeset.verify_failed.v1",
       компенсируемо=True),
    _п("rollback_start", APPLY_FAILED, ROLLING_BACK, {EXECUTOR, OPERATOR},
       пред=("эффект обратим",), пост=("запущена компенсация",),
       таймаут=600, повторов=2, событие="changeset.rolling_back.v1",
       компенсируемо=True),
    _п("rollback_ok", ROLLING_BACK, ROLLED_BACK, {EXECUTOR},
       пред=("восстановленное состояние проверено",),
       пост=("замок освобождён",),
       событие="changeset.rolled_back.v1"),
    _п("rollback_fail", ROLLING_BACK, ROLLBACK_FAILED, {EXECUTOR},
       пред=("компенсация не удалась",),
       пост=("прерыватель разомкнут",),
       событие="changeset.rollback_failed.v1"),
    _п("escalate", ROLLBACK_FAILED, MANUAL_INTERVENTION_REQUIRED,
       {EXECUTOR, OPERATOR},
       пред=("автоматические попытки исчерпаны",),
       пост=("критическое событие записано", "замок удержан до вмешательства"),
       событие="changeset.manual_intervention_required.v1"),
    _п("mark_stale", VALIDATED, STALE, {VALIDATOR, EXECUTOR},
       пред=("обнаружено расхождение с наблюдаемым состоянием",),
       пост=("одобрение аннулировано",), событие="changeset.stale.v1",
       компенсируемо=True),
    _п("mark_stale_approved", APPROVED, STALE, {VALIDATOR, EXECUTOR},
       пред=("обнаружено расхождение после одобрения",),
       пост=("одобрение аннулировано", "требуется новая валидация"),
       событие="changeset.stale.v1", компенсируемо=True),
    _п("revalidate", STALE, VALIDATING, {VALIDATOR},
       пред=("запрошена повторная валидация",),
       пост=("прежнее одобрение недействительно",),
       таймаут=120, повторов=2, событие="changeset.validating.v1",
       компенсируемо=True),
    _п("expire", AWAITING_APPROVAL, EXPIRED, {VALIDATOR, EXECUTOR, OPERATOR},
       пред=("истёк срок ожидания одобрения",),
       пост=("замок освобождён",), событие="changeset.expired.v1"),
    _п("expire_approved", APPROVED, EXPIRED, {VALIDATOR, EXECUTOR, OPERATOR},
       пред=("истёк срок действия одобрения",),
       пост=("замок освобождён", "одобрение аннулировано"),
       событие="changeset.expired.v1"),
    _п("revalidate_failed", VALIDATION_FAILED, VALIDATING, {VALIDATOR},
       пред=("причина отказа устранена",),
       пост=("прежняя причина сохранена в истории",),
       таймаут=120, повторов=2, событие="changeset.validating.v1",
       компенсируемо=True),
    _п("cancel_failed", VALIDATION_FAILED, CANCELLED, {PROPOSER, OPERATOR},
       пред=("заявка отозвана автором",),
       пост=("замок освобождён",), событие="changeset.cancelled.v1"),
    _п("cancel", PROPOSED, CANCELLED, {PROPOSER, OPERATOR},
       пред=("предложение ещё не применялось",),
       пост=("замок освобождён",), событие="changeset.cancelled.v1"),
    _п("cancel_validated", VALIDATED, CANCELLED, {PROPOSER, OPERATOR},
       пред=("предложение ещё не применялось",),
       пост=("замок освобождён",), событие="changeset.cancelled.v1"),
    _п("cancel_awaiting", AWAITING_APPROVAL, CANCELLED, {PROPOSER, OPERATOR},
       пред=("предложение ещё не применялось",),
       пост=("замок освобождён",), событие="changeset.cancelled.v1"),
)

#: Быстрый указатель: (из_состояния, действие) → переход.
ПО_ДЕЙСТВИЮ = {(п.из_состояния, п.действие): п for п in ПЕРЕХОДЫ}

#: Все состояния, достижимые из данного.
ДОСТИЖИМЫЕ = {}
for _п_ in ПЕРЕХОДЫ:
    ДОСТИЖИМЫЕ.setdefault(_п_.из_состояния, set()).add(_п_.в_состояние)


def разрешён(из_состояния: str, в_состояние: str) -> bool:
    return в_состояние in ДОСТИЖИМЫЕ.get(из_состояния, set())


def переход(из_состояния: str, действие: str) -> Переход | None:
    return ПО_ДЕЙСТВИЮ.get((из_состояния, действие))


def роли_службы(служба: str) -> frozenset[str]:
    return frozenset(ПРАВА.get(служба, set()))
