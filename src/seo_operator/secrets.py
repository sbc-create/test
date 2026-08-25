"""
Клиент Secret Hub (ТЗ §12).

Единственный контракт: оператор работает со ССЫЛКАМИ на секреты и получает
подтверждение работоспособности, но НИКОГДА не получает значение в память
процесса, доступную модели, в argv, в environment, в логи и в отчёты.

Реализация транспорта подключается владельцем. По умолчанию используется
`UnavailableSecretHub`, который честно отказывает — это лучше, чем молчаливое
чтение переменной окружения, которое выглядит как работа.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from .guardrails import AuthorizationBlocked
from .statuses import Status

SECRET_REF_PATTERN = re.compile(r"^secret://[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)+$")


class SecretLeak(RuntimeError):
    """Поднимается при попытке протащить значение секрета туда, где его быть не должно."""


@dataclass(frozen=True)
class SecretHandle:
    """
    Дескриптор секрета. Значения не содержит по построению — только ссылку
    и результат проверки. Именно это уходит в логи и отчёты.
    """

    ref: str
    available: bool
    scope: str
    checked_at: str
    expires_at: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not SECRET_REF_PATTERN.match(self.ref):
            raise ValueError(f"Некорректная ссылка на секрет: {self.ref!r}")

    def __repr__(self) -> str:
        return f"SecretHandle(ref={self.ref!r}, available={self.available}, scope={self.scope!r})"

    __str__ = __repr__

    def to_dict(self) -> dict[str, Any]:
        return {"ref": self.ref, "available": self.available, "scope": self.scope,
                "checked_at": self.checked_at, "expires_at": self.expires_at, "note": self.note}


class SecretHub(Protocol):
    def probe(self, ref: str) -> SecretHandle:
        """Проверить наличие и работоспособность секрета, НЕ возвращая значение."""
        ...

    def authorized_session(self, ref: str) -> Any:
        """
        Вернуть готовый транспорт (например, HTTP-сессию с уже проставленным
        заголовком), в котором значение недоступно вызывающему коду.
        """
        ...


class UnavailableSecretHub:
    """Заглушка по умолчанию: отказывает явно, вместо того чтобы читать env."""

    def probe(self, ref: str) -> SecretHandle:
        return SecretHandle(ref=ref, available=False, scope="none",
                            checked_at=datetime.now(timezone.utc).isoformat(),
                            note="Secret Hub не подключён")

    def authorized_session(self, ref: str) -> Any:
        raise AuthorizationBlocked(
            f"Secret Hub не подключён, секрет {ref} недоступен.",
            {"needs": "SEO_SECRET_HUB_URL + сервисный доступ", "ref": ref,
             "status": Status.BLOCKED_SECRET.value})


class InMemorySecretHub:
    """
    Для тестов и dry-run. Хранит ТОЛЬКО факт наличия и scope — значений нет
    даже здесь, поэтому тест не может случайно начать зависеть от значения.
    """

    def __init__(self, refs: dict[str, str] | None = None) -> None:
        self._refs = dict(refs or {})

    def register(self, ref: str, scope: str) -> None:
        if not SECRET_REF_PATTERN.match(ref):
            raise ValueError(f"Некорректная ссылка: {ref!r}")
        self._refs[ref] = scope

    def probe(self, ref: str) -> SecretHandle:
        now = datetime.now(timezone.utc).isoformat()
        if ref in self._refs:
            return SecretHandle(ref=ref, available=True, scope=self._refs[ref], checked_at=now)
        return SecretHandle(ref=ref, available=False, scope="none", checked_at=now,
                            note="секрет не зарегистрирован")

    def authorized_session(self, ref: str) -> Any:
        if ref not in self._refs:
            raise AuthorizationBlocked(f"Секрет {ref} отсутствует.",
                                       {"ref": ref, "status": Status.BLOCKED_SECRET.value})
        return _OpaqueSession(ref, self._refs[ref])


class _OpaqueSession:
    """Транспорт без доступа к значению: repr и str не раскрывают ничего."""

    def __init__(self, ref: str, scope: str) -> None:
        self.ref = ref
        self.scope = scope

    def __repr__(self) -> str:
        return f"_OpaqueSession(ref={self.ref!r}, scope={self.scope!r})"

    __str__ = __repr__


# Шаблоны ссылок для источников ТЗ §3.1.
def metrika_ref(site_id: str) -> str:
    return f"secret://metrika/{site_id}"


def webmaster_ref(site_id: str) -> str:
    return f"secret://webmaster/{site_id}"


def build_hub() -> SecretHub:
    """
    Фабрика. Если Secret Hub не сконфигурирован, возвращается отказывающая
    заглушка — падать в чтение переменных окружения запрещено (ТЗ §12).
    """
    if os.environ.get("SEO_SECRET_HUB_URL"):
        raise NotImplementedError(
            "Транспорт Secret Hub подключается владельцем: реализовать SecretHub.probe и "
            "authorized_session поверх выбранного хранилища (Vault/OpenBao/SOPS-agent). "
            "Значение секрета не должно возвращаться в вызывающий код.")
    return UnavailableSecretHub()


# --------------------------------------------------------------------------
# Защита от утечек
# --------------------------------------------------------------------------

LEAK_PATTERNS = (
    re.compile(r"\bAQAA[A-Za-z0-9_\-]{20,}"),          # Яндекс OAuth
    re.compile(r"\by0_[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def assert_no_secret(payload: str, context: str) -> None:
    """
    Барьер перед любой внешней публикацией: отчёт, HTML, лог, git.
    Поднимает SecretLeak, а не просто чистит текст: молчаливая очистка
    скрыла бы факт того, что секрет вообще попал в поток.
    """
    for pattern in LEAK_PATTERNS:
        if pattern.search(payload):
            raise SecretLeak(
                f"{context}: обнаружено значение, похожее на секрет. "
                "Публикация остановлена; значение не выводится.")


def scan_environment_for_secrets(env: dict[str, str] | None = None) -> list[str]:
    """
    Возвращает ИМЕНА переменных окружения, похожих на секреты (ТЗ §12:
    секретов не должно быть в обычных environment variables). Значения не возвращаются.
    """
    env = env if env is not None else dict(os.environ)
    suspicious = []
    for name, value in env.items():
        upper = name.upper()
        if any(marker in upper for marker in ("TOKEN", "SECRET", "PASSWORD", "OAUTH",
                                              "API_KEY", "APIKEY", "CREDENTIAL", "PRIVATE_KEY")):
            suspicious.append(name)
            continue
        for pattern in LEAK_PATTERNS:
            if pattern.search(value):
                suspicious.append(name)
                break
    return sorted(set(suspicious))
