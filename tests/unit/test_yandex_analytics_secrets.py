"""REQ-ANALYTICS-SECRET: значение OAuth-токена не покидает процесс.

Файл проверяет не «в коде есть слово redact», а поведение: токен не попадает в
repr, str, форматирование, сообщение исключения, аудит, отчёт, сериализацию и
журнал отказов. Каждый из этих путей однажды был способом утечки в реальных
системах, поэтому проверяется каждый, а не «в целом безопасно».
"""
from __future__ import annotations

import json
import os
import pickle

import pytest

from factory.analytics import credentials as creds
from factory.errors import BlockedSecret
from factory.redaction import PLACEHOLDER, forget_secrets, redact, redact_obj

SECRET = "y0_AgAAAABtestTOKENvalue1234567890abcdef"


@pytest.fixture
def token_file(tmp_path, monkeypatch):
    path = tmp_path / "yandex_oauth_token"
    path.write_text(SECRET + "\n", encoding="utf-8")
    path.chmod(0o600)
    monkeypatch.setenv(creds.TOKEN_FILE_ENV, str(path))
    for name in creds.FORBIDDEN_VALUE_ENV:
        monkeypatch.delenv(name, raising=False)
    yield path
    forget_secrets()


@pytest.fixture
def token(token_file):
    return creds.load_token(token_file, require_root_owner=False)


# ---------------------------------------------------------------- носитель
def test_token_never_prints_its_value(token):
    assert SECRET not in repr(token)
    assert SECRET not in str(token)
    assert SECRET not in f"{token}"
    assert SECRET not in "{}".format(token)  # noqa: UP032 — проверяется именно format
    assert SECRET not in f"токен: {token!r}"
    assert PLACEHOLDER in repr(token)


def test_token_value_is_available_only_through_reveal(token):
    assert token.reveal() == SECRET
    assert token.authorization_header() == f"OAuth {SECRET}"


def test_token_cannot_be_pickled(token):
    """Пикл секрета — это запись секрета на диск."""
    with pytest.raises(TypeError):
        pickle.dumps(token)


def test_fingerprint_reveals_nothing(token):
    fingerprint = token.fingerprint()
    assert SECRET not in fingerprint
    assert len(fingerprint) == 16
    # Отпечаток обязан быть стабильным: иначе им нельзя заметить ротацию.
    assert fingerprint == creds.OAuthToken(SECRET, "x").fingerprint()
    assert fingerprint != creds.OAuthToken(SECRET + "z", "x").fingerprint()


# ---------------------------------------------------------------- редакция
def test_loading_registers_the_secret_for_redaction(token):
    leak = f"curl -H 'Authorization: OAuth {SECRET}' https://api-metrika.yandex.net"
    assert SECRET not in redact(leak)
    assert PLACEHOLDER in redact(leak)


def test_redaction_survives_json_serialisation(token):
    payload = {"headers": {"Authorization": f"OAuth {SECRET}"}, "note": f"токен {SECRET}"}
    text = json.dumps(redact_obj(payload), ensure_ascii=False)
    assert SECRET not in text


def test_yandex_token_shape_is_redacted_even_without_registration():
    """Незарегистрированный токен всё равно вырезается по форме значения."""
    forget_secrets()
    unseen = "y0_AgAAAAAneverRegisteredValue0987654321"
    assert unseen not in redact(f"Authorization: OAuth {unseen}")


# ------------------------------------------------------- сообщения об ошибках
def test_error_messages_never_carry_the_file_contents(tmp_path, monkeypatch):
    path = tmp_path / "yandex_oauth_token"
    path.write_text(SECRET, encoding="utf-8")
    path.chmod(0o644)  # намеренно слишком открытые права
    monkeypatch.setenv(creds.TOKEN_FILE_ENV, str(path))
    with pytest.raises(BlockedSecret) as excinfo:
        creds.load_token(path, require_root_owner=False)
    assert SECRET not in str(excinfo.value)
    assert SECRET not in excinfo.value.reason
    assert SECRET not in json.dumps(excinfo.value.as_blocker(), ensure_ascii=False)


def test_multiline_file_is_rejected_without_echoing_it(tmp_path, monkeypatch):
    path = tmp_path / "yandex_oauth_token"
    path.write_text(f"{SECRET}\nвторая строка\n", encoding="utf-8")
    path.chmod(0o600)
    monkeypatch.setenv(creds.TOKEN_FILE_ENV, str(path))
    with pytest.raises(BlockedSecret) as excinfo:
        creds.load_token(path, require_root_owner=False)
    assert SECRET not in str(excinfo.value)
    assert "вторая строка" not in str(excinfo.value)


# ----------------------------------------------------------- права файла
@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604, 0o666, 0o660])
def test_group_or_world_readable_secret_is_refused(tmp_path, monkeypatch, mode):
    path = tmp_path / "yandex_oauth_token"
    path.write_text(SECRET, encoding="utf-8")
    path.chmod(mode)
    monkeypatch.setenv(creds.TOKEN_FILE_ENV, str(path))
    with pytest.raises(BlockedSecret):
        creds.load_token(path, require_root_owner=False)
    assert not creds.inspect_token_file(path).ok


@pytest.mark.parametrize("mode", [0o600, 0o400])
def test_owner_only_modes_are_accepted(tmp_path, monkeypatch, mode):
    path = tmp_path / "yandex_oauth_token"
    path.write_text(SECRET, encoding="utf-8")
    path.chmod(mode)
    monkeypatch.setenv(creds.TOKEN_FILE_ENV, str(path))
    assert creds.load_token(path, require_root_owner=False).reveal() == SECRET
    forget_secrets()


def test_empty_secret_file_is_not_permission_to_run_without_a_token(tmp_path, monkeypatch):
    path = tmp_path / "yandex_oauth_token"
    path.write_text("   \n", encoding="utf-8")
    path.chmod(0o600)
    monkeypatch.setenv(creds.TOKEN_FILE_ENV, str(path))
    with pytest.raises(BlockedSecret, match="пуст"):
        creds.load_token(path, require_root_owner=False)


def test_secret_inside_the_repository_is_refused(monkeypatch, tmp_path):
    from factory.paths import PATHS

    path = PATHS.root / "var" / "fake-token"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SECRET, encoding="utf-8")
    path.chmod(0o600)
    try:
        monkeypatch.setenv(creds.TOKEN_FILE_ENV, str(path))
        with pytest.raises(BlockedSecret, match="внутрь репозитория"):
            creds.load_token(path, require_root_owner=False)
    finally:
        path.unlink(missing_ok=True)


# ------------------------------------------------- запрещённые переменные
@pytest.mark.parametrize("variable", creds.FORBIDDEN_VALUE_ENV)
def test_token_value_in_the_environment_is_refused(tmp_path, monkeypatch, variable):
    """Удобный обходной путь появляется ровно тогда, когда его не проверяют."""
    path = tmp_path / "yandex_oauth_token"
    path.write_text(SECRET, encoding="utf-8")
    path.chmod(0o600)
    monkeypatch.setenv(creds.TOKEN_FILE_ENV, str(path))
    monkeypatch.setenv(variable, SECRET)
    with pytest.raises(BlockedSecret, match="переменной окружения"):
        creds.load_token(path, require_root_owner=False)


def test_default_path_is_outside_the_repository():
    from factory.paths import PATHS

    assert not str(creds.DEFAULT_TOKEN_FILE).startswith(str(PATHS.root))
    assert creds.DEFAULT_TOKEN_FILE.startswith("/etc/")


def test_inaccessible_secret_directory_is_reported_honestly(tmp_path, monkeypatch):
    """Закрытый каталог — не «файла нет» и не авария, а неизмеренное состояние."""
    closed = tmp_path / "closed"
    closed.mkdir()
    target = closed / "yandex_oauth_token"
    target.write_text(SECRET, encoding="utf-8")
    target.chmod(0o600)
    closed.chmod(0o000)
    try:
        monkeypatch.setenv(creds.TOKEN_FILE_ENV, str(target))
        status = creds.inspect_token_file(target)
        assert status.mode is None, "состояние не измерено — режим не должен придумываться"
        assert not status.stored_correctly, "непроверенное не объявляется корректным"
        assert any("недоступен" in p for p in status.problems)
        with pytest.raises(BlockedSecret, match="не проверено"):
            creds.load_token(target)
    finally:
        closed.chmod(0o700)


# ---------------------------------------------- systemd credentials
def test_systemd_credential_is_accepted_without_root_ownership(tmp_path, monkeypatch):
    """LoadCredential кладёт файл в tmpfs от имени сервиса — это штатный путь."""
    cred_dir = tmp_path / "credentials"
    cred_dir.mkdir()
    path = cred_dir / "yandex_oauth"
    path.write_text(SECRET, encoding="utf-8")
    path.chmod(0o400)
    monkeypatch.setenv(creds.CREDENTIALS_DIR_ENV, str(cred_dir))
    monkeypatch.setenv(creds.TOKEN_FILE_ENV, str(path))
    for name in creds.FORBIDDEN_VALUE_ENV:
        monkeypatch.delenv(name, raising=False)

    assert creds.is_systemd_credential(path)
    status = creds.inspect_token_file(path)
    assert status.ok, status.problems
    assert creds.load_token(path).reveal() == SECRET
    forget_secrets()


def test_a_file_outside_the_credentials_directory_still_needs_root(tmp_path, monkeypatch):
    cred_dir = tmp_path / "credentials"
    cred_dir.mkdir()
    outside = tmp_path / "yandex_oauth_token"
    outside.write_text(SECRET, encoding="utf-8")
    outside.chmod(0o600)
    monkeypatch.setenv(creds.CREDENTIALS_DIR_ENV, str(cred_dir))
    monkeypatch.setenv(creds.TOKEN_FILE_ENV, str(outside))
    assert not creds.is_systemd_credential(outside)
    if os.geteuid() != 0:
        with pytest.raises(BlockedSecret, match="root"):
            creds.load_token(outside)
