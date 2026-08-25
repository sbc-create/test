"""Хранилище Secret Hub: версии, права, атомарность, откат, изоляция направлений."""
from __future__ import annotations

import os
import sqlite3
import stat

import pytest

from factory.errors import BlockedInput, BlockedSecret
from factory.secret_hub import SECRET_FIELDS, crypto
from factory.secret_hub.store import STATUS_ACTIVE, STATUS_REVOKED, STATUS_SUPERSEDED, Store


@pytest.fixture
def master(tmp_path) -> crypto.MasterKey:
    path = tmp_path / "master.key"
    path.write_text(crypto.generate_master_key(), encoding="utf-8")
    os.chmod(path, 0o600)
    return crypto.load_master_key(path, require_root_owner=False)


@pytest.fixture
def store(tmp_path, master) -> Store:
    with Store(tmp_path / "hub" / "store.sqlite3", master) as opened:
        yield opened


def values(token: str = "токен-значение-01", publisher: str = "pub-01") -> dict:
    return {
        "api_token": crypto.Secret(token, "t"),
        "publisher_id": crypto.Secret(publisher, "p"),
    }


class TestPermissions:
    def test_directory_is_0700_and_file_is_0600(self, store):
        directory_mode = stat.S_IMODE(store.db_path.parent.stat().st_mode)
        file_mode = stat.S_IMODE(store.db_path.stat().st_mode)
        assert directory_mode == 0o700, f"каталог {directory_mode:04o}, ожидается 0700"
        assert file_mode == 0o600, f"файл {file_mode:04o}, ожидается 0600"

    def test_check_permissions_is_clean_on_fresh_store(self, store):
        store.put("yami", values(), provider="cdnvideohub", verified_at=None)
        assert store.check_permissions() == []

    def test_loosened_permissions_are_reported(self, store):
        os.chmod(store.db_path, 0o644)
        problems = store.check_permissions()
        assert any("доступен группе или миру" in p for p in problems)
        os.chmod(store.db_path, 0o600)

    def test_wal_and_shm_are_also_closed(self, store):
        """WAL содержит те же байты, что и база. Открытый WAL — открытая база."""
        store.put("yami", values(), provider="cdnvideohub", verified_at=None)
        for suffix in ("-wal", "-shm"):
            path = store.db_path.with_name(store.db_path.name + suffix)
            if path.exists():
                assert stat.S_IMODE(path.stat().st_mode) == 0o600, f"{path} открыт"


class TestCiphertextOnDisk:
    def test_plaintext_never_appears_in_database_file(self, store):
        """Главное свойство: в файле базы нет открытых значений."""
        store.put("yami", values("МАРКЕР-ТОКЕНА-XYZ", "МАРКЕР-ПАБЛИШЕРА"),
                  provider="cdnvideohub", verified_at=None)
        blob = store.db_path.read_bytes()
        for suffix in ("-wal", "-shm"):
            path = store.db_path.with_name(store.db_path.name + suffix)
            if path.exists():
                blob += path.read_bytes()
        assert "МАРКЕР-ТОКЕНА-XYZ".encode() not in blob
        assert "МАРКЕР-ПАБЛИШЕРА".encode() not in blob

    def test_master_key_is_not_stored_in_database(self, store, master):
        store.put("yami", values(), provider="cdnvideohub", verified_at=None)
        connection = sqlite3.connect(str(store.db_path))
        try:
            dump = "\n".join(connection.iterdump())
        finally:
            connection.close()
        assert master.key_id() not in dump or "key_id" in dump
        # key_id — публичный идентификатор, а не ключ; самого ключа быть не должно
        assert "master" not in dump.lower().replace("master_key_id", "")


class TestVersions:
    def test_put_creates_version_one(self, store):
        assert store.put("yami", values(), provider="cdnvideohub", verified_at=None) == 1

    def test_second_put_supersedes_first_without_deleting_it(self, store):
        store.put("yami", values("первый-токен"), provider="cdnvideohub", verified_at=None)
        second = store.put("yami", values("второй-токен"), provider="cdnvideohub",
                           verified_at=None)
        state = store.state("yami")
        assert second == 2
        assert state.active_version == 2
        statuses = {v.version: v.status for v in state.versions}
        assert statuses == {1: STATUS_SUPERSEDED, 2: STATUS_ACTIVE}, \
            "предыдущая версия обязана остаться в базе"

    def test_fingerprint_changes_when_value_changes(self, store):
        store.put("yami", values("токен-A"), provider="cdnvideohub", verified_at=None)
        first = store.state("yami").fingerprint
        store.put("yami", values("токен-B"), provider="cdnvideohub", verified_at=None)
        assert store.state("yami").fingerprint != first

    def test_fingerprint_is_stable_for_same_value(self, store):
        store.put("yami", values("токен-A"), provider="cdnvideohub", verified_at=None)
        first = store.state("yami").fingerprint
        store.put("yami", values("токен-A"), provider="cdnvideohub", verified_at=None)
        assert store.state("yami").fingerprint == first

    def test_empty_field_is_refused(self, store):
        with pytest.raises(BlockedInput) as excinfo:
            store.put("yami", values("", "pub"), provider="cdnvideohub", verified_at=None)
        assert "Пустое поле" in excinfo.value.reason

    def test_missing_field_is_refused(self, store):
        with pytest.raises(BlockedInput):
            store.put("yami", {"api_token": crypto.Secret("t", "t")},
                      provider="cdnvideohub", verified_at=None)


class TestState:
    def test_unknown_portfolio_is_not_configured(self, store):
        state = store.state("amedia")
        assert state.configured is False
        assert state.status == "not_configured"
        assert state.fingerprint is None

    def test_state_contains_no_secret_values(self, store):
        store.put("yami", values("СЕКРЕТНЫЙ-ТОКЕН-1", "СЕКРЕТНЫЙ-ПАБ"),
                  provider="cdnvideohub", verified_at=None)
        serialized = str(store.state("yami").as_dict())
        assert "СЕКРЕТНЫЙ-ТОКЕН-1" not in serialized
        assert "СЕКРЕТНЫЙ-ПАБ" not in serialized

    def test_verified_at_is_none_until_marked(self, store):
        store.put("yami", values(), provider="cdnvideohub", verified_at=None)
        assert store.state("yami").verified is False
        store.mark_verified("yami", 1)
        assert store.state("yami").verified is True


class TestRevokeAndRollback:
    def test_revoke_keeps_the_value(self, store):
        store.put("yami", values(), provider="cdnvideohub", verified_at="2026-08-25T00:00:00Z")
        store.revoke("yami")
        state = store.state("yami")
        assert state.configured is False
        assert state.status == STATUS_REVOKED
        assert [v.status for v in state.versions] == [STATUS_REVOKED], \
            "отозванная версия обязана остаться: иначе откат невозможен"

    def test_revoke_without_configuration_is_refused(self, store):
        with pytest.raises(BlockedInput):
            store.revoke("lords")

    def test_rollback_restores_previous_version(self, store):
        store.put("yami", values("старый-токен"), provider="cdnvideohub", verified_at=None)
        first_fingerprint = store.state("yami").fingerprint
        store.put("yami", values("новый-токен"), provider="cdnvideohub", verified_at=None)
        assert store.state("yami").fingerprint != first_fingerprint

        restored = store.rollback("yami")
        assert restored == 1
        assert store.state("yami").active_version == 1
        assert store.state("yami").fingerprint == first_fingerprint
        assert store.reveal_for_apply("yami")["api_token"].reveal() == "старый-токен"

    def test_rollback_without_previous_version_is_refused(self, store):
        store.put("yami", values(), provider="cdnvideohub", verified_at=None)
        with pytest.raises(BlockedInput) as excinfo:
            store.rollback("yami")
        assert "нет предыдущей версии" in excinfo.value.reason

    def test_rollback_skips_revoked_versions(self, store):
        """Откат не должен возвращать отозванное значение.

        Иначе `revoke` был бы обратим случайным `rollback`, и отозванный токен
        тихо вернулся бы на сайты.
        """
        store.put("yami", values("v1"), provider="cdnvideohub", verified_at=None)
        store.revoke("yami")
        store.put("yami", values("v2"), provider="cdnvideohub", verified_at=None)
        store.put("yami", values("v3"), provider="cdnvideohub", verified_at=None)
        assert store.rollback("yami") == 2


class TestPortfolioIsolation:
    def test_portfolios_do_not_see_each_others_values(self, store):
        store.put("yami", values("токен-yami", "pub-yami"), provider="cdnvideohub",
                  verified_at=None)
        store.put("lords", values("токен-lords", "pub-lords"), provider="cdnvideohub",
                  verified_at=None)
        assert store.reveal_for_apply("yami")["api_token"].reveal() == "токен-yami"
        assert store.reveal_for_apply("lords")["api_token"].reveal() == "токен-lords"

    def test_rollback_of_one_portfolio_does_not_touch_the_other(self, store):
        store.put("yami", values("yami-v1"), provider="cdnvideohub", verified_at=None)
        store.put("yami", values("yami-v2"), provider="cdnvideohub", verified_at=None)
        store.put("lords", values("lords-v1"), provider="cdnvideohub", verified_at=None)
        lords_before = store.state("lords").as_dict()

        store.rollback("yami")

        assert store.state("lords").as_dict() == lords_before
        assert store.reveal_for_apply("lords")["api_token"].reveal() == "lords-v1"

    def test_revoke_of_one_portfolio_does_not_touch_the_other(self, store):
        store.put("yami", values(), provider="cdnvideohub", verified_at=None)
        store.put("lords", values(), provider="cdnvideohub", verified_at=None)
        store.revoke("yami")
        assert store.state("lords").configured is True
        assert store.state("lords").status == STATUS_ACTIVE

    def test_ciphertext_swapped_between_portfolios_does_not_decrypt(self, store, master):
        """Подмена шифртекста прямо в SQLite обязана быть замечена."""
        store.put("yami", values("токен-yami"), provider="cdnvideohub", verified_at=None)
        store.put("lords", values("токен-lords"), provider="cdnvideohub", verified_at=None)

        connection = sqlite3.connect(str(store.db_path))
        try:
            row = connection.execute(
                "SELECT salt, nonce, ciphertext FROM secret_value"
                " WHERE portfolio='lords' AND field='api_token'").fetchone()
            connection.execute(
                "UPDATE secret_value SET salt=?, nonce=?, ciphertext=?"
                " WHERE portfolio='yami' AND field='api_token'", row)
            connection.commit()
        finally:
            connection.close()

        with pytest.raises(BlockedSecret):
            store.reveal_for_apply("yami")


class TestBackupAndRestore:
    def test_backup_is_created_with_closed_permissions(self, store, tmp_path):
        store.put("yami", values(), provider="cdnvideohub", verified_at=None)
        backup = store.backup(tmp_path / "backups", tag="test")
        assert backup.exists()
        assert stat.S_IMODE(backup.stat().st_mode) == 0o600
        assert stat.S_IMODE(backup.parent.stat().st_mode) == 0o700

    def test_backup_captures_committed_state(self, store, tmp_path, master):
        """Бэкап обязан содержать последние транзакции, а не старый файл.

        В режиме WAL свежие записи какое-то время живут в отдельном файле, и
        простое копирование `store.sqlite3` дало бы бэкап без них.
        """
        store.put("yami", values("токен-в-бэкапе"), provider="cdnvideohub", verified_at=None)
        backup = store.backup(tmp_path / "backups", tag="wal")

        with Store(backup, master, enforce_permissions=False) as copy:
            assert copy.reveal_for_apply("yami")["api_token"].reveal() == "токен-в-бэкапе"

    def test_restore_returns_previous_state(self, store, tmp_path):
        store.put("yami", values("до-бэкапа"), provider="cdnvideohub", verified_at=None)
        backup = store.backup(tmp_path / "backups", tag="before")
        store.put("yami", values("после-бэкапа"), provider="cdnvideohub", verified_at=None)
        assert store.state("yami").active_version == 2

        store.restore(backup)

        assert store.state("yami").active_version == 1
        assert store.reveal_for_apply("yami")["api_token"].reveal() == "до-бэкапа"

    def test_restore_of_missing_backup_is_refused(self, store, tmp_path):
        with pytest.raises(BlockedInput):
            store.restore(tmp_path / "нет-такого.sqlite3")


class TestAtomicity:
    def test_failed_put_leaves_previous_version_intact(self, store, monkeypatch):
        """Прерванная запись не должна оставлять половину новой версии."""
        store.put("yami", values("рабочий-токен"), provider="cdnvideohub", verified_at=None)
        before = store.state("yami").as_dict()

        from factory.secret_hub import store as store_mod

        def explode(*args, **kwargs):
            raise RuntimeError("сбой посреди записи")

        monkeypatch.setattr(store_mod, "encrypt", explode)
        with pytest.raises(RuntimeError):
            store.put("yami", values("новый-токен"), provider="cdnvideohub", verified_at=None)

        assert store.state("yami").as_dict() == before
        assert store.reveal_for_apply("yami")["api_token"].reveal() == "рабочий-токен"

    def test_backup_temp_file_is_not_left_behind(self, store, tmp_path):
        store.put("yami", values(), provider="cdnvideohub", verified_at=None)
        directory = tmp_path / "backups"
        store.backup(directory, tag="one")
        assert not list(directory.glob(".*tmp")), "временный файл бэкапа остался на диске"


class TestRevealIsNotPartOfTheApi:
    def test_reveal_requires_configured_portfolio(self, store):
        with pytest.raises(BlockedSecret):
            store.reveal_for_apply("amedia")

    def test_reveal_returns_all_fields(self, store):
        store.put("yami", values(), provider="cdnvideohub", verified_at=None)
        assert set(store.reveal_for_apply("yami")) == set(SECRET_FIELDS)
