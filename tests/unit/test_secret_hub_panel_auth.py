"""WebAuthn, recovery-коды и ограничение частоты в панели.

Церемонии проверяются настоящей криптографией: тест реализует программный
аутентификатор — генерирует ключ на P-256, собирает `clientDataJSON` и
`authenticatorData`, подписывает и отдаёт то же, что отдал бы Touch ID. Это
единственный способ доказать, что проверка подписи действительно работает: с
подделанной библиотекой тест доказывал бы только сам себя.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import struct

import pytest

from factory.secret_hub.panel import auth as auth_mod
from factory.secret_hub.panel.store import PanelStore

RP_ID = "yummyani.site"
ORIGIN = "https://yummyani.site"


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class SoftAuthenticator:
    """Программный аутентификатор: делает ровно то, что делает настоящий."""

    def __init__(self, rp_id: str = RP_ID, origin: str = ORIGIN) -> None:
        from cryptography.hazmat.primitives.asymmetric import ec

        self.rp_id = rp_id
        self.origin = origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.sign_count = 0

    # --- COSE ------------------------------------------------------------
    def _cose_key(self) -> bytes:
        numbers = self.key.public_key().public_numbers()
        x = numbers.x.to_bytes(32, "big")
        y = numbers.y.to_bytes(32, "big")
        # CBOR-карта из пяти пар: kty=2 (EC2), alg=-7 (ES256), crv=1 (P-256), x, y.
        return (b"\xa5"
                b"\x01\x02"
                b"\x03\x26"
                b"\x20\x01"
                b"\x21\x58\x20" + x +
                b"\x22\x58\x20" + y)

    def _auth_data(self, *, include_attested: bool, flags: int) -> bytes:
        rp_hash = hashlib.sha256(self.rp_id.encode()).digest()
        data = rp_hash + bytes([flags]) + struct.pack(">I", self.sign_count)
        if include_attested:
            cose = self._cose_key()
            data += (b"\x00" * 16
                     + struct.pack(">H", len(self.credential_id))
                     + self.credential_id + cose)
        return data

    def _client_data(self, kind: str, challenge: str) -> bytes:
        return json.dumps({"type": kind, "challenge": challenge,
                           "origin": self.origin, "crossOrigin": False}).encode()

    # --- церемонии --------------------------------------------------------
    def create(self, challenge_b64: str) -> dict:
        client_data = self._client_data("webauthn.create", challenge_b64)
        # flags: UP | UV | AT
        auth_data = self._auth_data(include_attested=True, flags=0x01 | 0x04 | 0x40)
        attestation = (b"\xa3"
                       b"\x63fmt\x64none"
                       b"\x67attStmt\xa0"
                       b"\x68authData\x59" + struct.pack(">H", len(auth_data)) + auth_data)
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client_data),
                "attestationObject": b64(attestation),
            },
        }

    def get(self, challenge_b64: str, *, bump: int = 1) -> dict:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        self.sign_count += bump
        client_data = self._client_data("webauthn.get", challenge_b64)
        auth_data = self._auth_data(include_attested=False, flags=0x01 | 0x04)
        signed = auth_data + hashlib.sha256(client_data).digest()
        signature = self.key.sign(signed, ec.ECDSA(hashes.SHA256()))
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client_data),
                "authenticatorData": b64(auth_data),
                "signature": b64(signature),
                "userHandle": None,
            },
        }


@pytest.fixture
def store(tmp_path):
    with PanelStore(tmp_path / "panel" / "panel.sqlite3") as opened:
        yield opened


@pytest.fixture
def rp():
    return auth_mod.RelyingParty.for_domain(RP_ID)


def register(store, rp, authenticator: SoftAuthenticator) -> None:
    options = auth_mod.begin_registration(store, rp)
    credential = authenticator.create(options["publicKey"]["challenge"])
    auth_mod.finish_registration(store, rp, options["challenge_id"], credential)


class TestRegistration:
    def test_passkey_is_registered_and_stored(self, store, rp):
        assert store.has_passkey() is False
        register(store, rp, SoftAuthenticator())
        assert store.has_passkey() is True
        assert len(store.passkeys()) == 1

    def test_only_public_key_is_stored(self, store, rp):
        """В базе панели лежит публичный ключ — приватный остаётся у устройства."""
        authenticator = SoftAuthenticator()
        register(store, rp, authenticator)
        blob = store.db_path.read_bytes()

        from cryptography.hazmat.primitives import serialization

        private = authenticator.key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        assert private not in blob

    def test_registration_challenge_cannot_be_replayed(self, store, rp):
        """Повторное использование challenge обязано быть отвергнуто."""
        authenticator = SoftAuthenticator()
        options = auth_mod.begin_registration(store, rp)
        credential = authenticator.create(options["publicKey"]["challenge"])
        auth_mod.finish_registration(store, rp, options["challenge_id"], credential)

        with pytest.raises(auth_mod.AuthError) as excinfo:
            auth_mod.finish_registration(store, rp, options["challenge_id"], credential)
        assert "истёк" in str(excinfo.value) or "повторён" in str(excinfo.value)

    def test_registration_from_wrong_origin_is_refused(self, store, rp):
        rogue = SoftAuthenticator(origin="https://evil.example")
        options = auth_mod.begin_registration(store, rp)
        credential = rogue.create(options["publicKey"]["challenge"])
        with pytest.raises(auth_mod.AuthError):
            auth_mod.finish_registration(store, rp, options["challenge_id"], credential)

    def test_registration_with_wrong_rp_id_is_refused(self, store, rp):
        rogue = SoftAuthenticator(rp_id="evil.example")
        options = auth_mod.begin_registration(store, rp)
        credential = rogue.create(options["publicKey"]["challenge"])
        with pytest.raises(auth_mod.AuthError):
            auth_mod.finish_registration(store, rp, options["challenge_id"], credential)

    def test_existing_keys_are_excluded(self, store, rp):
        register(store, rp, SoftAuthenticator())
        options = auth_mod.begin_registration(store, rp)
        assert len(options["publicKey"]["excludeCredentials"]) == 1


class TestAuthentication:
    def test_registered_key_authenticates(self, store, rp):
        authenticator = SoftAuthenticator()
        register(store, rp, authenticator)
        options = auth_mod.begin_authentication(store, rp)
        credential = authenticator.get(options["publicKey"]["challenge"])
        auth_mod.finish_authentication(store, rp, options["challenge_id"], credential)

    def test_authentication_challenge_cannot_be_replayed(self, store, rp):
        """Перехваченный ответ не должен работать второй раз."""
        authenticator = SoftAuthenticator()
        register(store, rp, authenticator)
        options = auth_mod.begin_authentication(store, rp)
        credential = authenticator.get(options["publicKey"]["challenge"])
        auth_mod.finish_authentication(store, rp, options["challenge_id"], credential)

        with pytest.raises(auth_mod.AuthError):
            auth_mod.finish_authentication(store, rp, options["challenge_id"], credential)

    def test_unknown_key_is_refused(self, store, rp):
        register(store, rp, SoftAuthenticator())
        stranger = SoftAuthenticator()
        options = auth_mod.begin_authentication(store, rp)
        credential = stranger.get(options["publicKey"]["challenge"])
        with pytest.raises(auth_mod.AuthError) as excinfo:
            auth_mod.finish_authentication(store, rp, options["challenge_id"], credential)
        assert "не зарегистрирован" in str(excinfo.value)

    def test_forged_signature_is_refused(self, store, rp):
        """Подпись чужим ключом при том же credential_id не проходит."""
        authenticator = SoftAuthenticator()
        register(store, rp, authenticator)

        forger = SoftAuthenticator()
        forger.credential_id = authenticator.credential_id
        options = auth_mod.begin_authentication(store, rp)
        credential = forger.get(options["publicKey"]["challenge"])
        with pytest.raises(auth_mod.AuthError) as excinfo:
            auth_mod.finish_authentication(store, rp, options["challenge_id"], credential)
        assert "не принята" in str(excinfo.value)

    def test_sign_count_going_backwards_is_refused(self, store, rp):
        """Счётчик, не выросший, — признак клонированного аутентификатора.

        Отказ обязателен; на каком слое он произойдёт — деталь. Библиотека
        отвергает такой ответ сама, наша проверка в `finish_authentication`
        остаётся вторым рубежом на случай, если поведение библиотеки
        изменится. Поэтому тест требует отказа, а не конкретной формулировки.
        """
        authenticator = SoftAuthenticator()
        register(store, rp, authenticator)
        first = auth_mod.begin_authentication(store, rp)
        auth_mod.finish_authentication(store, rp, first["challenge_id"],
                                       authenticator.get(first["publicKey"]["challenge"]))
        assert store.passkey(b64(authenticator.credential_id)).sign_count > 0

        second = auth_mod.begin_authentication(store, rp)
        clone = authenticator.get(second["publicKey"]["challenge"], bump=-1)
        with pytest.raises(auth_mod.AuthError):
            auth_mod.finish_authentication(store, rp, second["challenge_id"], clone)

    def test_our_own_sign_count_guard_rejects_a_stale_counter(self, store, rp):
        """Второй рубеж проверяется отдельно, без участия библиотеки."""
        authenticator = SoftAuthenticator()
        register(store, rp, authenticator)
        credential_id = b64(authenticator.credential_id)
        store.update_sign_count(credential_id, 500)

        options = auth_mod.begin_authentication(store, rp)
        authenticator.sign_count = 400
        credential = authenticator.get(options["publicKey"]["challenge"], bump=0)
        with pytest.raises(auth_mod.AuthError):
            auth_mod.finish_authentication(store, rp, options["challenge_id"], credential)
        assert store.passkey(credential_id).sign_count == 500, \
            "счётчик не должен откатываться назад"

    def test_authentication_without_passkeys_is_refused(self, store, rp):
        with pytest.raises(auth_mod.AuthError):
            auth_mod.begin_authentication(store, rp)


class TestRecoveryCodes:
    def test_codes_are_stored_only_as_hashes(self, store):
        codes = auth_mod.issue_recovery_codes(store)
        blob = store.db_path.read_bytes()
        for code in codes:
            assert code.encode() not in blob, "код восстановления лежит в базе открытым"

    def test_each_code_works_once(self, store):
        codes = auth_mod.issue_recovery_codes(store)
        auth_mod.use_recovery_code(store, codes[0])
        with pytest.raises(auth_mod.AuthError):
            auth_mod.use_recovery_code(store, codes[0])

    def test_other_codes_still_work_after_one_is_used(self, store):
        codes = auth_mod.issue_recovery_codes(store)
        auth_mod.use_recovery_code(store, codes[0])
        auth_mod.use_recovery_code(store, codes[1])

    def test_wrong_code_is_refused(self, store):
        auth_mod.issue_recovery_codes(store)
        with pytest.raises(auth_mod.AuthError):
            auth_mod.use_recovery_code(store, "ZZZZZ-ZZZZZ-ZZZZZ")

    def test_issuing_new_codes_kills_the_old_set(self, store):
        """Два действующих набора означали бы, что старый листок всё ещё открывает вход."""
        old = auth_mod.issue_recovery_codes(store)
        auth_mod.issue_recovery_codes(store)
        with pytest.raises(auth_mod.AuthError):
            auth_mod.use_recovery_code(store, old[0])

    def test_status_counts_without_revealing(self, store):
        codes = auth_mod.issue_recovery_codes(store)
        auth_mod.use_recovery_code(store, codes[0])
        status = store.recovery_status()
        assert status["total"] == len(codes)
        assert status["used"] == 1
        assert status["left"] == len(codes) - 1
        assert codes[0] not in str(status)


class TestEnrollment:
    def test_enrollment_code_works_once(self, store):
        code = store.create_enrollment(ttl_seconds=900)
        auth_mod.use_enrollment_code(store, code)
        with pytest.raises(auth_mod.AuthError):
            auth_mod.use_enrollment_code(store, code)

    def test_enrollment_code_is_hashed(self, store):
        code = store.create_enrollment(ttl_seconds=900)
        assert code.encode() not in store.db_path.read_bytes()

    def test_expired_enrollment_is_refused(self, store):
        code = store.create_enrollment(ttl_seconds=-1)
        with pytest.raises(auth_mod.AuthError):
            auth_mod.use_enrollment_code(store, code)

    def test_enrollment_open_reflects_state(self, store):
        assert store.enrollment_open() is False
        code = store.create_enrollment(ttl_seconds=900)
        assert store.enrollment_open() is True
        auth_mod.use_enrollment_code(store, code)
        assert store.enrollment_open() is False


class TestRateLimit:
    def test_login_attempts_are_capped(self, store, rp):
        register(store, rp, SoftAuthenticator())
        stranger = SoftAuthenticator()
        for _ in range(auth_mod.LOGIN_MAX_ATTEMPTS):
            options = auth_mod.begin_authentication(store, rp)
            with pytest.raises(auth_mod.AuthError):
                auth_mod.finish_authentication(store, rp, options["challenge_id"],
                                               stranger.get(options["publicKey"]["challenge"]))
        options = auth_mod.begin_authentication(store, rp)
        with pytest.raises(auth_mod.RateLimited):
            auth_mod.finish_authentication(store, rp, options["challenge_id"],
                                           stranger.get(options["publicKey"]["challenge"]))

    def test_recovery_attempts_are_capped(self, store):
        auth_mod.issue_recovery_codes(store)
        for _ in range(auth_mod.RECOVERY_MAX_ATTEMPTS):
            with pytest.raises(auth_mod.AuthError):
                auth_mod.use_recovery_code(store, "ZZZZZ-ZZZZZ-ZZZZZ")
        with pytest.raises(auth_mod.RateLimited):
            auth_mod.use_recovery_code(store, "ZZZZZ-ZZZZZ-ZZZZZ")

    def test_successful_login_clears_the_counter(self, store, rp):
        authenticator = SoftAuthenticator()
        register(store, rp, authenticator)
        stranger = SoftAuthenticator()
        for _ in range(auth_mod.LOGIN_MAX_ATTEMPTS - 1):
            options = auth_mod.begin_authentication(store, rp)
            with pytest.raises(auth_mod.AuthError):
                auth_mod.finish_authentication(store, rp, options["challenge_id"],
                                               stranger.get(options["publicKey"]["challenge"]))
        options = auth_mod.begin_authentication(store, rp)
        auth_mod.finish_authentication(store, rp, options["challenge_id"],
                                       authenticator.get(options["publicKey"]["challenge"]))
        assert store.attempts_within("login", auth_mod.LOGIN_WINDOW_SECONDS) == 0


class TestChallengeStore:
    def test_challenge_is_single_use(self, store):
        challenge_id = store.put_challenge(b"x" * 32, "register")
        assert store.take_challenge(challenge_id, "register") == b"x" * 32
        assert store.take_challenge(challenge_id, "register") is None

    def test_challenge_purpose_is_checked(self, store):
        """Challenge для входа нельзя предъявить как challenge для регистрации."""
        challenge_id = store.put_challenge(b"y" * 32, "authenticate")
        assert store.take_challenge(challenge_id, "register") is None

    def test_expired_challenge_is_refused(self, store, monkeypatch):
        import time as time_mod

        challenge_id = store.put_challenge(b"z" * 32, "register")
        real = time_mod.time
        monkeypatch.setattr(time_mod, "time",
                            lambda: real() + 10_000)
        assert store.take_challenge(challenge_id, "register") is None


class TestPanelStorePermissions:
    def test_database_is_closed_to_group_and_world(self, store):
        import stat as stat_mod

        assert stat_mod.S_IMODE(store.db_path.stat().st_mode) == 0o600
        assert stat_mod.S_IMODE(store.db_path.parent.stat().st_mode) == 0o700
        assert store.check_permissions() == []
