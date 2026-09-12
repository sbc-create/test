"""Ключи подписи одобрения: Ed25519, kid, ротация и отзыв.

Почему не HMAC
--------------

HMAC симметричен: кто проверяет — тот и может подписать. Значит рабочему
процессу, адаптерам и всему, что обязано лишь УБЕДИТЬСЯ в подлинности
одобрения, пришлось бы выдать тот же секрет, которым одобрение создаётся.
Одна утечка на стороне проверяющего — и подделать разрешение может любой.

Ed25519 разделяет эти роли арифметически: приватный ключ существует ровно в
одном месте — у выделенного signer, — а проверяющие получают публичный,
который секретом не является и может лежать хоть в Git.

Ротация и отзыв — разные вещи
-----------------------------

Смена ключа не отменяет старых одобрений сама по себе: подписанное вчера
проверяется вчерашним публичным ключом и остаётся действительным. Поэтому
`kid` выведенного из обращения ключа помечается отозванным явно, и подпись
с таким `kid` отвергается независимо от того, верна ли она математически.
Без этого «ротация» означала бы лишь то, что новые подписи другие.
"""
from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey)

АЛГОРИТМ = "Ed25519"
ПРЕФИКС = "ed25519"


class KeyringError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.error_code, self.detail = code, detail


def _b64(сырое: bytes) -> str:
    return base64.urlsafe_b64encode(сырое).decode("ascii").rstrip("=")


def _из_b64(текст: str) -> bytes:
    добивка = "=" * (-len(текст) % 4)
    return base64.urlsafe_b64decode(текст + добивка)


def kid_публичного(публичный: Ed25519PublicKey) -> str:
    """Устойчивый идентификатор ключа: выводится из самого ключа.

    Случайный или порядковый kid пришлось бы хранить рядом и синхронизировать;
    выведенный из ключа совпадает у всех, кто держит один и тот же ключ, без
    какой-либо договорённости.
    """
    сырое = публичный.public_bytes(serialization.Encoding.Raw,
                                   serialization.PublicFormat.Raw)
    return hashlib.sha256(сырое).hexdigest()[:16]


def создать_ключ() -> tuple[str, str, str]:
    """Сгенерировать пару. Возвращает (kid, приватный PEM, публичный b64)."""
    приватный = Ed25519PrivateKey.generate()
    публичный = приватный.public_key()
    pem = приватный.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode("ascii")
    сырое = публичный.public_bytes(serialization.Encoding.Raw,
                                   serialization.PublicFormat.Raw)
    return kid_публичного(публичный), pem, _b64(сырое)


def приватный_из_pem(pem: str) -> Ed25519PrivateKey:
    ключ = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    if not isinstance(ключ, Ed25519PrivateKey):
        raise KeyringError("KEY_ALGORITHM_UNSUPPORTED",
                           "ключ подписи обязан быть Ed25519")
    return ключ


def подписать(pem: str, тело: str) -> str:
    """Подпись в виде `ed25519:<kid>:<base64>`."""
    ключ = приватный_из_pem(pem)
    kid = kid_публичного(ключ.public_key())
    подпись = ключ.sign(тело.encode("utf-8"))
    return f"{ПРЕФИКС}:{kid}:{_b64(подпись)}"


@dataclass(frozen=True)
class Ключ:
    kid: str
    публичный: str
    состояние: str          # ACTIVE | RETIRED | REVOKED
    not_after: str | None = None


class НаборКлючей:
    """Публичные ключи проверки. Секретов не содержит.

    Отозванный ключ остаётся в наборе намеренно: удалив его, мы перестали бы
    отличать «подпись неизвестным ключом» от «подпись отозванным ключом», а
    это разные события — второе означает попытку воспользоваться выведенным
    из обращения разрешением.
    """

    def __init__(self, ключи: list[Ключ]) -> None:
        self.ключи = {к.kid: к for к in ключи}

    @classmethod
    def из_json(cls, текст: str) -> "НаборКлючей":
        данные = json.loads(текст)
        записи = данные.get("keys", данные if isinstance(данные, list) else [])
        return cls([Ключ(kid=з["kid"], публичный=з["public"],
                         состояние=(з.get("state") or "ACTIVE").upper(),
                         not_after=з.get("not_after")) for з in записи])

    def в_json(self) -> str:
        return json.dumps(
            {"alg": АЛГОРИТМ,
             "keys": [{"kid": к.kid, "public": к.публичный, "state": к.состояние,
                       **({"not_after": к.not_after} if к.not_after else {})}
                      for к in sorted(self.ключи.values(), key=lambda x: x.kid)]},
            ensure_ascii=False, indent=1)

    @property
    def активный(self) -> Ключ | None:
        активные = [к for к in self.ключи.values() if к.состояние == "ACTIVE"]
        return активные[0] if len(активные) == 1 else (активные[0] if активные else None)

    def проверить(self, подпись: str, тело: str) -> dict[str, Any]:
        """Подлинна ли подпись и вправе ли этот ключ ещё что-либо разрешать."""
        части = (подпись or "").split(":")
        if len(части) != 3 or части[0] != ПРЕФИКС:
            raise KeyringError("SIGNATURE_MALFORMED",
                               "подпись не в формате ed25519:<kid>:<base64>")
        _, kid, сырое = части
        ключ = self.ключи.get(kid)
        if ключ is None:
            raise KeyringError("SIGNATURE_KEY_UNKNOWN",
                               f"ключ {kid} набору проверки неизвестен")
        if ключ.состояние == "REVOKED":
            # Отдельный код: владельцу важно отличать подделку от попытки
            # воспользоваться отозванным разрешением.
            raise KeyringError("APPROVAL_KEY_REVOKED",
                               f"ключ {kid} отозван; одобрения им недействительны")
        публичный = Ed25519PublicKey.from_public_bytes(_из_b64(ключ.публичный))
        try:
            публичный.verify(_из_b64(сырое), тело.encode("utf-8"))
        except InvalidSignature as ош:
            raise KeyringError("APPROVAL_SIGNATURE_INVALID",
                               "подпись одобрения не совпала") from ош
        return {"kid": kid, "state": ключ.состояние}
