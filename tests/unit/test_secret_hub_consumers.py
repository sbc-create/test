"""Применение к потребителям: атомарность, права, откат, отсутствие утечек.

Тесты работают на настоящих файлах во временных каталогах и на настоящих
объектах реестра. Подделывается ровно одно — `systemctl`: перезапускать чужие
unit'ы в тесте нельзя, но проверить, какие именно unit'ы были бы перезапущены,
можно и нужно.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from factory.errors import BlockedTarget
from factory.secret_hub import consumers as consumers_mod
from factory.secret_hub.crypto import Secret
from factory.secret_hub.registry import Consumer, Portfolio, Reload

TOKEN = "значение-токена-для-потребителя"
PUBLISHER = "publisher-777"


def values(token: str = TOKEN, publisher: str = PUBLISHER) -> dict:
    return {"api_token": Secret(token, "t"), "publisher_id": Secret(publisher, "p")}


def file_consumer(tmp_path: Path, consumer_id: str = "yami-staging-compose") -> Consumer:
    return Consumer(
        id=consumer_id, kind="file_mount", title="стенд",
        directory=tmp_path / "runtime" / "cdnvideohub",
        files={"api_token": "api-token", "publisher_id": "publisher-id"},
        owner="root", group="root", file_mode=0o400, directory_mode=0o755,
        reload=Reload("none"),
    )


def unit_consumer(tmp_path: Path, consumer_id: str = "lords-01") -> Consumer:
    return Consumer(
        id=consumer_id, kind="systemd_credential", title=f"{consumer_id}.service",
        directory=tmp_path / "secrets" / consumer_id,
        files={"api_token": "cdnvideohub-api-token",
               "publisher_id": "cdnvideohub-publisher-id"},
        owner="root", group="root", file_mode=0o400, directory_mode=0o700,
        reload=Reload("systemd"), unit=f"{consumer_id}.service",
        dropin=tmp_path / "systemd" / f"{consumer_id}.service.d" / "10-cred.conf",
        credential_names={"api_token": "cdnvideohub_api_token",
                          "publisher_id": "cdnvideohub_publisher_id"},
    )


@pytest.fixture
def fake_systemd(monkeypatch):
    """`systemctl` не запускается: записывается, что было бы запущено."""
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = "unit-file loaded\n"

    def fake_run(command, **kwargs):
        calls.append(list(command))
        return Result()

    monkeypatch.setattr(consumers_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(consumers_mod, "_unit_exists", lambda unit: True)
    return calls


class TestFileMount:
    def test_values_are_written_with_closed_permissions(self, tmp_path):
        consumer = file_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        result = consumers_mod.apply_consumer(consumer, values(),
                                              backup_root=tmp_path / "backups")
        assert result.status == "applied", result.detail
        for name in ("api_token", "publisher_id"):
            path = consumer.path_for(name)
            assert path.read_text(encoding="utf-8") == values()[name].reveal()
            assert stat.S_IMODE(path.stat().st_mode) == 0o400

    def test_no_trailing_newline_is_added(self, tmp_path):
        """Лишний перевод строки стал бы частью значения для systemd."""
        consumer = file_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        consumers_mod.apply_consumer(consumer, values(), backup_root=tmp_path / "backups")
        assert consumer.path_for("api_token").read_bytes() == TOKEN.encode("utf-8")

    def test_file_mount_consumer_is_not_restarted(self, tmp_path, fake_systemd):
        """Работающий стенд не перезапускается ради записи файла."""
        consumer = file_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        result = consumers_mod.apply_consumer(consumer, values(),
                                              backup_root=tmp_path / "backups")
        assert result.restarted == ()
        assert fake_systemd == []

    def test_temp_file_is_not_left_behind(self, tmp_path):
        consumer = file_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        consumers_mod.apply_consumer(consumer, values(), backup_root=tmp_path / "backups")
        assert not list(consumer.directory.glob(".*tmp"))

    def test_missing_mount_in_compose_is_blocked(self, tmp_path):
        """Файл, который никуда не примонтирован, писать бессмысленно."""
        compose = tmp_path / "compose.yaml"
        compose.write_text("services:\n  web:\n    image: x\n", encoding="utf-8")
        consumer = file_consumer(tmp_path)
        consumer = Consumer(**{**consumer.__dict__, "compose_file": compose,
                               "expect_mount_target": "/run/cdnvideohub"})
        consumer.directory.parent.mkdir(parents=True)
        result = consumers_mod.apply_consumer(consumer, values(),
                                              backup_root=tmp_path / "backups")
        assert result.status == "blocked"
        assert "нет монтирования" in result.detail
        assert not consumer.path_for("api_token").exists(), "заблокированная цель не пишется"


class TestSystemdCredential:
    def test_dropin_contains_paths_not_values(self, tmp_path, fake_systemd):
        consumer = unit_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        result = consumers_mod.apply_consumer(consumer, values(),
                                              backup_root=tmp_path / "backups")
        assert result.status == "applied", result.detail
        text = consumer.dropin.read_text(encoding="utf-8")
        assert TOKEN not in text, "значение попало в drop-in"
        assert PUBLISHER not in text
        assert "LoadCredential=cdnvideohub_api_token:" in text
        assert str(consumer.path_for("api_token")) in text

    def test_dropin_does_not_use_the_percent_d_specifier(self, tmp_path, fake_systemd):
        """`%d` появился в systemd 250, а Ubuntu 22.04 везёт 249.

        Там строка не разворачивается и остаётся literal-ом «%d/...», после чего
        потребитель падает на «файл не найден» — молча, потому что для systemd
        запись синтаксически корректна. Эти же грабли уже наступили в слое
        аналитики; повторять их здесь незачем.
        """
        consumer = unit_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        consumers_mod.apply_consumer(consumer, values(), backup_root=tmp_path / "backups")
        text = consumer.dropin.read_text(encoding="utf-8")
        directives = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        assert not any("%d" in line for line in directives), \
            "drop-in использует %d: на systemd 249 путь не развернётся"
        assert "CDNVIDEOHUB_API_TOKEN_CREDENTIAL=cdnvideohub_api_token" in text

    def test_only_own_unit_is_restarted(self, tmp_path, fake_systemd):
        consumer = unit_consumer(tmp_path, "lords-01")
        consumer.directory.parent.mkdir(parents=True)
        result = consumers_mod.apply_consumer(consumer, values(),
                                              backup_root=tmp_path / "backups")
        assert result.restarted == ("lords-01.service",)
        restarts = [c for c in fake_systemd if "restart" in c]
        assert restarts == [["systemctl", "restart", "lords-01.service"]]

    def test_restart_can_be_suppressed(self, tmp_path, fake_systemd):
        consumer = unit_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        result = consumers_mod.apply_consumer(consumer, values(),
                                              backup_root=tmp_path / "backups", restart=False)
        assert result.status == "applied"
        assert result.restarted == ()
        assert [c for c in fake_systemd if "restart" in c] == []

    def test_missing_unit_blocks_before_writing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(consumers_mod, "_unit_exists", lambda unit: False)
        consumer = unit_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        result = consumers_mod.apply_consumer(consumer, values(),
                                              backup_root=tmp_path / "backups")
        assert result.status == "blocked"
        assert "не найден в systemd" in result.detail
        assert not consumer.directory.exists() or not consumer.path_for("api_token").exists()


class TestRollback:
    def test_previous_values_return_after_a_failure(self, tmp_path, fake_systemd, monkeypatch):
        consumer = unit_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        consumers_mod.apply_consumer(consumer, values("старое-значение"),
                                     backup_root=tmp_path / "backups")
        assert consumer.path_for("api_token").read_text() == "старое-значение"

        def fail_after_write(*args, **kwargs):
            raise RuntimeError("сбой перезапуска")

        monkeypatch.setattr(consumers_mod, "_reload_unit", fail_after_write)
        result = consumers_mod.apply_consumer(consumer, values("новое-значение"),
                                              backup_root=tmp_path / "backups")

        assert result.status == "failed"
        assert consumer.path_for("api_token").read_text() == "старое-значение", \
            "откат обязан вернуть прежнее значение"

    def test_rollback_removes_files_that_did_not_exist_before(self, tmp_path, monkeypatch):
        """Первая в жизни установка при откате не должна оставлять новых файлов."""
        consumer = file_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)

        original = consumers_mod.verify_written
        monkeypatch.setattr(consumers_mod, "verify_written",
                            lambda c: ["искусственная проблема"])
        result = consumers_mod.apply_consumer(consumer, values(),
                                              backup_root=tmp_path / "backups")
        monkeypatch.setattr(consumers_mod, "verify_written", original)

        assert result.status == "failed"
        assert not consumer.path_for("api_token").exists()
        assert not consumer.path_for("publisher_id").exists()

    def test_portfolio_rollback_restores_earlier_consumers(self, tmp_path, fake_systemd,
                                                           monkeypatch):
        """Отказ на втором потребителе возвращает и первого.

        Половина сайтов на новом токене и половина на старом — состояние,
        которое никак не называется; направление возвращается целиком.
        """
        first = unit_consumer(tmp_path, "lords-01")
        second = unit_consumer(tmp_path, "lords-02")
        for consumer in (first, second):
            consumer.directory.parent.mkdir(parents=True, exist_ok=True)
        portfolio = Portfolio("lords", "Lords", True, (first, second))

        consumers_mod.apply_portfolio(portfolio, values("исходное"), version=1,
                                      backup_root=tmp_path / "backups")
        assert first.path_for("api_token").read_text() == "исходное"

        real_apply = consumers_mod._apply_consumer

        def fail_on_second(consumer, vals, **kwargs):
            if consumer.id == "lords-02":
                from factory.secret_hub.consumers import ConsumerResult, Rollback

                return ConsumerResult(consumer.id, "failed", "искусственный отказ"), \
                    Rollback(tmp_path / "unused")
            return real_apply(consumer, vals, **kwargs)

        monkeypatch.setattr(consumers_mod, "_apply_consumer", fail_on_second)
        report = consumers_mod.apply_portfolio(portfolio, values("новое"), version=2,
                                               backup_root=tmp_path / "backups")

        assert report.ok is False
        assert report.rolled_back is True
        assert first.path_for("api_token").read_text() == "исходное", \
            "первый потребитель обязан вернуться к прежнему значению"


class TestIsolation:
    def test_applying_yami_does_not_touch_lords_files(self, tmp_path, fake_systemd):
        yami = file_consumer(tmp_path / "yami")
        lords = unit_consumer(tmp_path / "lords")
        for consumer in (yami, lords):
            consumer.directory.parent.mkdir(parents=True, exist_ok=True)

        consumers_mod.apply_consumer(lords, values("токен-lords"),
                                     backup_root=tmp_path / "backups")
        lords_before = lords.path_for("api_token").read_bytes()

        consumers_mod.apply_consumer(yami, values("токен-yami"),
                                     backup_root=tmp_path / "backups")

        assert lords.path_for("api_token").read_bytes() == lords_before
        assert yami.path_for("api_token").read_text() == "токен-yami"

    def test_applying_lords_does_not_restart_yami(self, tmp_path, fake_systemd):
        lords = unit_consumer(tmp_path / "lords", "lords-01")
        lords.directory.parent.mkdir(parents=True)
        consumers_mod.apply_consumer(lords, values(), backup_root=tmp_path / "backups")
        restarted = [c[2] for c in fake_systemd if len(c) > 2 and c[1] == "restart"]
        assert restarted == ["lords-01.service"]
        assert not any("yummyani" in unit or "yami" in unit for unit in restarted)


class TestBlockedPortfolio:
    def test_blocked_target_portfolio_is_refused(self, tmp_path):
        from factory.secret_hub.registry import BlockedTarget as BlockedTargetRecord

        portfolio = Portfolio("amedia", "Amedia", True, (),
                              BlockedTargetRecord("BLOCKED_TARGET", "инфраструктура не передана",
                                                  "каталог развёртывания"))
        with pytest.raises(BlockedTarget):
            consumers_mod.apply_portfolio(portfolio, values(), version=1,
                                          backup_root=tmp_path / "backups")

    def test_portfolio_without_consumers_is_refused(self, tmp_path):
        portfolio = Portfolio("новое", "Новое", True, ())
        with pytest.raises(BlockedTarget) as excinfo:
            consumers_mod.apply_portfolio(portfolio, values(), version=1,
                                          backup_root=tmp_path / "backups")
        assert "применять некуда" in excinfo.value.reason


class TestNoLeaks:
    def test_result_never_contains_values(self, tmp_path, fake_systemd):
        consumer = unit_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        result = consumers_mod.apply_consumer(consumer, values(),
                                              backup_root=tmp_path / "backups")
        serialized = str(result.as_dict())
        assert TOKEN not in serialized
        assert PUBLISHER not in serialized

    def test_describe_never_contains_values(self, tmp_path, fake_systemd):
        consumer = unit_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        consumers_mod.apply_consumer(consumer, values(), backup_root=tmp_path / "backups")
        portfolio = Portfolio("lords", "Lords", True, (consumer,))
        serialized = str(consumers_mod.describe(portfolio))
        assert TOKEN not in serialized
        assert PUBLISHER not in serialized

    def test_failure_detail_never_contains_values(self, tmp_path, monkeypatch):
        consumer = file_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)

        def explode(path, value, mode):
            raise RuntimeError(f"не записал {path}")

        monkeypatch.setattr(consumers_mod, "_write_atomically", explode)
        result = consumers_mod.apply_consumer(consumer, values(),
                                              backup_root=tmp_path / "backups")
        assert result.status == "failed"
        assert TOKEN not in result.detail

    def test_backup_copies_are_closed(self, tmp_path, fake_systemd):
        consumer = unit_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        consumers_mod.apply_consumer(consumer, values("первое"),
                                     backup_root=tmp_path / "backups")
        consumers_mod.apply_consumer(consumer, values("второе"),
                                     backup_root=tmp_path / "backups")
        copies = list((tmp_path / "backups").rglob("cdnvideohub-api-token"))
        assert copies, "снимок прежнего файла не сделан"
        for copy in copies:
            assert stat.S_IMODE(copy.stat().st_mode) == 0o600
            assert stat.S_IMODE(copy.parent.stat().st_mode) == 0o700


class TestUnmeasuredPaths:
    def test_closed_directory_does_not_crash_describe(self, tmp_path):
        """Закрытый каталог — работающая защита, а не авария status."""
        consumer = unit_consumer(tmp_path)
        consumer.directory.parent.mkdir(parents=True)
        consumer.directory.mkdir()
        (consumer.directory / "cdnvideohub-api-token").write_text("x", encoding="utf-8")
        os.chmod(consumer.directory, 0o000)
        try:
            portfolio = Portfolio("lords", "Lords", True, (consumer,))
            rows = consumers_mod.describe(portfolio)
            entry = rows[0]["files"][0]
            assert entry["present"] is None
            assert entry["measured"] is False
        finally:
            os.chmod(consumer.directory, 0o700)
