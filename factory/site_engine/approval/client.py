"""Как контур обращается к службе подписи.

Готовое тело подписи отсюда не уходит и уйти не может: служба его не
принимает. Наружу идёт ссылка на набор изменений и сведения об одобряющем;
всё остальное служба читает из канонического хранилища сама.

Проверка подписи — локальная, по публичному набору ключей: она обязана
работать и тогда, когда служба подписи недоступна, иначе её падение
останавливало бы проверку всех уже выданных одобрений.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from factory.site_engine.approval import keyring as K
from factory.site_engine.credentials import store as C

НАБОР = "approval-verify-keys"
#: Имя credential вызывающего задаёт юнит: у каждого вызывающего он свой.
ПЕРЕМЕННАЯ_ВЫЗЫВАЮЩЕГО = "APPROVAL_CALLER"

_набор_кэш: tuple[str, K.НаборКлючей] | None = None


def адрес() -> str:
    """Читается на вызове, а не на импорте."""
    return os.environ.get("APPROVAL_SIGNER_BASE", "http://127.0.0.1:8795")


def _токен() -> str:
    имя = os.environ.get(ПЕРЕМЕННАЯ_ВЫЗЫВАЮЩЕГО, "").strip()
    if not имя:
        raise K.KeyringError(
            "CALLER_IDENTITY_MISSING",
            f"{ПЕРЕМЕННАЯ_ВЫЗЫВАЮЩЕГО} не задана: юнит обязан назвать себя")
    try:
        return C.получить(f"approval-caller-{имя}")
    except C.CredentialError as ош:
        raise K.KeyringError(ош.error_code, ош.detail)


def набор_ключей() -> K.НаборКлючей:
    global _набор_кэш
    сырое = C.получить(НАБОР)
    if _набор_кэш is None or _набор_кэш[0] != сырое:
        _набор_кэш = (сырое, K.НаборКлючей.из_json(сырое))
    return _набор_кэш[1]


def _запрос(путь: str, тело: dict, *, таймаут: float) -> dict:
    зпр = urllib.request.Request(
        адрес() + путь, method="POST",
        data=json.dumps(тело, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + _токен()})
    try:
        with urllib.request.urlopen(зпр, timeout=таймаут) as о:
            return json.loads(о.read())
    except urllib.error.HTTPError as ош:
        подробности = ош.read().decode("utf-8", "replace")[:300]
        try:
            разобрано = json.loads(подробности)
            код = разобрано.get("error_code", "SIGNER_REFUSED")
            детали = разобрано.get("detail", подробности)
        except ValueError:
            код, детали = "SIGNER_REFUSED", подробности
        raise K.KeyringError(код, f"HTTP {ош.code}: {детали}")
    except (urllib.error.URLError, OSError) as ош:
        raise K.KeyringError("SIGNER_UNAVAILABLE",
                             f"служба подписи недоступна: {ош}")


def подписать_одобрение(*, changeset_id: str, approver_id: str,
                        approver_service: str, approver_type: str,
                        expires_at: str, таймаут: float = 10.0) -> str:
    """Подпись одобрения. Тело строит служба, а не вызывающий."""
    ответ = _запрос("/approval", {
        "changeset_id": changeset_id, "approver_id": approver_id,
        "approver_service": approver_service, "approver_type": approver_type,
        "expires_at": expires_at}, таймаут=таймаут)
    return ответ["signature"]


def запросить_разрешение(*, changeset_id: str, audience: str,
                         fencing_token: int, таймаут: float = 10.0) -> dict:
    """Короткоживущее разрешение на исполнение уже одобренного набора."""
    return _запрос("/grant", {"changeset_id": changeset_id,
                              "audience": audience,
                              "fencing_token": fencing_token}, таймаут=таймаут)


def проверить(подпись: str, тело: str) -> dict:
    return набор_ключей().проверить(подпись, тело)
