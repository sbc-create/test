"""Шифрование, мастер-ключ и права файлов Secret Hub.

Проверяется не «функция вызывается без ошибки», а свойства, ради которых модуль
существует: неверный ключ отказывает явно, подменённый шифртекст не проходит,
значение нельзя напечатать, а файл ключа с открытыми правами не читается.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from factory.secret_hub import crypto


def _key_file(tmp_path: Path, value: str | None = None, mode: int = 0o600) -> Path:
    path = tmp_path / "master.key"
    # `value is None`, а не `value or ...`: пустая строка — это ровно тот случай,
    # который проверяет тест про пустой файл, и подставлять вместо неё
    # сгенерированный ключ значило бы проверять не то.
    path.write_text(crypto.generate_master_key() if value is None else value, encoding="utf-8")
    os.chmod(path, mode)
    return path


def _load(path: Path) -> crypto.MasterKey:
    # require_root_owner=False: временные файлы принадлежат тестовому
    # пользователю, а не root. Права 0600 при этом проверяются как в бою.
    return crypto.load_master_key(path, require_root_owner=False)


class TestRoundTrip:
    def test_encrypt_decrypt_returns_same_value(self, tmp_path):
        master = _load(_key_file(tmp_path))
        material = crypto.Secret("значение-токена-1234567890", label="t")
        envelope = crypto.encrypt(master, material, aad=b"yami|api_token|1")
        restored = crypto.decrypt(master, envelope, aad=b"yami|api_token|1")
        assert restored.reveal() == "значение-токена-1234567890"

    def test_ciphertext_does_not_contain_plaintext(self, tmp_path):
        master = _load(_key_file(tmp_path))
        material = crypto.Secret("PLAINTEXT-MARKER-9876543210", label="t")
        envelope = crypto.encrypt(master, material, aad=b"a|b|1")
        assert b"PLAINTEXT-MARKER" not in envelope.ciphertext
        assert "PLAINTEXT-MARKER" not in repr(envelope)

    def test_same_value_encrypts_differently_each_time(self, tmp_path):
        """Одинаковые значения обязаны давать разный шифртекст.

        Иначе по совпадению шифртекстов видно, что у двух направлений один и
        тот же токен, — а это уже утечка, пусть и частичная.
        """
        master = _load(_key_file(tmp_path))
        first = crypto.encrypt(master, crypto.Secret("одинаковое", "a"), aad=b"x|y|1")
        second = crypto.encrypt(master, crypto.Secret("одинаковое", "b"), aad=b"x|y|1")
        assert first.ciphertext != second.ciphertext
        assert first.salt != second.salt


class TestWrongKey:
    def test_wrong_master_key_is_explicit_refusal(self, tmp_path):
        """Неверный ключ обязан отказать, а не вернуть пустое или мусорное значение."""
        good = _load(_key_file(tmp_path))
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        bad = _load(_key_file(other_dir))
        envelope = crypto.encrypt(good, crypto.Secret("секрет", "t"), aad=b"a|b|1")

        with pytest.raises(crypto.MasterKeyError) as excinfo:
            crypto.decrypt(bad, envelope, aad=b"a|b|1")
        assert excinfo.value.status == "BLOCKED_SECRET"
        assert "не расшифровано" in excinfo.value.reason

    def test_key_ids_differ_between_keys(self, tmp_path):
        first = _load(_key_file(tmp_path))
        second_dir = tmp_path / "second"
        second_dir.mkdir()
        second = _load(_key_file(second_dir))
        assert first.key_id() != second.key_id()

    def test_tampered_ciphertext_is_rejected(self, tmp_path):
        """AES-GCM аутентифицирует: подмена байта в базе обязана быть замечена."""
        master = _load(_key_file(tmp_path))
        envelope = crypto.encrypt(master, crypto.Secret("значение", "t"), aad=b"a|b|1")
        broken = crypto.Envelope(
            envelope.scheme, envelope.salt, envelope.nonce,
            bytes([envelope.ciphertext[0] ^ 0x01]) + envelope.ciphertext[1:],
            envelope.key_id,
        )
        with pytest.raises(crypto.MasterKeyError):
            crypto.decrypt(master, broken, aad=b"a|b|1")

    def test_moving_ciphertext_between_records_is_rejected(self, tmp_path):
        """Перенос шифртекста в чужую запись не должен расшифровываться.

        Это и есть смысл aad: без него строку из `lords/api_token` можно было бы
        подставить в `yami/api_token` прямо в SQLite, и оба направления начали бы
        работать на одном токене без единого следа.
        """
        master = _load(_key_file(tmp_path))
        envelope = crypto.encrypt(master, crypto.Secret("токен-lords", "t"),
                                  aad=b"secret-hub/v1|lords|api_token|1")
        with pytest.raises(crypto.MasterKeyError):
            crypto.decrypt(master, envelope, aad=b"secret-hub/v1|yami|api_token|1")


class TestSecretNeverPrints:
    def test_str_repr_format_are_redacted(self):
        material = crypto.Secret("СЕКРЕТНОЕ-ЗНАЧЕНИЕ", "t")
        assert "СЕКРЕТНОЕ" not in str(material)
        assert "СЕКРЕТНОЕ" not in repr(material)
        assert "СЕКРЕТНОЕ" not in f"{material}"
        assert "СЕКРЕТНОЕ" not in "{}".format(material)  # noqa: UP032 - проверяется __format__

    def test_secret_cannot_be_pickled(self):
        import pickle

        with pytest.raises(TypeError):
            pickle.dumps(crypto.Secret("значение", "t"))

    def test_master_key_never_prints(self, tmp_path):
        raw = crypto.generate_master_key()
        master = _load(_key_file(tmp_path, raw))
        assert raw not in repr(master)
        assert raw not in str(master)
        assert raw not in master.key_id()

    def test_fingerprint_is_irreversible_and_stable(self):
        material = crypto.Secret("значение-для-отпечатка", "t")
        again = crypto.Secret("значение-для-отпечатка", "t")
        assert material.fingerprint() == again.fingerprint()
        assert "значение" not in material.fingerprint()
        assert crypto.Secret("другое", "t").fingerprint() != material.fingerprint()


class TestKeyFilePermissions:
    @pytest.mark.parametrize("mode", [0o644, 0o640, 0o660, 0o604])
    def test_group_or_world_readable_key_is_refused(self, tmp_path, mode):
        path = _key_file(tmp_path, mode=mode)
        with pytest.raises(crypto.MasterKeyError) as excinfo:
            _load(path)
        assert "группе или миру" in excinfo.value.reason

    def test_missing_key_file_is_refused(self, tmp_path):
        with pytest.raises(crypto.MasterKeyError) as excinfo:
            _load(tmp_path / "нет-такого")
        assert "не найден" in excinfo.value.reason

    def test_empty_key_file_is_refused(self, tmp_path):
        path = _key_file(tmp_path, value="")
        with pytest.raises(crypto.MasterKeyError) as excinfo:
            _load(path)
        assert "пуст" in excinfo.value.reason

    def test_wrong_length_key_is_refused(self, tmp_path):
        path = _key_file(tmp_path, value="ab" * 8)  # 8 байт вместо 32
        with pytest.raises(crypto.MasterKeyError) as excinfo:
            _load(path)
        assert "hex или base64" in excinfo.value.reason

    def test_inspect_does_not_read_contents(self, tmp_path):
        raw = crypto.generate_master_key()
        status = crypto.inspect_key_file(_key_file(tmp_path, raw))
        serialized = str(status.as_dict())
        assert raw not in serialized
        assert status.mode == "0600"

    def test_key_inside_repository_is_refused(self, tmp_path, repo_root):
        inside = repo_root / "var" / "test-master.key"
        inside.parent.mkdir(parents=True, exist_ok=True)
        inside.write_text(crypto.generate_master_key(), encoding="utf-8")
        os.chmod(inside, 0o600)
        try:
            with pytest.raises(crypto.MasterKeyError) as excinfo:
                _load(inside)
            assert "внутрь репозитория" in excinfo.value.reason
        finally:
            inside.unlink()


class TestForbiddenEnvironment:
    @pytest.mark.parametrize("name", sorted(crypto.FORBIDDEN_VALUE_ENV))
    def test_value_in_environment_blocks_load(self, tmp_path, monkeypatch, name):
        """Значение в переменной окружения — ошибка, а не удобный обходной путь."""
        monkeypatch.setenv(name, "значение-которого-тут-быть-не-должно")
        with pytest.raises(crypto.MasterKeyError) as excinfo:
            _load(_key_file(tmp_path))
        assert name in excinfo.value.reason

    def test_forbidden_env_list_covers_both_credential_fields(self):
        assert "CDNVIDEOHUB_API_TOKEN" in crypto.FORBIDDEN_VALUE_ENV
        assert "CDNVIDEOHUB_PUBLISHER_ID" in crypto.FORBIDDEN_VALUE_ENV


class TestGeneratedKey:
    def test_generated_key_has_required_length(self):
        assert len(bytes.fromhex(crypto.generate_master_key())) == crypto.KEY_BYTES

    def test_generated_keys_differ(self):
        assert crypto.generate_master_key() != crypto.generate_master_key()
