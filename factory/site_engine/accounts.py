"""Учётные записи зрителей. Отдельно от операторов — во всём.

Смешивать их нельзя ни в одном месте: ни в хранилище, ни в cookie, ни в
ролях, ни в областях доступа. Один общий список «пользователей» рано или
поздно приводит к тому, что зритель оказывается с правом оператора — не по
злому умыслу, а потому что где-то забыли проверить, из какого он списка.

Записи привязаны к витрине. Один и тот же адрес на двух витринах — две разные
учётные записи: витрины принадлежат разным доменам и разным владельцам, и
общая учётная запись означала бы, что регистрация на одной даёт вход на
другую.

Три свойства, каждое из-за конкретной опасности.

**Ответы не различают существующий адрес и несуществующий.** Ни при
регистрации, ни при восстановлении, ни при повторной отправке. Разный ответ
превращает форму в перебор адресов.

**Токены одноразовы и истекают.** Подтверждение и восстановление хранятся
только хэшем: доступ к хранилищу не должен давать возможность подтвердить
чужой адрес или сменить чужой пароль.

**Смена пароля гасит все сессии.** Иначе украденная сессия переживает реакцию
на кражу, а смена пароля превращается в успокаивающий ритуал.
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

from factory.site_engine.mail import Mailer, Message
from factory.site_engine.operators import OperatorError as _PasswordPolicyError
from factory.site_engine.operators import hash_password as _hash_password
from factory.site_engine.operators import verify_password

CONTRACT_VERSION = "account-state/1.0.0"

VERIFY_TTL_SECONDS = 24 * 60 * 60
RESET_TTL_SECONDS = 60 * 60
#: Сколько писем одного назначения можно отправить за окно. Ограничение
#: существует не ради нагрузки: без него форма повторной отправки становится
#: способом заваливать чужой ящик.
RESEND_LIMIT = 3
RESEND_WINDOW_SECONDS = 60 * 60
LOGIN_LOCKOUT_THRESHOLD = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60

#: Текущая версия правил. Согласие хранится вместе с версией: «согласился»
#: без указания, с чем именно, юридически ничего не значит.
CONSENT_VERSION = "terms/1.0.0"


class AccountError(RuntimeError):
    """Действие над учётной записью невозможно."""


class AccountState(str, enum.Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    #: Удалено по требованию владельца. Запись остаётся тенью: адрес
    #: освобождается, персональные поля стираются, а идентификатор живёт,
    #: чтобы ссылки из журналов не превращались в загадки.
    DELETED = "DELETED"


@dataclasses.dataclass
class Account:
    account_id: str
    site_id: str
    email: str
    state: AccountState = AccountState.PENDING_VERIFICATION
    password: dict[str, Any] | None = None
    display_name: str = ""
    consent_version: str = ""
    consent_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    verified_at: str = ""
    blocked_reason: str = ""
    failed_logins: int = 0
    locked_until: float = 0.0
    sessions_valid_after: float = 0.0
    #: Одноразовые токены: только хэш и срок.
    verify_hash: str = ""
    verify_expires: float = 0.0
    reset_hash: str = ""
    reset_expires: float = 0.0
    #: Отметки отправок по назначению — для ограничения частоты.
    sends: dict[str, list[float]] = dataclasses.field(default_factory=dict)
    version: int = 1

    def as_dict(self, *, safe: bool = True) -> dict[str, Any]:
        d = {
            "accountId": self.account_id,
            "siteId": self.site_id,
            "email": self.email,
            "state": self.state.value,
            "displayName": self.display_name,
            "consentVersion": self.consent_version,
            "consentAt": self.consent_at,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "verifiedAt": self.verified_at,
            "blockedReason": self.blocked_reason,
            "version": self.version,
            "contractVersion": CONTRACT_VERSION,
        }
        if not safe:
            d.update(
                {
                    "password": self.password,
                    "verifyHash": self.verify_hash,
                    "verifyExpires": self.verify_expires,
                    "resetHash": self.reset_hash,
                    "resetExpires": self.reset_expires,
                    "failedLogins": self.failed_logins,
                    "lockedUntil": self.locked_until,
                    "sessionsValidAfter": self.sessions_valid_after,
                    "sends": self.sends,
                }
            )
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Account:
        return cls(
            account_id=d["accountId"],
            site_id=d["siteId"],
            email=d["email"],
            state=AccountState(d.get("state", "PENDING_VERIFICATION")),
            password=d.get("password"),
            display_name=d.get("displayName", ""),
            consent_version=d.get("consentVersion", ""),
            consent_at=d.get("consentAt", ""),
            created_at=d.get("createdAt", ""),
            updated_at=d.get("updatedAt", ""),
            verified_at=d.get("verifiedAt", ""),
            blocked_reason=d.get("blockedReason", ""),
            failed_logins=int(d.get("failedLogins", 0)),
            locked_until=float(d.get("lockedUntil", 0.0)),
            sessions_valid_after=float(d.get("sessionsValidAfter", 0.0)),
            verify_hash=d.get("verifyHash", ""),
            verify_expires=float(d.get("verifyExpires", 0.0)),
            reset_hash=d.get("resetHash", ""),
            reset_expires=float(d.get("resetExpires", 0.0)),
            sends={k: [float(x) for x in v] for k, v in (d.get("sends") or {}).items()},
            version=int(d.get("version", 1)),
        )


def hash_password(пароль: str) -> dict[str, Any]:
    """Тот же алгоритм, что у операторов, но своя ошибка.

    Алгоритм общий намеренно: две схемы хранения паролей в одной системе
    означают, что одна из них однажды окажется слабее. А вот тип ошибки общим
    быть не должен: исключение операторского контура, всплывшее в публичном,
    заставляет обработчик знать про чужой контур — и рано или поздно кто-то
    поймает не тот тип и пропустит отказ.
    """
    try:
        return _hash_password(пароль)
    except _PasswordPolicyError as ошибка:
        raise AccountError(str(ошибка)) from ошибка


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash(значение: str) -> str:
    return hashlib.sha256((значение or "").encode("utf-8")).hexdigest()


@dataclasses.dataclass
class AccountSession:
    sid_hash: str
    account_id: str
    site_id: str
    created_at: float
    last_seen: float
    user_agent: str = ""
    revoked_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "sessionId": self.sid_hash[:16],
            "accountId": self.account_id,
            "siteId": self.site_id,
            "createdAt": dt.datetime.fromtimestamp(self.created_at, dt.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "userAgent": self.user_agent[:120],
            "active": not self.revoked_at,
        }


class AccountDirectory:
    """Учётные записи зрителей одной установки, разложенные по витринам."""

    def __init__(self, root: Path | str, *, mailer: Mailer | None = None, now=None) -> None:
        import time

        from factory.site_engine.mail import CaptureMailer

        self._now = now or time.time
        self.root = Path(root)
        self.dir = self.root / "var" / "state" / "accounts"
        self.sessions_dir = self.dir / "sessions"
        for d in (self.dir, self.sessions_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.mailer = mailer or CaptureMailer()

    # ---- служебное ------------------------------------------------------
    @staticmethod
    def normalise_email(email: str) -> str:
        адрес = (email or "").strip().lower()
        if "@" not in адрес or адрес.startswith("@") or адрес.endswith("@"):
            raise AccountError("негодный адрес")
        return адрес

    @staticmethod
    def _id(site_id: str, email: str) -> str:
        """Ключ учитывает витрину: один адрес на двух витринах — две записи."""
        return hashlib.sha256(f"{site_id}|{email}".encode()).hexdigest()[:24]

    @staticmethod
    def _safe(идентификатор: str) -> str:
        if (
            not идентификатор
            or "/" in идентификатор
            or ".." in идентификатор
            or len(идентификатор) > 128
        ):
            raise AccountError("негодный идентификатор")
        return идентификатор

    def _write(self, путь: Path, данные: dict) -> None:
        врем = путь.with_name(f".{путь.name}.tmp")
        врем.write_text(json.dumps(данные, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(врем, путь)

    def get(self, account_id: str) -> Account:
        путь = self.dir / f"{self._safe(account_id)}.json"
        if not путь.exists():
            raise AccountError("учётной записи нет")
        return Account.from_dict(json.loads(путь.read_text(encoding="utf-8")))

    def by_email(self, site_id: str, email: str) -> Account | None:
        try:
            return self.get(self._id(site_id, self.normalise_email(email)))
        except AccountError:
            return None

    def save(self, запись: Account) -> Account:
        запись.updated_at = _now_iso()
        self._write(self.dir / f"{запись.account_id}.json", запись.as_dict(safe=False))
        return запись

    def list(
        self, *, site_id: str = "", state: str = "", offset: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        все: list[Account] = []
        for файл in sorted(self.dir.glob("*.json")):
            try:
                все.append(Account.from_dict(json.loads(файл.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
        отобрано = [
            a
            for a in все
            if (not site_id or a.site_id == site_id) and (not state or a.state.value == state)
        ]
        отобрано.sort(key=lambda a: (a.site_id, a.email))
        по_состояниям: dict[str, int] = {}
        for a in все:
            по_состояниям[a.state.value] = по_состояниям.get(a.state.value, 0) + 1
        return {
            "total": len(отобрано),
            "totalAll": len(все),
            "offset": offset,
            "limit": limit,
            "byState": по_состояниям,
            "items": [a.as_dict() for a in отобрано[offset : offset + limit]],
            "contractVersion": CONTRACT_VERSION,
        }

    # ---- ограничение частоты --------------------------------------------
    def _можно_отправить(self, запись: Account, purpose: str) -> bool:
        сейчас = float(self._now())
        окно = [t for t in запись.sends.get(purpose, []) if сейчас - t < RESEND_WINDOW_SECONDS]
        запись.sends[purpose] = окно
        return len(окно) < RESEND_LIMIT

    def _отметить_отправку(self, запись: Account, purpose: str) -> None:
        запись.sends.setdefault(purpose, []).append(float(self._now()))

    # ---- регистрация ------------------------------------------------------
    def register(
        self, *, site_id: str, email: str, password: str, consent: bool, display_name: str = ""
    ) -> dict[str, Any]:
        """Регистрация. Ответ одинаков и для нового адреса, и для занятого.

        Разный ответ превратил бы форму в способ узнать, кто зарегистрирован.
        Поэтому существующему адресу письмо тоже уходит — но с текстом «на этот
        адрес уже есть учётная запись», а не со ссылкой подтверждения.
        """
        if not consent:
            raise AccountError("нужно согласие с правилами")
        адрес = self.normalise_email(email)
        hash_password(password)  # проверка длины до всего остального

        существующая = self.by_email(site_id, адрес)
        общий = {
            "accepted": True,
            "state": "PENDING_VERIFICATION",
            "message": "Если адрес свободен, на него отправлено письмо " "с подтверждением.",
            "contractVersion": CONTRACT_VERSION,
        }
        if существующая is not None:
            if существующая.state is not AccountState.DELETED:
                if self._можно_отправить(существующая, "exists"):
                    self._отметить_отправку(существующая, "exists")
                    self.mailer.send(
                        Message(
                            to=адрес,
                            purpose="exists",
                            subject="Учётная запись уже существует",
                            body="На этот адрес уже зарегистрирована учётная запись. "
                            "Если это были не вы, ничего делать не нужно.",
                        )
                    )
                    self.save(существующая)
                return общий
            запись = существующая
            запись.state = AccountState.PENDING_VERIFICATION
        else:
            запись = Account(
                account_id=self._id(site_id, адрес),
                site_id=site_id,
                email=адрес,
                created_at=_now_iso(),
            )

        запись.password = hash_password(password)
        запись.display_name = (display_name or "").strip()[:80]
        запись.consent_version = CONSENT_VERSION
        запись.consent_at = _now_iso()
        запись.version += 1
        токен = self._выдать_токен(запись, "verify")
        self.save(запись)
        self.mailer.send(
            Message(
                to=адрес,
                purpose="verify",
                subject="Подтверждение адреса",
                body=f"Ссылка подтверждения: /account/verify?token={токен}\n"
                f"Она одноразовая и действует сутки.",
            )
        )
        return общий

    def _выдать_токен(self, запись: Account, вид: str) -> str:
        токен = secrets.token_urlsafe(32)
        срок = float(self._now()) + (VERIFY_TTL_SECONDS if вид == "verify" else RESET_TTL_SECONDS)
        if вид == "verify":
            запись.verify_hash, запись.verify_expires = _hash(токен), срок
        else:
            запись.reset_hash, запись.reset_expires = _hash(токен), срок
        self._отметить_отправку(запись, вид)
        return токен

    def verify(self, *, site_id: str, token: str) -> Account:
        отпечаток = _hash(token)
        for файл in sorted(self.dir.glob("*.json")):
            try:
                запись = Account.from_dict(json.loads(файл.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
            if запись.site_id != site_id or not запись.verify_hash:
                continue
            if not hmac.compare_digest(запись.verify_hash, отпечаток):
                continue
            if запись.verify_expires < float(self._now()):
                raise AccountError("срок ссылки истёк")
            запись.state = AccountState.ACTIVE
            запись.verified_at = _now_iso()
            # Токен одноразовый: стирается сразу, а не «когда-нибудь».
            запись.verify_hash, запись.verify_expires = "", 0.0
            запись.version += 1
            return self.save(запись)
        raise AccountError("ссылка не подходит")

    def resend_verification(self, *, site_id: str, email: str) -> dict[str, Any]:
        общий = {
            "accepted": True,
            "message": "Если адрес ожидает подтверждения, письмо отправлено.",
        }
        запись = self.by_email(site_id, email) if "@" in (email or "") else None
        if запись is None or запись.state is not AccountState.PENDING_VERIFICATION:
            return общий
        if not self._можно_отправить(запись, "verify"):
            # Ответ тот же: иначе по нему видно, что адрес существует.
            self.save(запись)
            return общий
        токен = self._выдать_токен(запись, "verify")
        self.save(запись)
        self.mailer.send(
            Message(
                to=запись.email,
                purpose="verify",
                subject="Подтверждение адреса",
                body=f"Ссылка подтверждения: /account/verify?token={токен}",
            )
        )
        return общий

    # ---- вход -------------------------------------------------------------
    def authenticate(self, *, site_id: str, email: str, password: str) -> Account:
        общий = AccountError("неверный адрес или пароль")
        try:
            адрес = self.normalise_email(email)
        except AccountError:
            raise общий from None
        запись = self.by_email(site_id, адрес)
        if запись is None:
            verify_password(password, hash_password("заглушка-для-времени"))
            raise общий
        сейчас = float(self._now())
        if запись.locked_until > сейчас or запись.state is not AccountState.ACTIVE:
            raise общий
        if not verify_password(password, запись.password):
            запись.failed_logins += 1
            if запись.failed_logins >= LOGIN_LOCKOUT_THRESHOLD:
                запись.locked_until = сейчас + LOGIN_LOCKOUT_SECONDS
                запись.failed_logins = 0
            self.save(запись)
            raise общий
        запись.failed_logins, запись.locked_until = 0, 0.0
        self.save(запись)
        return запись

    # ---- восстановление пароля -------------------------------------------
    def request_reset(self, *, site_id: str, email: str) -> dict[str, Any]:
        общий = {"accepted": True, "message": "Если адрес зарегистрирован, письмо отправлено."}
        запись = self.by_email(site_id, email) if "@" in (email or "") else None
        if запись is None or запись.state is not AccountState.ACTIVE:
            return общий
        if not self._можно_отправить(запись, "reset"):
            self.save(запись)
            return общий
        токен = self._выдать_токен(запись, "reset")
        self.save(запись)
        self.mailer.send(
            Message(
                to=запись.email,
                purpose="reset",
                subject="Смена пароля",
                body=f"Ссылка смены пароля: /account/reset?token={токен}\n"
                f"Она одноразовая и действует час.",
            )
        )
        return общий

    def reset_password(self, *, site_id: str, token: str, password: str) -> Account:
        отпечаток = _hash(token)
        for файл in sorted(self.dir.glob("*.json")):
            try:
                запись = Account.from_dict(json.loads(файл.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
            if запись.site_id != site_id or not запись.reset_hash:
                continue
            if not hmac.compare_digest(запись.reset_hash, отпечаток):
                continue
            if запись.reset_expires < float(self._now()):
                raise AccountError("срок ссылки истёк")
            запись.password = hash_password(password)
            запись.reset_hash, запись.reset_expires = "", 0.0
            # Смена пароля гасит все сессии: иначе украденная переживает
            # реакцию на кражу.
            запись.sessions_valid_after = float(self._now())
            запись.failed_logins, запись.locked_until = 0, 0.0
            запись.version += 1
            return self.save(запись)
        raise AccountError("ссылка не подходит")

    def change_password(self, account_id: str, *, current: str, new: str) -> Account:
        запись = self.get(account_id)
        if not verify_password(current, запись.password):
            raise AccountError("текущий пароль неверен")
        запись.password = hash_password(new)
        запись.sessions_valid_after = float(self._now())
        запись.version += 1
        return self.save(запись)

    # ---- профиль, блокировка, удаление -----------------------------------
    def update_profile(self, account_id: str, *, display_name: str) -> Account:
        запись = self.get(account_id)
        запись.display_name = (display_name or "").strip()[:80]
        запись.version += 1
        return self.save(запись)

    def block(self, account_id: str, *, reason: str) -> Account:
        запись = self.get(account_id)
        запись.state = AccountState.BLOCKED
        запись.blocked_reason = reason
        запись.sessions_valid_after = float(self._now())
        запись.version += 1
        return self.save(запись)

    def export(self, account_id: str) -> dict[str, Any]:
        """Выгрузка своих данных. Хэш пароля и токены сюда не входят."""
        запись = self.get(account_id)
        return {
            "account": запись.as_dict(safe=True),
            "sessions": self.list_sessions(account_id=account_id),
            "exportedAt": _now_iso(),
            "note": "хэш пароля и одноразовые токены в выгрузку не входят",
        }

    def delete(self, account_id: str) -> Account:
        """Удаление по требованию владельца. Запись остаётся тенью.

        Персональные поля стираются, адрес освобождается, идентификатор живёт:
        ссылки из журналов не должны превращаться в загадки.
        """
        запись = self.get(account_id)
        запись.state = AccountState.DELETED
        запись.password = None
        запись.display_name = ""
        запись.email = f"deleted-{запись.account_id[:12]}@invalid"
        запись.verify_hash = запись.reset_hash = ""
        запись.sessions_valid_after = float(self._now())
        запись.version += 1
        self.revoke_all_sessions(account_id)
        return self.save(запись)

    # ---- сессии -----------------------------------------------------------
    def register_session(
        self, *, sid: str, account_id: str, site_id: str, user_agent: str = ""
    ) -> AccountSession:
        сейчас = float(self._now())
        сессия = AccountSession(
            sid_hash=_hash(sid),
            account_id=account_id,
            site_id=site_id,
            created_at=сейчас,
            last_seen=сейчас,
            user_agent=user_agent,
        )
        данные = сессия.as_dict()
        данные.update({"sidHash": сессия.sid_hash, "createdAtRaw": сейчас, "revokedAtRaw": 0.0})
        self._write(self.sessions_dir / f"{сессия.sid_hash}.json", данные)
        return сессия

    def session_valid(self, sid: str, *, site_id: str = "") -> Account | None:
        путь = self.sessions_dir / f"{_hash(sid)}.json"
        if not путь.exists():
            return None
        try:
            данные = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if данные.get("revokedAtRaw"):
            return None
        # Сессия действительна только на своей витрине: cookie, украденная на
        # одной, не должна открывать другую.
        if site_id and данные.get("siteId") != site_id:
            return None
        try:
            запись = self.get(данные["accountId"])
        except AccountError:
            return None
        if запись.state is not AccountState.ACTIVE:
            return None
        if float(данные.get("createdAtRaw", 0)) < запись.sessions_valid_after:
            return None
        return запись

    def list_sessions(self, *, account_id: str) -> list[dict[str, Any]]:
        итог = []
        for файл in sorted(self.sessions_dir.glob("*.json")):
            try:
                данные = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if данные.get("accountId") != account_id or данные.get("revokedAtRaw"):
                continue
            итог.append(
                {k: v for k, v in данные.items() if not k.endswith("Raw") and k != "sidHash"}
            )
        return итог

    def revoke_session(self, session_id: str, *, account_id: str) -> bool:
        for файл in sorted(self.sessions_dir.glob("*.json")):
            try:
                данные = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            # Чужую сессию отозвать нельзя: проверяется владелец, а не только
            # идентификатор.
            if данные.get("sessionId") != session_id or данные.get("accountId") != account_id:
                continue
            if данные.get("revokedAtRaw"):
                return False
            данные["revokedAtRaw"] = float(self._now())
            данные["active"] = False
            self._write(файл, данные)
            return True
        return False

    def revoke_all_sessions(self, account_id: str) -> int:
        запись = self.get(account_id)
        запись.sessions_valid_after = float(self._now())
        self.save(запись)
        сколько = 0
        for файл in sorted(self.sessions_dir.glob("*.json")):
            try:
                данные = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if данные.get("accountId") != account_id or данные.get("revokedAtRaw"):
                continue
            данные["revokedAtRaw"] = float(self._now())
            данные["active"] = False
            self._write(файл, данные)
            сколько += 1
        return сколько
