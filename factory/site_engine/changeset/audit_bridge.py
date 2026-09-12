"""Доставка событий ChangeSet в существующий Audit Ledger.

Второй журнал не заводится. Контур изменений пишет в свой исходящий ящик — в
одной транзакции с изменением состояния — а отсюда события уходят в журнал
аудита с ключом идемпотентности. Доставка «хотя бы один раз», приём —
идемпотентный; дублей в журнале не появляется.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .store import сейчас

БАЗА = os.environ.get("CONTROL_API_BASE", "http://127.0.0.1:8790").rstrip("/")


class LedgerUnavailable(RuntimeError):
    """Журнал аудита недоступен."""


#: Имя личности задаёт ЮНИТ — оно не секрет и потому живёт в конфигурации.
#: Один и тот же код публикует исходящий ящик из двух разных процессов, и
#: общая на двоих личность сделала бы записи в журнале неразличимыми по
#: производителю. Запасного варианта «чужая личность, если своей нет» здесь
#: нет: при сбое конфигурации служба обязана замолчать, а не начать писать от
#: чужого имени.
ПЕРЕМЕННАЯ_ЛИЧНОСТИ = "AUDIT_LEDGER_IDENTITY"


def личность() -> str:
    имя = os.environ.get(ПЕРЕМЕННАЯ_ЛИЧНОСТИ, "").strip()
    if not имя:
        raise LedgerUnavailable(
            f"{ПЕРЕМЕННАЯ_ЛИЧНОСТИ} не задана: юнит обязан назвать свою "
            f"личность в журнале")
    return имя


def _токен() -> str:
    from factory.site_engine.credentials import store as C
    try:
        return C.получить(f"audit-token-{личность()}")
    except C.CredentialError as ош:
        raise LedgerUnavailable(f"{ош.error_code}: {ош.detail}") from ош


def доступен(таймаут: float = 5.0) -> bool:
    """Готов ли журнал принимать записи.

    Проверяется до любого внешнего эффекта: применить изменение и не суметь
    записать о нём — значит получить изменение, которого нет в истории.
    """
    try:
        with urllib.request.urlopen(БАЗА + "/api/v1/audit/health",
                                    timeout=таймаут) as о:
            д = json.loads(о.read() or b"{}")
            return bool(д.get("ready"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return False


ФАЗА_ПО_СОСТОЯНИЮ = {
    "PROPOSED": "PROPOSED", "VALIDATING": "VALIDATED",
    "VALIDATED": "VALIDATED", "AWAITING_APPROVAL": "PROPOSED",
    "APPROVED": "AUTHORIZED", "APPLYING": "STARTED",
    "VERIFYING": "STARTED", "SUCCEEDED": "SUCCEEDED",
    "VALIDATION_FAILED": "FAILED", "REJECTED": "CANCELLED",
    "STALE": "BLOCKED", "EXPIRED": "CANCELLED", "CANCELLED": "CANCELLED",
    "APPLY_FAILED": "FAILED", "ROLLING_BACK": "STARTED",
    "ROLLED_BACK": "ROLLED_BACK", "ROLLBACK_FAILED": "FAILED",
    "MANUAL_INTERVENTION_REQUIRED": "BLOCKED",
}
РЕЗУЛЬТАТ_ПО_СОСТОЯНИЮ = {
    "SUCCEEDED": "SUCCESS", "ROLLED_BACK": "SUCCESS",
    "VALIDATION_FAILED": "FAILURE", "APPLY_FAILED": "FAILURE",
    "ROLLBACK_FAILED": "FAILURE", "MANUAL_INTERVENTION_REQUIRED": "FAILURE",
    "REJECTED": "NOT_APPLICABLE", "CANCELLED": "NOT_APPLICABLE",
    "EXPIRED": "NOT_APPLICABLE", "STALE": "NOT_APPLICABLE",
}


def отправить(запись: dict[str, Any], *, таймаут: float = 15.0) -> dict:
    """Отправить одну запись ящика в журнал аудита."""
    нагрузка = json.loads(запись["payload"])
    состояние = нагрузка.get("to_status") or _состояние_записи(нагрузка)
    цели = нагрузка.get("target_site_ids") or []
    тело = {
        "event_type": запись["event_type"],
        "phase": ФАЗА_ПО_СОСТОЯНИЮ.get(состояние, "OBSERVED"),
        "result": РЕЗУЛЬТАТ_ПО_СОСТОЯНИЮ.get(состояние, "PENDING"),
        # Область SITE требует известного реестру site_id. Набор может
        # касаться нескольких сайтов, поэтому область — FLEET, а цели
        # перечислены в содержимом: подставлять один из нескольких означало бы
        # умолчать об остальных.
        "scope": "SITE" if len(цели) == 1 else "FLEET",
        "site_id": цели[0] if len(цели) == 1 else None,
        "environment": "control-plane",
        "resource_type": нагрузка.get("resource_type"),
        "resource_id": нагрузка.get("resource_id"),
        "resource_owner": "control-plane",
        "correlation_id": нагрузка.get("correlation_id"),
        "causation_id": нагрузка.get("causation_id"),
        "action_id": нагрузка.get("changeset_id"),
        "idempotency_key": запись["idempotency_key"],
        "occurred_at": нагрузка.get("occurred_at") or запись["created_at"],
        "summary": _сводка(запись, нагрузка),
    }
    зап = urllib.request.Request(
        БАЗА + "/api/v1/audit/events", method="POST",
        data=json.dumps(тело, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + _токен()})
    try:
        with urllib.request.urlopen(зап, timeout=таймаут) as о:
            return {"status": о.status, "body": json.loads(о.read() or b"{}")}
    except urllib.error.HTTPError as e:
        тело_ошибки = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 403, 409, 422):
            # Отказ по существу повторять бессмысленно: он не пройдёт и в
            # десятый раз. Такое уходит в отдельный разбор, а не в цикл.
            return {"status": e.code, "permanent": True, "body": тело_ошибки}
        raise LedgerUnavailable(f"HTTP {e.code}: {тело_ошибки}") from e
    except (urllib.error.URLError, OSError) as e:
        raise LedgerUnavailable(str(e)) from e


def _состояние_записи(нагрузка: dict[str, Any]) -> str:
    return нагрузка.get("status") or "PROPOSED"


def _сводка(запись: dict[str, Any], нагрузка: dict[str, Any]) -> str:
    ч = [f"changeset {нагрузка.get('changeset_id', '')[:8]}"]
    if нагрузка.get("from_status"):
        ч.append(f"{нагрузка['from_status']} -> {нагрузка['to_status']}")
    else:
        ч.append(f"создан в состоянии {нагрузка.get('status')}")
    if нагрузка.get("action"):
        ч.append(f"действие {нагрузка['action']}")
    if нагрузка.get("role"):
        ч.append(f"роль {нагрузка['role']}")
    if нагрузка.get("reason"):
        ч.append(f"причина: {нагрузка['reason']}")
    цели = нагрузка.get("target_site_ids") or []
    if цели:
        ч.append(f"целей {len(цели)}")
    return "; ".join(ч)[:900]


def опубликовать(соед, *, предел: int = 500) -> dict[str, Any]:
    """Слить исходящий ящик в журнал аудита."""
    строки = [dict(r) for r in соед.execute(
        "SELECT * FROM changeset_outbox WHERE published_at IS NULL "
        "ORDER BY seq LIMIT ?", (предел,))]
    отправлено = отказов = 0
    for з in строки:
        try:
            итог = отправить(з)
        except LedgerUnavailable as e:
            соед.execute(
                "UPDATE changeset_outbox SET attempts=attempts+1, last_error=? "
                "WHERE seq=?", (str(e)[:300], з["seq"]))
            break  # журнал недоступен — дальше идти бессмысленно
        if итог.get("permanent"):
            соед.execute(
                "INSERT INTO changeset_dlq(changeset_id, event_type, error_code, "
                "reason, attempts, payload, created_at) VALUES(?,?,?,?,?,?,?)",
                (з["changeset_id"], з["event_type"], "LEDGER_REJECTED",
                 str(итог["body"])[:400], з["attempts"] + 1, з["payload"],
                 сейчас()))
            соед.execute("UPDATE changeset_outbox SET published_at=?, "
                         "attempts=attempts+1 WHERE seq=?", (сейчас(), з["seq"]))
            отказов += 1
            continue
        соед.execute("UPDATE changeset_outbox SET published_at=?, "
                     "attempts=attempts+1 WHERE seq=?", (сейчас(), з["seq"]))
        отправлено += 1
    backlog = соед.execute("SELECT count(*) c FROM changeset_outbox "
                           "WHERE published_at IS NULL").fetchone()["c"]
    dlq = соед.execute("SELECT count(*) c FROM changeset_dlq").fetchone()["c"]
    return {"published": отправлено, "rejected": отказов,
            "backlog": backlog, "dlq": dlq}
