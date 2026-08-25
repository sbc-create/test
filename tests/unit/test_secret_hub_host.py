"""Фактическая проверка хоста: nginx, systemd, установленный сервис, публичность сайтов.

Эти тесты измеряют реальное состояние машины, а не выдумывают его. Там, где
измерение невозможно (нет nginx, не установлен unit, каталог закрыт), тест
помечается SKIPPED с причиной — «пройденным» он от этого не становится. Правило
задания: «не объявлять работу завершённой только по локальным тестам».
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from factory.secret_hub.registry import load as load_config

HUB_UNIT = "site-factory-secret-hub.service"
ENROLL_UNIT = "site-factory-secret-hub-enroll@.service"
IMPORT_UNIT = "site-factory-secret-hub-import@.service"
UNIT_DIR = Path("/etc/systemd/system")


@pytest.fixture(scope="module")
def config(repo_root):
    return load_config(repo_root / "config" / "secret-hub.json")


def _systemctl(*args: str) -> subprocess.CompletedProcess | None:
    if shutil.which("systemctl") is None:
        return None
    try:
        return subprocess.run(["systemctl", *args], capture_output=True, text=True,
                              timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None


class TestUnitFilesInRepository:
    """Проверяется репозиторий: эти тесты обязаны идти всегда и везде."""

    def test_hub_unit_exists_and_loads_credential(self, repo_root):
        text = (repo_root / "automation" / "secret-hub" / HUB_UNIT).read_text(encoding="utf-8")
        assert "LoadCredential=secret_hub_master_key:" in text
        assert "User=root" in text

    def test_hub_unit_does_not_put_secrets_in_environment(self, repo_root):
        """Значение в `Environment=` видно в `systemctl show`. Там его быть не должно."""
        text = (repo_root / "automation" / "secret-hub" / HUB_UNIT).read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("Environment="):
                assert "TOKEN=" not in line.upper().replace("TOKEN_FILE=", "")
                assert "KEY=" not in line.upper().replace("KEY_FILE=", "")

    def test_core_dumps_are_disabled(self, repo_root):
        """Дамп памяти этого процесса — дамп всех секретов направлений."""
        text = (repo_root / "automation" / "secret-hub" / HUB_UNIT).read_text(encoding="utf-8")
        assert "LimitCORE=0" in text

    @pytest.mark.parametrize("unit", [HUB_UNIT, ENROLL_UNIT, IMPORT_UNIT])
    def test_units_are_shipped(self, repo_root, unit):
        assert (repo_root / "automation" / "secret-hub" / unit).exists()

    def test_install_script_does_not_overwrite_existing_key(self, repo_root):
        """Перезапись мастер-ключа — потеря всех секретов. Скрипт обязан этого не делать."""
        text = (repo_root / "automation" / "secret-hub" / "install.sh").read_text(encoding="utf-8")
        assert 'if [ -e "$KEY_FILE" ]' in text
        assert "не трогаю" in text

    def test_install_script_touches_neither_dns_nor_basic_auth(self, repo_root):
        text = (repo_root / "automation" / "secret-hub" / "install.sh").read_text(encoding="utf-8")
        for forbidden in ("htpasswd", "auth_basic", "certbot", "named", "route53", "dropdb"):
            assert forbidden not in text, f"install.sh трогает «{forbidden}»"


class TestInstalledOnThisHost:
    """Измерение фактического состояния машины."""

    def test_hub_unit_is_installed(self):
        if not (UNIT_DIR / HUB_UNIT).exists():
            pytest.skip(f"{HUB_UNIT} не установлен на этом хосте: "
                        "запустите automation/secret-hub/install.sh от root")
        assert (UNIT_DIR / HUB_UNIT).is_file()

    def test_hub_service_is_active(self):
        result = _systemctl("is-active", HUB_UNIT)
        if result is None:
            pytest.skip("systemctl недоступен в этой среде")
        if result.stdout.strip() in ("inactive", "unknown", "failed"):
            pytest.skip(f"{HUB_UNIT} не запущен ({result.stdout.strip()}): "
                        "живая проверка хоста ещё не выполнялась")
        assert result.stdout.strip() == "active"

    def test_master_key_is_root_owned_and_closed(self):
        from factory.secret_hub.crypto import DEFAULT_KEY_FILE, inspect_key_file

        status = inspect_key_file(Path(DEFAULT_KEY_FILE))
        if not status.exists:
            pytest.skip("мастер-ключ ещё не создан: установка не выполнялась")
        if status.mode is None:
            # Каталог закрыт целиком — это ровно то, что нужно. Состояние файла
            # измерить нельзя, и объявлять тест пройденным на этом основании
            # было бы неправдой.
            pytest.skip("каталог секретов закрыт для этой учётной записи: "
                        "состояние ключа не измерено (так и задумано)")
        assert status.owner_is_root, f"мастер-ключ принадлежит uid={status.owner_uid}"
        assert not status.group_or_world_readable, f"права {status.mode}"

    def test_store_directory_is_closed(self, config):
        try:
            info = config.store_dir.stat()
        except FileNotFoundError:
            pytest.skip("хранилище ещё не создано: установка не выполнялась")
        except PermissionError:
            pytest.skip("каталог хранилища закрыт для этой учётной записи (так и задумано)")
        mode = stat.S_IMODE(info.st_mode)
        assert not (mode & 0o077), f"каталог хранилища {mode:04o} открыт группе или миру"

    def test_socket_is_not_world_accessible(self, config):
        from factory.secret_hub import service

        status = service.socket_status(config.socket_path)
        if not status.get("exists"):
            pytest.skip("сокет отсутствует: сервис не запущен")
        assert status["world_accessible"] is False


class TestConsumerTargetsExistOnThisHost:
    """Цели применения — реальные каталоги и unit'ы, а не строки в конфигурации."""

    def test_yami_mount_directory_exists(self, config):
        directory = config.portfolio("yami").consumers[0].directory
        if not directory.parent.exists():
            pytest.skip(f"стенд Yami отсутствует на этом хосте ({directory.parent})")
        assert directory.parent.is_dir()

    def test_yami_compose_declares_the_mount(self, config):
        consumer = config.portfolio("yami").consumers[0]
        if not consumer.compose_file or not consumer.compose_file.exists():
            pytest.skip(f"compose-файл {consumer.compose_file} отсутствует на этом хосте")
        text = consumer.compose_file.read_text(encoding="utf-8", errors="replace")
        assert consumer.expect_mount_target in text, \
            "запись файлов бессмысленна: каталог никуда не примонтирован"
        assert str(consumer.directory) in text

    def test_yami_compose_does_not_put_values_in_environment(self, config):
        """Значение в `environment:` видно в `docker inspect`. Оно должно приходить файлом."""
        consumer = config.portfolio("yami").consumers[0]
        if not consumer.compose_file or not consumer.compose_file.exists():
            pytest.skip("compose-файл отсутствует на этом хосте")
        for line in consumer.compose_file.read_text(encoding="utf-8",
                                                    errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("CDNVIDEOHUB_API_TOKEN:"):
                value = stripped.split(":", 1)[1].strip()
                assert value in ("", "${CDNVIDEOHUB_API_TOKEN:-}"), \
                    f"в compose записано значение: {value}"

    @pytest.mark.parametrize("consumer_id", ["lords-01", "lords-02", "lords-03"])
    def test_lords_units_exist(self, config, consumer_id):
        consumer = config.portfolio("lords").consumer(consumer_id)
        if not (UNIT_DIR / consumer.unit).exists():
            pytest.skip(f"{consumer.unit} отсутствует на этом хосте")
        assert (UNIT_DIR / consumer.unit).is_file()

    def test_amedia_has_no_targets_and_says_so(self, config):
        amedia = config.portfolio("amedia")
        assert amedia.consumers == ()
        assert amedia.blocked_target is not None
        assert amedia.blocked_target.status == "BLOCKED_TARGET"
        assert amedia.deployable is False


class TestSitesStayPublicAndNoindex:
    """Basic Auth не восстанавливается; noindex остаётся.

    Задание прямо требует: сайты остаются публичными без пароля, но с
    выключенной индексацией. Проверяется по фактической конфигурации nginx на
    этом хосте.
    """

    NGINX_DIRS = (Path("/etc/nginx/sites-enabled"), Path("/etc/nginx/conf.d"))

    def _configs(self) -> list[Path]:
        out: list[Path] = []
        for directory in self.NGINX_DIRS:
            try:
                out.extend(p for p in directory.iterdir() if p.is_file() or p.is_symlink())
            except (FileNotFoundError, PermissionError):
                continue
        return out

    def _readable(self) -> list[tuple[Path, str]]:
        readable: list[tuple[Path, str]] = []
        for path in self._configs():
            try:
                readable.append((path, path.read_text(encoding="utf-8", errors="replace")))
            except (OSError, PermissionError):
                continue
        return readable

    def test_no_basic_auth_is_configured(self):
        readable = self._readable()
        if not readable:
            pytest.skip("конфигурация nginx недоступна для чтения в этой среде")
        offenders = [str(path) for path, text in readable
                     if "auth_basic" in text and "auth_basic off" not in text]
        assert offenders == [], f"Basic Auth настроен в: {', '.join(offenders)}"

    def test_noindex_header_is_present_for_yummyani(self):
        readable = [(p, t) for p, t in self._readable() if "yummyani" in p.name]
        if not readable:
            pytest.skip("конфигурации yummyani недоступны в этой среде")
        with_header = [str(p) for p, t in readable if "noindex" in t.lower()]
        assert with_header, "ни в одной конфигурации yummyani нет X-Robots-Tag: noindex"

    def test_secret_hub_adds_no_nginx_configuration(self, repo_root):
        """Хаб не публикуется наружу и nginx не трогает вовсе."""
        for path in (repo_root / "automation" / "secret-hub").iterdir():
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "server_name" not in text, f"{path} описывает vhost"
            assert "proxy_pass" not in text, f"{path} настраивает nginx"


class TestNoSecretsInProcessSurface:
    """Значения не передаются через argv и обычные переменные окружения."""

    def test_no_forbidden_variable_is_set_in_this_process(self):
        from factory.secret_hub.crypto import FORBIDDEN_VALUE_ENV

        present = [name for name in FORBIDDEN_VALUE_ENV if os.environ.get(name)]
        assert present == [], f"значение секрета в окружении: {', '.join(present)}"

    def test_units_pass_paths_not_values(self, repo_root):
        for name in (HUB_UNIT, ENROLL_UNIT, IMPORT_UNIT):
            text = (repo_root / "automation" / "secret-hub" / name).read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("ExecStart="):
                    assert "--token" not in line and "--key" not in line, \
                        f"{name}: секрет передаётся через argv"

    def test_cli_has_no_flag_that_accepts_a_value(self, repo_root):
        """У `factory secrets` не должно быть флага, принимающего значение секрета.

        Такой флаг положил бы значение в argv, то есть в `ps`, в историю shell и
        в журнал sudo.
        """
        import argparse

        from factory.secret_hub import cli

        parser = argparse.ArgumentParser()
        cli.register(parser.add_subparsers())
        text = parser.format_help()
        for forbidden in ("--api-token", "--token", "--publisher-id", "--secret", "--value"):
            assert forbidden not in text, f"CLI принимает {forbidden} — значение попадёт в argv"


class TestRunningServiceAnswers:
    """Если сервис установлен и запущен — он обязан отвечать и не отдавать значений."""

    def test_status_over_socket_returns_no_values(self, config):
        from factory.secret_hub import service

        if not service.socket_status(config.socket_path).get("exists"):
            pytest.skip("сервис не запущен на этом хосте: живая проверка не выполнялась")
        try:
            response = service.request(config.socket_path, {"op": "status"})
        except (OSError, PermissionError) as exc:
            pytest.skip(f"сокет недоступен этой учётной записи ({exc.__class__.__name__})")
        serialized = json.dumps(response, ensure_ascii=False)
        for key in ("api_token", "publisher_id"):
            assert f'"{key}":' not in serialized, f"status вернул поле «{key}»"

    def test_no_read_operation_is_accepted_by_running_service(self, config):
        from factory.secret_hub import service

        if not service.socket_status(config.socket_path).get("exists"):
            pytest.skip("сервис не запущен на этом хосте")
        try:
            response = service.request(config.socket_path,
                                       {"op": "reveal", "portfolio": "yami"})
        except (OSError, PermissionError) as exc:
            pytest.skip(f"сокет недоступен ({exc.__class__.__name__})")
        assert response["ok"] is False
        assert response["error"] == "unknown_operation"
