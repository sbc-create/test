"""Вход владельца по passkey и восстановление по одноразовым кодам.

Пароля в панели нет ни в каком виде. Владелец подтверждает себя ключом,
который никогда не покидает его устройство: браузер подписывает challenge, а
панель проверяет подпись публичным ключом, сохранённым при регистрации.

Почему именно WebAuthn, а не пароль: пароль нужно где-то хранить, куда-то
вводить и как-то восстанавливать — и каждый из трёх шагов создаёт способ его
украсть. Подпись по challenge не переиспользуется, не подбирается и не
фишится: браузер не отдаст её сайту с другим origin.

Три церемонии:

``register``
    Добавление passkey. Разрешена в двух случаях: по одноразовому коду
    первичной регистрации (его печатает root-установка) либо владельцем,
    который уже вошёл. Иначе кто угодно добавил бы себе ключ.

``authenticate``
    Вход. Challenge выдаётся сервером, гасится при использовании, подпись
    проверяется, счётчик подписей не должен идти назад.

``recover``
    Вход по одноразовому коду, когда устройство с passkey недоступно. Код
    гасится и даёт ровно одну возможность — зарегистрировать новый passkey.

Проверка ``rp_id`` и ``origin`` строгая: RP ID — домен панели, origin — его
HTTPS-адрес. Ошибка здесь означала бы, что подпись, добытую на чужом сайте,
можно предъявить нашему.
"""
from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass

from factory.secret_hub.panel import RECOVERY_CODE_COUNT
from factory.secret_hub.panel.store import PanelStore, generate_code

#: Ограничения частоты. Считаются по «корзинам» в базе панели.
LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_ATTEMPTS = 10
RECOVERY_WINDOW_SECONDS = 900
RECOVERY_MAX_ATTEMPTS = 5
ENROLL_WINDOW_SECONDS = 900
ENROLL_MAX_ATTEMPTS = 5


class AuthError(RuntimeError):
    """Церемония не прошла. Текст пригоден для показа владельцу."""


class RateLimited(AuthError):
    """Слишком много попыток. Отдельный класс — чтобы вернуть 429."""


@dataclass(frozen=True)
class RelyingParty:
    """Кто мы с точки зрения браузера."""

    rp_id: str
    rp_name: str
    origin: str

    @classmethod
    def for_domain(cls, server_name: str, name: str = "Secret Hub") -> RelyingParty:
        return cls(rp_id=server_name, rp_name=name, origin=f"https://{server_name}")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _guard(store: PanelStore, bucket: str, window: int, limit: int) -> None:
    if store.attempts_within(bucket, window) >= limit:
        raise RateLimited(
            "Слишком много попыток. Подождите несколько минут и попробуйте снова."
        )
    store.record_attempt(bucket)


# --- регистрация ----------------------------------------------------------
def begin_registration(store: PanelStore, rp: RelyingParty, *, label: str = "") -> dict:
    """Опции для ``navigator.credentials.create``.

    Уже зарегистрированные ключи уходят в ``excludeCredentials``: браузер не
    даст зарегистрировать тот же аутентификатор дважды и не создаст владельцу
    иллюзию второго независимого ключа.
    """
    from webauthn import generate_registration_options
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )

    existing = [PublicKeyCredentialDescriptor(id=_unb64(p.credential_id))
                for p in store.passkeys()]
    options = generate_registration_options(
        rp_id=rp.rp_id,
        rp_name=rp.rp_name,
        # Владелец один. Стабильный user_id нужен, чтобы passkey'и складывались
        # в одну учётную запись, а не в разные при каждой регистрации.
        user_id=b"secret-hub-owner",
        user_name="owner",
        user_display_name="Владелец Secret Hub",
        exclude_credentials=existing,
        authenticator_selection=AuthenticatorSelectionCriteria(
            # resident key: вход без ввода имени пользователя — владелец просто
            # нажимает «Войти» и подтверждает Touch ID.
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    challenge_id = store.put_challenge(options.challenge, "register")
    return {
        "challenge_id": challenge_id,
        "publicKey": {
            "rp": {"id": rp.rp_id, "name": rp.rp_name},
            "user": {
                "id": _b64(options.user.id),
                "name": options.user.name,
                "displayName": options.user.display_name,
            },
            "challenge": _b64(options.challenge),
            "pubKeyCredParams": [{"type": "public-key", "alg": int(p.alg)}
                                 for p in options.pub_key_cred_params],
            "timeout": options.timeout,
            "attestation": "none",
            "excludeCredentials": [{"type": "public-key", "id": _b64(c.id)}
                                   for c in existing],
            "authenticatorSelection": {
                "residentKey": "preferred",
                "userVerification": "preferred",
            },
        },
        "label": label,
    }


def finish_registration(store: PanelStore, rp: RelyingParty, challenge_id: str,
                        credential: dict, *, label: str = "") -> dict:
    """Проверяет ответ аутентификатора и сохраняет публичный ключ."""
    from webauthn import verify_registration_response

    expected = store.take_challenge(challenge_id, "register")
    if expected is None:
        raise AuthError("Срок регистрации истёк или запрос повторён. Начните заново.")
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=expected,
            expected_rp_id=rp.rp_id,
            expected_origin=rp.origin,
        )
    except Exception as exc:
        # Текст библиотеки не пробрасывается владельцу дословно: он технический и
        # ничего ему не говорит. В журнал уходит класс ошибки, не содержимое.
        raise AuthError(f"Ключ не принят ({exc.__class__.__name__}).") from None

    store.add_passkey(
        credential_id=_b64(verified.credential_id),
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        label=label or "passkey",
    )
    return {"credential_id": _b64(verified.credential_id)[:12] + "…", "label": label}


# --- вход -----------------------------------------------------------------
def begin_authentication(store: PanelStore, rp: RelyingParty) -> dict:
    from webauthn import generate_authentication_options
    from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement

    if not store.has_passkey():
        raise AuthError("Ни одного passkey не зарегистрировано.")
    allowed = [PublicKeyCredentialDescriptor(id=_unb64(p.credential_id))
               for p in store.passkeys()]
    options = generate_authentication_options(
        rp_id=rp.rp_id,
        allow_credentials=allowed,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    challenge_id = store.put_challenge(options.challenge, "authenticate")
    return {
        "challenge_id": challenge_id,
        "publicKey": {
            "challenge": _b64(options.challenge),
            "rpId": rp.rp_id,
            "timeout": options.timeout,
            "userVerification": "preferred",
            "allowCredentials": [{"type": "public-key", "id": _b64(c.id)} for c in allowed],
        },
    }


def finish_authentication(store: PanelStore, rp: RelyingParty, challenge_id: str,
                          credential: dict, *, bucket: str = "login") -> None:
    """Проверяет подпись. Успех — вызывающий создаёт сессию."""
    from webauthn import verify_authentication_response

    _guard(store, bucket, LOGIN_WINDOW_SECONDS, LOGIN_MAX_ATTEMPTS)

    expected = store.take_challenge(challenge_id, "authenticate")
    if expected is None:
        raise AuthError("Срок входа истёк или запрос повторён. Обновите страницу.")

    raw_id = credential.get("rawId") or credential.get("id") or ""
    passkey = store.passkey(raw_id)
    if passkey is None:
        raise AuthError("Этот ключ не зарегистрирован.")

    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=expected,
            expected_rp_id=rp.rp_id,
            expected_origin=rp.origin,
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
        )
    except Exception as exc:
        raise AuthError(f"Подпись не принята ({exc.__class__.__name__}).") from None

    # Счётчик, пошедший назад, — признак клонированного аутентификатора.
    # Аутентификаторы, которые счётчик не ведут, всегда отдают 0: для них
    # проверка не применяется, и это штатное поведение спецификации.
    if verified.new_sign_count and verified.new_sign_count <= passkey.sign_count:
        raise AuthError("Счётчик подписей не вырос: ключ мог быть скопирован.")
    store.update_sign_count(passkey.credential_id, verified.new_sign_count)
    store.clear_attempts(bucket)


# --- recovery -------------------------------------------------------------
def issue_recovery_codes(store: PanelStore) -> list[str]:
    """Новый набор кодов. Показывается владельцу ровно один раз.

    Прежние коды при этом гаснут: два действующих набора означали бы, что
    старый листок, забытый в переписке или в почте, продолжает открывать вход.
    """
    codes = [generate_code(groups=3, size=5) for _ in range(RECOVERY_CODE_COUNT)]
    store.replace_recovery_codes(codes)
    return codes


def use_recovery_code(store: PanelStore, code: str, *, bucket: str = "recovery") -> None:
    """Гасит код. Успех даёт право зарегистрировать новый passkey."""
    _guard(store, bucket, RECOVERY_WINDOW_SECONDS, RECOVERY_MAX_ATTEMPTS)
    if not store.consume_recovery_code(code.strip().upper()):
        raise AuthError("Код восстановления неверен или уже использован.")
    store.clear_attempts(bucket)


def use_enrollment_code(store: PanelStore, code: str, *, bucket: str = "enroll") -> None:
    """Код первичной регистрации из root-консоли."""
    _guard(store, bucket, ENROLL_WINDOW_SECONDS, ENROLL_MAX_ATTEMPTS)
    if not store.consume_enrollment(code.strip().upper()):
        raise AuthError("Код регистрации неверен, истёк или уже использован.")
    store.clear_attempts(bucket)


def status(store: PanelStore) -> dict:
    """Состояние аутентификации для страницы. Ключей и кодов здесь нет."""
    return {
        "passkeys": [p.as_dict() for p in store.passkeys()],
        "passkey_count": len(store.passkeys()),
        "recovery": store.recovery_status(),
        "enrollment_open": store.enrollment_open(),
    }


def new_csrf() -> str:
    return secrets.token_urlsafe(32)
