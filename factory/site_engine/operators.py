"""Каталог операторов: роли, приглашения, сессии, блокировка.

До этого модель доступа была такой: вход по токену Control API, права — области
токена. Для одного человека этого хватает, для команды нет. Токен нельзя
отозвать у одного и оставить у другого, нельзя увидеть, кто вошёл, нельзя
заблокировать человека, не выбив всех остальных, и нельзя узнать, кто принял
решение — в журнале виден отпечаток токена, а не человек.

Здесь появляется то, чего не хватало: люди, роли, приглашения и сессии.

Три решения, каждое стоит объяснить.

**Пароль хранится только как scrypt-хэш.** scrypt взят из стандартной
библиотеки: своя схема на sha256 с солью выглядит так же, но подбирается на
несколько порядков дешевле. Параметры вынесены в константы и версионированы —
их придётся поднимать, и запись обязана помнить, какими она посчитана.

**Отзыв действует немедленно.** Сессия проверяется по каталогу на каждом
запросе, а не только при входе: сессия, пережившая блокировку владельца, —
это дыра, которую видно только в журнале и только потом. Цена — чтение файла
на запрос; она заметно меньше цены ошибки.

**Последнего администратора нельзя ни удалить, ни разжаловать, ни
заблокировать.** Не из вежливости: система без администратора не чинится
изнутри, и восстановление превращается в правку файлов на сервере руками.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "operator-identity/1.0.0"

#: Параметры scrypt. Версионированы: их придётся поднимать, и старая запись
#: обязана помнить, какими она посчитана, иначе проверка сломается молча.
SCRYPT = {"version": 1, "n": 2**14, "r": 8, "p": 1, "dklen": 32}

#: Роли и области Control API, которые они дают. Роль — это имя набора прав,
#: а не отдельная сущность: два способа выражать одно и то же расходятся.
ROLES: dict[str, tuple[str, ...]] = {
    "viewer": ("read",),
    "reviewer": ("read", "review:write"),
    "editor": ("read", "review:write", "jobs:write"),
    "operator": ("read", "review:write", "jobs:write", "cache:write", "audit:read"),
    "admin": (
        "read",
        "review:write",
        "jobs:write",
        "cache:write",
        "audit:read",
        "config:write",
        "operators:write",
    ),
}

#: Порядок старшинства. Нужен, чтобы «повысить себя» можно было определить, а
#: не обсуждать.
RANK = {"viewer": 0, "reviewer": 1, "editor": 2, "operator": 3, "admin": 4}

INVITE_TTL_SECONDS = 72 * 60 * 60
#: Сколько неудачных попыток подряд до временной блокировки входа.
LOCKOUT_THRESHOLD = 5
LOCKOUT_SECONDS = 15 * 60


class OperatorError(RuntimeError):
    """Действие над каталогом операторов невозможно."""


class OperatorState(str, enum.Enum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    #: Удаление не стирает запись: журнал ссылается на действующее лицо, и
    #: исчезнувший идентификатор превращает историю в набор загадок.
    DELETED = "DELETED"


class MfaState(str, enum.Enum):
    """Контракт второго фактора. Провайдера пока нет, состояния уже есть.

    Отсутствие провайдера — не повод не описать переходы: когда он появится,
    в коде не должно оказаться места, где второй фактор «просто не проверяется».
    """

    NOT_ENROLLED = "NOT_ENROLLED"
    ENROLLMENT_PENDING = "ENROLLMENT_PENDING"
    ENROLLED = "ENROLLED"
    #: Восстановление: владелец потерял фактор и подтвердил это иным путём.
    RECOVERY_PENDING = "RECOVERY_PENDING"
    #: Провайдер не настроен — проверка не выполнялась, и это видно.
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"


def _сейчас() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _метка(момент: float) -> str:
    return dt.datetime.fromtimestamp(момент, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_password(пароль: str, *, соль: bytes | None = None) -> dict[str, Any]:
    """scrypt из стандартной библиотеки. Своя схема здесь была бы хуже."""
    if not пароль or len(пароль) < 12:
        raise OperatorError("пароль короче двенадцати символов")
    соль = соль or secrets.token_bytes(16)
    ключ = hashlib.scrypt(
        пароль.encode("utf-8"),
        salt=соль,
        n=SCRYPT["n"],
        r=SCRYPT["r"],
        p=SCRYPT["p"],
        dklen=SCRYPT["dklen"],
    )
    return {
        "algo": "scrypt",
        "version": SCRYPT["version"],
        "n": SCRYPT["n"],
        "r": SCRYPT["r"],
        "p": SCRYPT["p"],
        "salt": соль.hex(),
        "hash": ключ.hex(),
    }


def verify_password(пароль: str, запись: dict[str, Any] | None) -> bool:
    """Проверка постоянного времени. Отсутствие записи — тоже отказ."""
    if not запись or запись.get("algo") != "scrypt":
        return False
    try:
        ключ = hashlib.scrypt(
            (пароль or "").encode("utf-8"),
            salt=bytes.fromhex(запись["salt"]),
            n=int(запись["n"]),
            r=int(запись["r"]),
            p=int(запись["p"]),
            dklen=len(bytes.fromhex(запись["hash"])),
        )
    except (KeyError, ValueError):
        return False
    return hmac.compare_digest(ключ, bytes.fromhex(запись["hash"]))


def scopes_for(роли) -> tuple[str, ...]:
    """Области по ролям. Неизвестная роль не даёт ничего и не молчит об этом."""
    итог: set[str] = set()
    for роль in роли or ():
        if роль not in ROLES:
            raise OperatorError(f"неизвестная роль {роль!r}; известны {sorted(ROLES)}")
        итог.update(ROLES[роль])
    return tuple(sorted(итог))


@dataclasses.dataclass
class Operator:
    operator_id: str
    email: str
    roles: tuple[str, ...] = ()
    state: OperatorState = OperatorState.INVITED
    password: dict[str, Any] | None = None
    mfa_state: MfaState = MfaState.NOT_ENROLLED
    mfa_recovery_hash: str = ""
    created_at: str = ""
    updated_at: str = ""
    blocked_reason: str = ""
    failed_logins: int = 0
    locked_until: float = 0.0
    #: Все сессии, выданные после этой отметки, действительны; выданные раньше —
    #: нет. Одно число отзывает все сессии сразу, не перебирая их.
    sessions_valid_after: float = 0.0
    version: int = 1

    def as_dict(self, *, safe: bool = True) -> dict[str, Any]:
        d = {
            "operatorId": self.operator_id,
            "email": self.email,
            "roles": list(self.roles),
            "state": self.state.value,
            "scopes": list(scopes_for(self.roles)) if self.roles else [],
            "mfaState": self.mfa_state.value,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "blockedReason": self.blocked_reason,
            "failedLogins": self.failed_logins,
            "lockedUntil": _метка(self.locked_until) if self.locked_until else "",
            "version": self.version,
            "contractVersion": CONTRACT_VERSION,
        }
        if not safe:
            d["password"] = self.password
            d["mfaRecoveryHash"] = self.mfa_recovery_hash
            d["sessionsValidAfter"] = self.sessions_valid_after
            d["lockedUntilRaw"] = self.locked_until
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Operator:
        return cls(
            operator_id=d["operatorId"],
            email=d["email"],
            roles=tuple(d.get("roles") or ()),
            state=OperatorState(d.get("state", "INVITED")),
            password=d.get("password"),
            mfa_state=MfaState(d.get("mfaState", "NOT_ENROLLED")),
            mfa_recovery_hash=d.get("mfaRecoveryHash", ""),
            created_at=d.get("createdAt", ""),
            updated_at=d.get("updatedAt", ""),
            blocked_reason=d.get("blockedReason", ""),
            failed_logins=int(d.get("failedLogins", 0)),
            locked_until=float(d.get("lockedUntilRaw", 0.0)),
            sessions_valid_after=float(d.get("sessionsValidAfter", 0.0)),
            version=int(d.get("version", 1)),
        )


@dataclasses.dataclass
class Invite:
    invite_id: str
    email: str
    roles: tuple[str, ...]
    token_hash: str
    created_by: str
    created_at: str
    expires_at: float
    accepted_at: str = ""
    revoked_at: str = ""

    @property
    def state(self) -> str:
        if self.revoked_at:
            return "REVOKED"
        if self.accepted_at:
            return "ACCEPTED"
        return "PENDING"

    def as_dict(self) -> dict[str, Any]:
        return {
            "inviteId": self.invite_id,
            "email": self.email,
            "roles": list(self.roles),
            "createdBy": self.created_by,
            "createdAt": self.created_at,
            "expiresAt": _метка(self.expires_at),
            "acceptedAt": self.accepted_at,
            "revokedAt": self.revoked_at,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any], *, token_hash: str = "") -> Invite:
        return cls(
            invite_id=d["inviteId"],
            email=d["email"],
            roles=tuple(d.get("roles") or ()),
            token_hash=token_hash or d.get("tokenHash", ""),
            created_by=d.get("createdBy", ""),
            created_at=d.get("createdAt", ""),
            expires_at=float(d.get("expiresAtRaw", 0.0)),
            accepted_at=d.get("acceptedAt", ""),
            revoked_at=d.get("revokedAt", ""),
        )


@dataclasses.dataclass
class SessionRecord:
    """Сессия в каталоге. Существует отдельно от памяти процесса.

    Иначе отзыв сессии работал бы только в том процессе, где её создали, а
    служба может быть перезапущена или их может быть несколько.
    """

    sid_hash: str
    operator_id: str
    created_at: float
    last_seen: float
    user_agent: str = ""
    ip_hint: str = ""
    revoked_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "sessionId": self.sid_hash[:16],
            "operatorId": self.operator_id,
            "createdAt": _метка(self.created_at),
            "lastSeen": _метка(self.last_seen),
            "userAgent": self.user_agent[:120],
            "ipHint": self.ip_hint,
            "revokedAt": _метка(self.revoked_at) if self.revoked_at else "",
            "active": not self.revoked_at,
        }


class OperatorDirectory:
    """Каталог операторов на диске. Одна запись — один файл."""

    def __init__(self, root: Path | str, *, now=None) -> None:
        import time

        self._now = now or time.time
        base = Path(root) / "var" / "state" / "operators"
        self.dir = base
        self.invites_dir = base / "invites"
        self.sessions_dir = base / "sessions"
        for d in (self.dir, self.invites_dir, self.sessions_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ---- низкий уровень -------------------------------------------------
    @staticmethod
    def _безопасный(идентификатор: str) -> str:
        if (
            not идентификатор
            or "/" in идентификатор
            or ".." in идентификатор
            or len(идентификатор) > 128
        ):
            raise OperatorError(f"негодный идентификатор {идентификатор!r}")
        return идентификатор

    def _записать(self, путь: Path, данные: dict) -> None:
        врем = путь.with_name(f".{путь.name}.tmp")
        врем.write_text(json.dumps(данные, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(врем, путь)

    @staticmethod
    def normalise_email(email: str) -> str:
        """Адрес приводится к одному виду: иначе один человек заводится дважды."""
        адрес = (email or "").strip().lower()
        if "@" not in адрес or адрес.startswith("@") or адрес.endswith("@"):
            raise OperatorError(f"негодный адрес {email!r}")
        return адрес

    @staticmethod
    def _id_по_адресу(email: str) -> str:
        return hashlib.sha256(email.encode("utf-8")).hexdigest()[:24]

    # ---- операторы ------------------------------------------------------
    def get(self, operator_id: str) -> Operator:
        путь = self.dir / f"{self._безопасный(operator_id)}.json"
        if not путь.exists():
            raise OperatorError(f"оператора {operator_id} нет")
        return Operator.from_dict(json.loads(путь.read_text(encoding="utf-8")))

    def by_email(self, email: str) -> Operator | None:
        try:
            return self.get(self._id_по_адресу(self.normalise_email(email)))
        except OperatorError:
            return None

    def save(self, оператор: Operator) -> Operator:
        оператор.updated_at = _сейчас()
        self._записать(self.dir / f"{оператор.operator_id}.json", оператор.as_dict(safe=False))
        return оператор

    def list(
        self, *, state: str = "", role: str = "", offset: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        все: list[Operator] = []
        for файл in sorted(self.dir.glob("*.json")):
            try:
                все.append(Operator.from_dict(json.loads(файл.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
        отобрано = [
            o
            for o in все
            if (not state or o.state.value == state) and (not role or role in o.roles)
        ]
        отобрано.sort(key=lambda o: o.email)
        по_состояниям: dict[str, int] = {}
        for o in все:
            по_состояниям[o.state.value] = по_состояниям.get(o.state.value, 0) + 1
        return {
            "total": len(отобрано),
            "totalAll": len(все),
            "offset": offset,
            "limit": limit,
            "byState": по_состояниям,
            "items": [o.as_dict() for o in отобрано[offset : offset + limit]],
            "contractVersion": CONTRACT_VERSION,
        }

    def _активных_админов(self, *, кроме: str = "") -> int:
        сколько = 0
        for файл in self.dir.glob("*.json"):
            try:
                o = Operator.from_dict(json.loads(файл.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
            if o.operator_id == кроме:
                continue
            if o.state is OperatorState.ACTIVE and "admin" in o.roles:
                сколько += 1
        return сколько

    def _не_последний_админ(self, оператор: Operator, действие: str) -> None:
        """Система без администратора не чинится изнутри."""
        if "admin" not in оператор.roles or оператор.state is not OperatorState.ACTIVE:
            return
        if self._активных_админов(кроме=оператор.operator_id) == 0:
            raise OperatorError(
                f"нельзя {действие}: это последний активный администратор. "
                f"Сначала назначьте другого — иначе управление каталогом "
                f"операторов будет потеряно и восстанавливается только правкой "
                f"файлов на сервере"
            )

    # ---- приглашения ----------------------------------------------------
    def invite(
        self, *, email: str, roles, created_by: str, ttl_seconds: int = INVITE_TTL_SECONDS
    ) -> tuple[Invite, str]:
        """Создаёт приглашение. Возвращает запись и одноразовый секрет.

        Секрет отдаётся ровно один раз и на диск кладётся только хэшем: иначе
        доступ к каталогу приглашений равен доступу ко всем учётным записям.
        """
        адрес = self.normalise_email(email)
        роли = tuple(roles or ())
        scopes_for(роли)  # проверка ролей до записи
        if not роли:
            raise OperatorError("приглашение без ролей бессмысленно")
        существующий = self.by_email(адрес)
        if существующий and существующий.state is OperatorState.ACTIVE:
            raise OperatorError(f"{адрес} уже активен")

        секрет = secrets.token_urlsafe(32)
        запись = Invite(
            invite_id=secrets.token_urlsafe(12),
            email=адрес,
            roles=роли,
            token_hash=hashlib.sha256(секрет.encode("utf-8")).hexdigest(),
            created_by=created_by,
            created_at=_сейчас(),
            expires_at=float(self._now()) + ttl_seconds,
        )
        данные = запись.as_dict()
        данные["tokenHash"] = запись.token_hash
        данные["expiresAtRaw"] = запись.expires_at
        self._записать(self.invites_dir / f"{запись.invite_id}.json", данные)

        # Заводим запись оператора в состоянии INVITED, чтобы он был виден в
        # списке сразу: приглашение, которого не видно, теряется.
        if существующий is None:
            self.save(
                Operator(
                    operator_id=self._id_по_адресу(адрес),
                    email=адрес,
                    roles=роли,
                    state=OperatorState.INVITED,
                    mfa_state=MfaState.PROVIDER_NOT_CONFIGURED,
                    created_at=_сейчас(),
                )
            )
        return запись, секрет

    def list_invites(self) -> list[dict[str, Any]]:
        итог = []
        for файл in sorted(self.invites_dir.glob("*.json")):
            try:
                данные = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            приглашение = Invite.from_dict(данные)
            строка = приглашение.as_dict()
            if приглашение.state == "PENDING" and приглашение.expires_at < float(self._now()):
                строка["state"] = "EXPIRED"
            итог.append(строка)
        return итог

    def revoke_invite(self, invite_id: str, *, actor: str) -> dict[str, Any]:
        путь = self.invites_dir / f"{self._безопасный(invite_id)}.json"
        if not путь.exists():
            raise OperatorError(f"приглашения {invite_id} нет")
        данные = json.loads(путь.read_text(encoding="utf-8"))
        if данные.get("acceptedAt"):
            raise OperatorError("приглашение уже принято: отзывать нечего")
        данные["revokedAt"] = _сейчас()
        данные["revokedBy"] = actor
        self._записать(путь, данные)
        return данные

    def accept_invite(self, *, secret: str, password: str) -> Operator:
        """Принятие приглашения. Пароль задаёт приглашённый, а не приглашающий.

        Иначе пароль хотя бы недолго известен двоим, и «универсальный
        первоначальный пароль» появляется сам собой.
        """
        отпечаток = hashlib.sha256((secret or "").encode("utf-8")).hexdigest()
        for файл in sorted(self.invites_dir.glob("*.json")):
            try:
                данные = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not hmac.compare_digest(str(данные.get("tokenHash", "")), отпечаток):
                continue
            приглашение = Invite.from_dict(данные)
            if приглашение.revoked_at:
                raise OperatorError("приглашение отозвано")
            if приглашение.accepted_at:
                raise OperatorError("приглашение уже использовано")
            if приглашение.expires_at < float(self._now()):
                raise OperatorError("срок приглашения истёк")

            оператор = self.by_email(приглашение.email) or Operator(
                operator_id=self._id_по_адресу(приглашение.email),
                email=приглашение.email,
                created_at=_сейчас(),
            )
            оператор.roles = приглашение.roles
            оператор.password = hash_password(password)
            оператор.state = OperatorState.ACTIVE
            оператор.mfa_state = MfaState.PROVIDER_NOT_CONFIGURED
            оператор.failed_logins = 0
            оператор.locked_until = 0.0
            оператор.version += 1
            self.save(оператор)

            данные["acceptedAt"] = _сейчас()
            self._записать(файл, данные)
            return оператор
        raise OperatorError("приглашение не найдено")

    # ---- роли, блокировка ----------------------------------------------
    def set_roles(self, operator_id: str, roles, *, actor_id: str, actor_roles) -> Operator:
        """Смена ролей. Себе полномочия не повышают."""
        роли = tuple(roles or ())
        scopes_for(роли)
        оператор = self.get(operator_id)
        if operator_id == actor_id:
            своё = max((RANK[r] for r in оператор.roles), default=-1)
            новое = max((RANK[r] for r in роли), default=-1)
            if новое > своё:
                raise OperatorError(
                    "нельзя повысить собственные полномочия: повышение выдаёт "
                    "другой администратор, иначе роль перестаёт что-либо значить"
                )
        if "admin" in оператор.roles and "admin" not in роли:
            self._не_последний_админ(оператор, "снять роль администратора")
        оператор.roles = роли
        оператор.version += 1
        # Смена ролей отзывает выданные сессии: иначе новые ограничения
        # начинают действовать только после того, как человек сам выйдет.
        оператор.sessions_valid_after = float(self._now())
        return self.save(оператор)

    def block(self, operator_id: str, *, reason: str, actor_id: str) -> Operator:
        оператор = self.get(operator_id)
        if operator_id == actor_id:
            raise OperatorError("нельзя заблокировать самого себя")
        self._не_последний_админ(оператор, "заблокировать")
        оператор.state = OperatorState.BLOCKED
        оператор.blocked_reason = reason
        оператор.version += 1
        оператор.sessions_valid_after = float(self._now())
        return self.save(оператор)

    def unblock(self, operator_id: str) -> Operator:
        оператор = self.get(operator_id)
        if оператор.state is not OperatorState.BLOCKED:
            raise OperatorError("оператор не заблокирован")
        оператор.state = OperatorState.ACTIVE if оператор.password else OperatorState.INVITED
        оператор.blocked_reason = ""
        оператор.failed_logins = 0
        оператор.locked_until = 0.0
        оператор.version += 1
        return self.save(оператор)

    def delete(self, operator_id: str, *, actor_id: str) -> Operator:
        оператор = self.get(operator_id)
        if operator_id == actor_id:
            raise OperatorError("нельзя удалить самого себя")
        self._не_последний_админ(оператор, "удалить")
        оператор.state = OperatorState.DELETED
        оператор.password = None
        оператор.roles = ()
        оператор.version += 1
        оператор.sessions_valid_after = float(self._now())
        return self.save(оператор)

    # ---- вход -----------------------------------------------------------
    def authenticate(self, *, email: str, password: str) -> Operator:
        """Вход. Ответ одинаков для всех отказов — иначе адреса перебираются.

        Блокировка после нескольких неудач тоже не различает причину: сообщение
        «слишком много попыток» уже подтверждает существование адреса, поэтому
        счётчик ведётся, а наружу уходит один и тот же отказ.
        """
        общий = OperatorError("неверный адрес или пароль")
        try:
            адрес = self.normalise_email(email)
        except OperatorError:
            raise общий from None
        оператор = self.by_email(адрес)
        if оператор is None:
            # Считаем хэш всё равно: иначе несуществующий адрес отвечает
            # заметно быстрее, и перебор становится дешёвым.
            verify_password(password, hash_password("заглушка-для-времени"))
            raise общий
        сейчас = float(self._now())
        if оператор.locked_until > сейчас:
            raise общий
        if оператор.state is not OperatorState.ACTIVE:
            raise общий
        if not verify_password(password, оператор.password):
            оператор.failed_logins += 1
            if оператор.failed_logins >= LOCKOUT_THRESHOLD:
                оператор.locked_until = сейчас + LOCKOUT_SECONDS
                оператор.failed_logins = 0
            self.save(оператор)
            raise общий
        оператор.failed_logins = 0
        оператор.locked_until = 0.0
        self.save(оператор)
        return оператор

    def set_password(self, operator_id: str, *, password: str) -> Operator:
        оператор = self.get(operator_id)
        оператор.password = hash_password(password)
        оператор.version += 1
        # Смена пароля отзывает все сессии: иначе украденная сессия переживает
        # реакцию на кражу.
        оператор.sessions_valid_after = float(self._now())
        return self.save(оператор)

    # ---- сессии ---------------------------------------------------------
    @staticmethod
    def _отпечаток_сессии(sid: str) -> str:
        return hashlib.sha256(sid.encode("utf-8")).hexdigest()

    def register_session(
        self, *, sid: str, operator_id: str, user_agent: str = "", ip_hint: str = ""
    ) -> SessionRecord:
        сейчас = float(self._now())
        запись = SessionRecord(
            sid_hash=self._отпечаток_сессии(sid),
            operator_id=operator_id,
            created_at=сейчас,
            last_seen=сейчас,
            user_agent=user_agent,
            ip_hint=ip_hint,
        )
        данные = запись.as_dict()
        данные.update(
            {
                "sidHash": запись.sid_hash,
                "createdAtRaw": запись.created_at,
                "lastSeenRaw": запись.last_seen,
                "revokedAtRaw": 0.0,
            }
        )
        self._записать(self.sessions_dir / f"{запись.sid_hash}.json", данные)
        return запись

    def _сессия(self, sid_hash: str) -> dict | None:
        путь = self.sessions_dir / f"{sid_hash}.json"
        if not путь.exists():
            return None
        try:
            return json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def session_valid(self, sid: str) -> Operator | None:
        """Проверяется на КАЖДОМ запросе. Отзыв обязан действовать сразу."""
        данные = self._сессия(self._отпечаток_сессии(sid))
        if данные is None or данные.get("revokedAtRaw"):
            return None
        try:
            оператор = self.get(данные["operatorId"])
        except OperatorError:
            return None
        if оператор.state is not OperatorState.ACTIVE:
            return None
        if float(данные.get("createdAtRaw", 0)) < оператор.sessions_valid_after:
            return None
        данные["lastSeenRaw"] = float(self._now())
        данные["lastSeen"] = _метка(данные["lastSeenRaw"])
        self._записать(self.sessions_dir / f"{данные['sidHash']}.json", данные)
        return оператор

    def list_sessions(
        self, *, operator_id: str = "", active_only: bool = True
    ) -> list[dict[str, Any]]:
        итог = []
        for файл in sorted(self.sessions_dir.glob("*.json")):
            try:
                данные = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if operator_id and данные.get("operatorId") != operator_id:
                continue
            отозвана = bool(данные.get("revokedAtRaw"))
            if active_only and отозвана:
                continue
            try:
                оператор = self.get(данные["operatorId"])
                устарела = float(данные.get("createdAtRaw", 0)) < оператор.sessions_valid_after
            except OperatorError:
                устарела = True
            строка = {k: v for k, v in данные.items() if not k.endswith("Raw") and k != "sidHash"}
            строка["active"] = not отозвана and not устарела
            строка["staleByPolicy"] = устарела
            if active_only and устарела:
                continue
            итог.append(строка)
        return итог

    def revoke_session(self, session_id: str, *, actor: str) -> bool:
        """Отзыв одной сессии по короткому идентификатору из списка."""
        for файл in sorted(self.sessions_dir.glob("*.json")):
            try:
                данные = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if данные.get("sessionId") != session_id:
                continue
            if данные.get("revokedAtRaw"):
                return False
            данные["revokedAtRaw"] = float(self._now())
            данные["revokedAt"] = _сейчас()
            данные["revokedBy"] = actor
            self._записать(файл, данные)
            return True
        return False

    def revoke_all_sessions(self, operator_id: str, *, actor: str) -> int:
        """Отзыв всех сессий одним числом, а не перебором файлов.

        Перебор пропустил бы сессию, созданную в тот же миг другим процессом;
        отметка времени — нет.
        """
        оператор = self.get(operator_id)
        оператор.sessions_valid_after = float(self._now())
        оператор.version += 1
        self.save(оператор)
        сколько = 0
        for файл in sorted(self.sessions_dir.glob("*.json")):
            try:
                данные = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if данные.get("operatorId") != operator_id or данные.get("revokedAtRaw"):
                continue
            данные["revokedAtRaw"] = float(self._now())
            данные["revokedAt"] = _сейчас()
            данные["revokedBy"] = actor
            self._записать(файл, данные)
            сколько += 1
        return сколько

    # ---- второй фактор ---------------------------------------------------
    def start_mfa_enrollment(self, operator_id: str) -> dict[str, Any]:
        """Начало привязки. Провайдера нет — состояние это и показывает."""
        оператор = self.get(operator_id)
        оператор.mfa_state = MfaState.ENROLLMENT_PENDING
        оператор.version += 1
        self.save(оператор)
        return {
            "operatorId": operator_id,
            "mfaState": оператор.mfa_state.value,
            "providerConfigured": False,
            "blocker": "внешний поставщик второго фактора не настроен",
            "contractVersion": CONTRACT_VERSION,
        }

    def issue_mfa_recovery(self, operator_id: str) -> tuple[Operator, str]:
        """Код восстановления. На диске только хэш."""
        оператор = self.get(operator_id)
        код = secrets.token_urlsafe(16)
        оператор.mfa_recovery_hash = hashlib.sha256(код.encode("utf-8")).hexdigest()
        оператор.mfa_state = MfaState.RECOVERY_PENDING
        оператор.version += 1
        return self.save(оператор), код

    def consume_mfa_recovery(self, operator_id: str, *, code: str) -> Operator:
        оператор = self.get(operator_id)
        отпечаток = hashlib.sha256((code or "").encode("utf-8")).hexdigest()
        if not оператор.mfa_recovery_hash or not hmac.compare_digest(
            оператор.mfa_recovery_hash, отпечаток
        ):
            raise OperatorError("код восстановления не подходит")
        оператор.mfa_recovery_hash = ""
        оператор.mfa_state = MfaState.NOT_ENROLLED
        оператор.version += 1
        return self.save(оператор)
