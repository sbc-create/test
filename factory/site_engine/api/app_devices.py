"""Доступ устройств к каталогу приложения «Кинатека» — без ключа в APK и без adb.

Служба чтения (`app-read-api`) пускает к каталогу только с заголовком
`X-App-Key`. Служебный ключ на устройства не выдаётся: он один на всех, и его
нельзя ни отозвать у одного телефона, ни положить в APK. Вместо него у каждого
устройства свой ключ, который выдаёт редактор в панели:

1. редактор добавляет устройство («Телевизор в гостиной») — панель один раз
   показывает короткий код вида `KQ7M-4TXP`, действующий CODE_TTL_S;
2. приложение отправляет код на `POST /api/app/v1/activate` службы чтения и
   получает в ответ ключ этого устройства; дальше ходит с ним, как с любым ключом;
3. «Отозвать» в панели — ключ перестаёт действовать сразу (служба перечитывает
   файл по изменению).

Хранилище — `var/app-config/<site>/devices.json` рядом с ревизиями: пишет только
Control API (атомарной подменой), служба чтения только читает. Ни ключ, ни код
в файле не лежат открытым текстом:

* `keyHash` = sha256(ключ) — по нему служба узнаёт ключ в запросе;
* `code.hash` = sha256("code" ‖ соль ‖ код) — по нему служба находит запись;
* `code.sealed` = сырой ключ XOR sha256("seal" ‖ соль ‖ код) — ключ, который
  может раскрыть только знающий код. Служба чтения не пишет на диск (у неё
  только чтение этого каталога), поэтому ключ рождается здесь и передаётся ей
  запечатанным.

Код одноразовый в пределах работы службы (она помнит использованные) и в любом
случае живёт не дольше CODE_TTL_S; «Новый код» выдаёт устройству новый ключ, и
прежняя установка с ним перестаёт работать. Подбор кода упирается в общий предел
попыток активации службы (31^8 ≈ 8,5·10^11 вариантов против десятков попыток в
минуту). Та же раскладка и те же формулы — в app-read-api (держать равными;
общий тестовый вектор в тестах обеих сторон).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any

SCHEMA = "kinateka-devices/1"
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"   # без 0/O, 1/I/L — читается с экрана и вводится пультом
CODE_LEN = 8
CODE_TTL_S = 24 * 3600
KEY_BYTES = 24
KEY_PREFIX = "dk_"
MAX_DEVICES = 200
MAX_NAME = 60
ID_RE = re.compile(r"^d-[0-9a-f]{12}$")


class DeviceError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _iso(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_code(raw: str) -> str:
    """Как вводит человек: строчные, пробелы и дефисы — то же самое."""
    return re.sub(r"[\s-]+", "", str(raw or "")).upper()


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def code_hash(salt: bytes, code: str) -> str:
    return hashlib.sha256(b"code" + salt + code.encode("ascii")).hexdigest()


def _pad(salt: bytes, code: str) -> bytes:
    return hashlib.sha256(b"seal" + salt + code.encode("ascii")).digest()[:KEY_BYTES]


def seal(raw_key: bytes, salt: bytes, code: str) -> str:
    return bytes(a ^ b for a, b in zip(raw_key, _pad(salt, code))).hex()


def unseal(sealed_hex: str, salt: bytes, code: str) -> str:
    raw = bytes(a ^ b for a, b in zip(bytes.fromhex(sealed_hex), _pad(salt, code)))
    return KEY_PREFIX + raw.hex()


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LEN))


def shown_code(code: str) -> str:
    return f"{code[:4]}-{code[4:]}"


class DeviceStore:
    """devices.json одного приложения. Вызывающий держит блокировку на запись."""

    def __init__(self, root: Path, *, now=time.time) -> None:
        self.path = Path(root) / "devices.json"
        self._now = now

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": SCHEMA, "devices": []}
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        if doc.get("schema") != SCHEMA or not isinstance(doc.get("devices"), list):
            raise DeviceError(503, "devices_unreadable", "файл устройств не той схемы")
        return doc

    def _save(self, doc: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def _find(self, doc: dict[str, Any], device_id: str) -> dict[str, Any]:
        d = next((x for x in doc["devices"] if x.get("id") == device_id), None)
        if d is None:
            raise DeviceError(404, "device_not_found", "нет такого устройства")
        return d

    def listing(self) -> list[dict[str, Any]]:
        """Для панели: без хэшей и запечатанных ключей."""
        now = self._now()
        out = []
        for d in self._load()["devices"]:
            code = d.get("code") or {}
            expires = code.get("expiresAt")
            out.append({"id": d["id"], "name": d.get("name", ""), "createdAt": d.get("createdAt"),
                        "createdBy": d.get("createdBy"), "revokedAt": d.get("revokedAt"),
                        "codeExpiresAt": expires,
                        "codeActive": bool(expires) and not d.get("revokedAt")
                        and _parse(expires) > now})
        return out

    def _issue(self, d: dict[str, Any]) -> str:
        """Новый ключ и код устройству; вернуть код (показывается один раз)."""
        raw = secrets.token_bytes(KEY_BYTES)
        salt = secrets.token_bytes(16)
        code = new_code()
        d["keyHash"] = key_hash(KEY_PREFIX + raw.hex())
        d["code"] = {"salt": salt.hex(), "hash": code_hash(salt, code), "sealed": seal(raw, salt, code),
                     "expiresAt": _iso(self._now() + CODE_TTL_S)}
        return code

    def add(self, name: str, *, by: str) -> tuple[dict[str, Any], str]:
        name = " ".join(str(name or "").split())
        if not 1 <= len(name) <= MAX_NAME:
            raise DeviceError(400, "invalid_name", f"название устройства — от 1 до {MAX_NAME} знаков")
        doc = self._load()
        if len([d for d in doc["devices"] if not d.get("revokedAt")]) >= MAX_DEVICES:
            raise DeviceError(422, "too_many_devices", f"действующих устройств не больше {MAX_DEVICES}")
        d = {"id": f"d-{secrets.token_hex(6)}", "name": name, "createdAt": _iso(self._now()),
             "createdBy": by, "revokedAt": None}
        code = self._issue(d)
        doc["devices"].append(d)
        self._save(doc)
        return d, code

    def reissue(self, device_id: str) -> tuple[dict[str, Any], str]:
        doc = self._load()
        d = self._find(doc, device_id)
        if d.get("revokedAt"):
            raise DeviceError(422, "device_revoked", "устройство отозвано — добавьте новое")
        code = self._issue(d)
        self._save(doc)
        return d, code

    def revoke(self, device_id: str) -> dict[str, Any]:
        doc = self._load()
        d = self._find(doc, device_id)
        if not d.get("revokedAt"):
            d["revokedAt"] = _iso(self._now())
            d["code"] = None
        self._save(doc)
        return d


def _parse(value: str) -> float:
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return 0.0
