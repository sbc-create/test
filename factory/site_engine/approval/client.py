"""Как контур подписывает и проверяет одобрения.

Подпись — сетевой вызов к выделенной службе: приватного ключа здесь нет и
быть не должно. Проверка — локальная, по публичному набору: она обязана
работать и тогда, когда signer недоступен, иначе падение одной службы
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
ТОКЕН = "approval-signer-token"
def адрес() -> str:
    """Читается на вызове, а не на импорте.

    Захваченный при импорте адрес нельзя изменить ни настройкой юнита, ни
    проверкой: модуль, однажды загруженный, навсегда ходит туда, куда решил
    в первую секунду жизни процесса.
    """
    return os.environ.get("APPROVAL_SIGNER_BASE", "http://127.0.0.1:8795")

_набор_кэш: tuple[str, K.НаборКлючей] | None = None


def набор_ключей() -> K.НаборКлючей:
    """Публичный набор проверки. Читается один раз на процесс."""
    global _набор_кэш
    сырое = C.получить(НАБОР)
    if _набор_кэш is None or _набор_кэш[0] != сырое:
        _набор_кэш = (сырое, K.НаборКлючей.из_json(сырое))
    return _набор_кэш[1]


def подписать(тело: str, *, таймаут: float = 10.0) -> str:
    токен = C.получить(ТОКЕН)
    зпр = urllib.request.Request(
        адрес() + "/sign", method="POST",
        data=json.dumps({"body": тело}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + токен})
    try:
        with urllib.request.urlopen(зпр, timeout=таймаут) as о:
            return json.loads(о.read())["signature"]
    except urllib.error.HTTPError as ош:
        подробности = ош.read().decode("utf-8", "replace")[:200]
        raise K.KeyringError("SIGNER_REFUSED", f"HTTP {ош.code}: {подробности}")
    except (urllib.error.URLError, OSError) as ош:
        raise K.KeyringError("SIGNER_UNAVAILABLE",
                             f"служба подписи недоступна: {ош}")


def проверить(подпись: str, тело: str) -> dict:
    return набор_ключей().проверить(подпись, тело)
