"""Доставка событий ChangeSet в существующий Audit Ledger.

Второй журнал не заводится. Контур изменений пишет в свой исходящий ящик — в
одной транзакции с изменением состояния — а отсюда события уходят в журнал
аудита с ключом идемпотентности. Доставка «хотя бы один раз», приём —
идемпотентный; дублей в журнале не появляется.
"""
from __future__ import annotations

import json
import os
import time
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
    "APPLIED": "STARTED", "VERIFYING": "STARTED", "VERIFIED": "STARTED",
    "SUCCEEDED": "SUCCEEDED",
    "VALIDATION_FAILED": "FAILED", "REJECTED": "CANCELLED",
    "STALE": "BLOCKED", "EXPIRED": "CANCELLED", "CANCELLED": "CANCELLED",
    "APPLY_FAILED": "FAILED", "ROLLBACK_REQUESTED": "STARTED",
    "ROLLING_BACK": "STARTED",
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


#: Сколько раз позволено сорваться на ВРЕМЕННОЙ ошибке, прежде чем запись
#: уйдёт в очередь недоставленного. Без предела одна неустранимая поломка
#: держала бы ящик в вечной попытке, и отличить её от короткого перебоя было
#: бы нечем.
ПРЕДЕЛ_ОТПРАВОК = 8

#: Первая отсрочка и её потолок. Удвоение — чтобы недоступность журнала не
#: оборачивалась непрерывным потоком одинаковых запросов к нему же.
ОТСРОЧКА_СЕК = 2.0
ПРЕДЕЛ_ОТСРОЧКИ_СЕК = 300.0

#: Версии событий, которые этот выпуск умеет отправлять. Неизвестная версия
#: не пропускается молча: запись, смысла которой отправитель не понимает, —
#: это либо откат выпуска, либо чужая запись, и оба случая требуют разбора.
ИЗВЕСТНЫЕ_ВЕРСИИ_СОБЫТИЙ = frozenset({1})


def версия_события(тип: str) -> int | None:
    """Номер версии из хвоста имени события: changeset.applied.v1 → 1."""
    хвост = тип.rsplit(".", 1)[-1]
    if хвост.startswith("v") and хвост[1:].isdigit():
        return int(хвост[1:])
    return None


def _отсрочка(попыток: int) -> float:
    return min(ОТСРОЧКА_СЕК * (2 ** max(0, попыток)), ПРЕДЕЛ_ОТСРОЧКИ_СЕК)


def _в_очередь_недоставленного(соед, з: dict, код: str, причина: str) -> None:
    соед.execute(
        "INSERT INTO changeset_dlq(changeset_id, event_type, error_code, "
        "reason, attempts, payload, created_at) VALUES(?,?,?,?,?,?,?)",
        (з["changeset_id"], з["event_type"], код, причина[:400],
         з["attempts"] + 1, з["payload"], сейчас()))
    # Запись снимается с очереди отправки: она уже разобрана, и держать её
    # в ящике значило бы пытаться отправить её снова на каждом проходе.
    соед.execute("UPDATE changeset_outbox SET published_at=?, attempts=attempts+1 "
                 "WHERE seq=?", (сейчас(), з["seq"]))


def опубликовать(соед, *, предел: int = 500) -> dict[str, Any]:
    """Слить исходящий ящик в журнал аудита."""
    теперь = time.time()
    строки = [dict(r) for r in соед.execute(
        "SELECT * FROM changeset_outbox WHERE published_at IS NULL "
        "AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
        "ORDER BY seq LIMIT ?", (теперь, предел))]
    отправлено = отказов = отложено = 0
    for з in строки:
        версия = версия_события(з["event_type"])
        if версия not in ИЗВЕСТНЫЕ_ВЕРСИИ_СОБЫТИЙ:
            _в_очередь_недоставленного(
                соед, з, "EVENT_VERSION_UNKNOWN",
                f"версия события {з['event_type']!r} этому выпуску неизвестна")
            отказов += 1
            continue
        try:
            итог = отправить(з)
        except LedgerUnavailable as e:
            попыток = з["attempts"] + 1
            if попыток >= ПРЕДЕЛ_ОТПРАВОК:
                _в_очередь_недоставленного(
                    соед, з, "LEDGER_UNAVAILABLE_EXHAUSTED", str(e))
                отказов += 1
                continue
            соед.execute(
                "UPDATE changeset_outbox SET attempts=attempts+1, last_error=?, "
                "next_attempt_at=? WHERE seq=?",
                (str(e)[:300], time.time() + _отсрочка(попыток), з["seq"]))
            отложено += 1
            break  # журнал недоступен — дальше идти бессмысленно
        if итог.get("permanent"):
            _в_очередь_недоставленного(соед, з, "LEDGER_REJECTED",
                                       str(итог["body"]))
            отказов += 1
            continue
        соед.execute("UPDATE changeset_outbox SET published_at=?, "
                     "attempts=attempts+1, next_attempt_at=NULL WHERE seq=?",
                     (сейчас(), з["seq"]))
        отправлено += 1
    backlog = соед.execute("SELECT count(*) c FROM changeset_outbox "
                           "WHERE published_at IS NULL").fetchone()["c"]
    dlq = соед.execute("SELECT count(*) c FROM changeset_dlq").fetchone()["c"]
    return {"published": отправлено, "rejected": отказов,
            "deferred": отложено, "backlog": backlog, "dlq": dlq}


def воспроизвести(соед, *, с_позиции: int = 0,
                  предел: int = 500) -> dict[str, Any]:
    """Отправить заново уже отправленные записи, начиная с позиции.

    Нужно после восстановления журнала из копии: часть событий в нём есть, а
    часть потеряна, и разбирать вручную, каких именно, — работа, которую
    ящик умеет сделать сам. Повтор безопасен: журнал опознаёт запись по
    idempotency_key и второй раз её не заводит, — поэтому воспроизведение
    можно начинать с заведомо более ранней позиции, чем нужно.
    """
    строки = [dict(r) for r in соед.execute(
        "SELECT * FROM changeset_outbox WHERE seq > ? ORDER BY seq LIMIT ?",
        (с_позиции, предел))]
    отправлено = пропущено = 0
    позиция = с_позиции
    for з in строки:
        позиция = з["seq"]
        if версия_события(з["event_type"]) not in ИЗВЕСТНЫЕ_ВЕРСИИ_СОБЫТИЙ:
            пропущено += 1
            continue
        try:
            отправить(з)
        except LedgerUnavailable:
            # Останавливаемся на первой же недоступности: позиция возвращается
            # честная, и продолжить можно ровно отсюда.
            позиция = з["seq"] - 1
            break
        отправлено += 1
    return {"replayed": отправлено, "skipped": пропущено, "cursor": позиция}
