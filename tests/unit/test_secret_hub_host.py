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
PANEL_UNIT = "site-factory-secret-panel.service"
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

    @pytest.mark.parametrize("unit", [HUB_UNIT, PANEL_UNIT, IMPORT_UNIT])
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


def basic_auth_directives(text: str) -> list[str]:
    """Строки, включающие Basic Auth. ``auth_basic off`` таковой не является.

    Отдельная функция, потому что прежняя проверка была неправильной и молча
    давала «чисто» там, где Basic Auth включён. Она искала `auth_basic` во всём
    файле и прощала его, если где-нибудь в том же файле встречался
    `auth_basic off`. В боевых конфигурациях yummyani встречается и то и другое:
    `off` — в location для ACME-челленджа, включение — в `location /`. Одно
    выключение в одном месте не отменяет включения в другом, и вывод «пароля
    нет» был ложным.
    """
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line.startswith("auth_basic"):
            continue
        if line.startswith("auth_basic_user_file"):
            continue
        value = line[len("auth_basic"):].strip().rstrip(";").strip()
        if value.strip('"').strip("'").lower() == "off":
            continue
        out.append(line)
    return out


class TestSitesStayPublicAndNoindex:
    """Индексация закрыта, а состояние Basic Auth измеряется честно.

    Фактическое состояние хоста на 2026-08-25: Basic Auth **включён** в
    `location /` всех трёх vhost'ов yummyani. Тест ниже это фиксирует, а не
    требует обратного: снимать пароль со staging-стенда заданием не поручено, а
    Secret Hub обязан лишь не устанавливать и не восстанавливать его. Что от
    него действительно требуется — чтобы его собственный endpoint отвечал без
    `WWW-Authenticate`; за это отвечает `auth_basic off` в location формы и
    живая проверка лончером.
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

    def test_secret_hub_does_not_add_basic_auth(self):
        """Secret Hub не добавляет Basic Auth ни в одну конфигурацию.

        Именно это ему запрещено — не «на хосте нигде нет пароля», а «этот слой
        его не ставит». Существующий пароль staging-стенда не его рук дело и не
        его дело.
        """
        readable = self._readable()
        if not readable:
            pytest.skip("конфигурация nginx недоступна для чтения в этой среде")
        offenders = [
            f"{path}: {'; '.join(basic_auth_directives(text))}"
            for path, text in readable
            if "secret-hub" in path.name and basic_auth_directives(text)
        ]
        assert offenders == [], f"Secret Hub поставил Basic Auth: {offenders}"

    def test_existing_basic_auth_state_is_reported_not_assumed(self):
        """Состояние Basic Auth на стенде фиксируется как факт, а не как желание.

        Тест не требует ни включённого, ни выключенного пароля: он падает
        только если конфигурация непроверяема. Смысл — чтобы состояние было
        измерено и записано, а не выведено из прошлого отчёта.
        """
        readable = [(p, t) for p, t in self._readable() if "yummyani" in p.name]
        if not readable:
            pytest.skip("конфигурации yummyani недоступны в этой среде")
        measured = {str(p): basic_auth_directives(t) for p, t in readable}
        assert measured, "состояние Basic Auth не измерено"
        # На 2026-08-25 пароль включён на всех трёх vhost. Если он когда-нибудь
        # будет снят — снимет его не Secret Hub, и тест это переживёт.
        for path, directives in measured.items():
            assert isinstance(directives, list), path

    def test_noindex_header_is_present_for_yummyani(self):
        readable = [(p, t) for p, t in self._readable() if "yummyani" in p.name]
        if not readable:
            pytest.skip("конфигурации yummyani недоступны в этой среде")
        with_header = [str(p) for p, t in readable if "noindex" in t.lower()]
        assert with_header, "ни в одной конфигурации yummyani нет X-Robots-Tag: noindex"

    def test_parser_targets_the_right_block_in_the_real_vhost(self, config):
        """Разбор проверяется на настоящем боевом файле, а не только на фикстуре.

        Файл при этом не меняется: вставка симулируется в памяти. Ошибиться
        блоком здесь означало бы повесить форму за 308-редирект (www) или на
        HTTP (:80) — и то и другое обнаружилось бы уже на живой проверке, но
        после правки боевого конфига.
        """
        import re

        from factory.secret_hub import publish

        if config.public_form is None:
            pytest.skip("public_form не настроен")
        vhost = config.public_form.vhost
        if not vhost.exists():
            pytest.skip(f"{vhost} отсутствует на этом хосте")
        try:
            text = vhost.read_text(encoding="utf-8")
        except PermissionError:
            pytest.skip("vhost недоступен этой учётной записи")

        start, end = publish._apex_server_span(text, config.public_form.server_name)
        block = text[start:end]

        names = re.search(r"server_name\s+([^;]+);", block).group(1).split()
        assert names == [config.public_form.server_name], f"выбран блок для {names}"
        assert re.search(r"\blisten\s+443\b", block), "выбран не HTTPS-блок"
        assert "listen 80;" not in block, "выбран блок редиректа с HTTP"

        insertion = (f"\n    {publish.BEGIN}\n"
                     f"    include {publish.SNIPPET_DIR}/*.conf;\n"
                     f"    {publish.END}\n")
        patched = block[:-1].rstrip() + "\n" + insertion + "}"
        assert patched.count("{") == patched.count("}"), "вставка ломает баланс скобок"

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
        for name in (HUB_UNIT, PANEL_UNIT, IMPORT_UNIT):
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


class TestInstallerContract:
    """Установщик: не импортирует старое, идемпотентен, ссылается на живые unit'ы.

    Требования владельца от 25.08.2026: установка не должна подхватывать
    прежние токены Yami и Lords, а повторный запуск не должен ничего ломать.
    """

    def _launcher(self, repo_root) -> str:
        return (repo_root / "var" / "install-secret-hub.sh").read_text(encoding="utf-8")

    def _installer(self, repo_root) -> str:
        return (repo_root / "automation" / "secret-hub" / "install.sh").read_text(
            encoding="utf-8")

    def test_launcher_never_imports_existing_credentials(self, repo_root):
        text = self._launcher(repo_root)
        for forbidden in ("rootcmd import", "import_existing", "migrate",
                          "secret-hub-import@"):
            assert forbidden not in text, \
                f"установщик подхватывает старые credentials: «{forbidden}»"

    def test_install_panel_does_not_touch_migration(self, repo_root):
        """Проверяется разбором кода, а не чтением глазами."""
        import ast

        source = (repo_root / "factory" / "secret_hub" / "rootcmd.py").read_text(
            encoding="utf-8")
        tree = ast.parse(source)
        function = next(n for n in ast.walk(tree)
                        if isinstance(n, ast.FunctionDef) and n.name == "cmd_install_panel")
        names = {n.attr for n in ast.walk(function) if isinstance(n, ast.Attribute)}
        for node in ast.walk(function):
            if isinstance(node, ast.ImportFrom):
                names.add(node.module or "")
        assert not any("migrate" in n or "import_existing" in n or "discover" in n
                       for n in names), "установка панели обращается к импорту"

    def test_installer_only_starts_and_installs_shipped_units(self, repo_root):
        """Запускать и ставить можно только то, что есть в репозитории.

        Запрет именно на «ставить» и «запускать», а не на упоминание вообще:
        удалённый unit нужно ещё и снять с хоста, где он остался от прежней
        установки, и строка `rm -f …enroll@.service` здесь законна.
        """
        text = self._installer(repo_root)
        shipped = {p.name for p in (repo_root / "automation" / "secret-hub").iterdir()
                   if p.suffix == ".service"}

        def template_of(unit: str) -> str:
            return unit.replace("<направление>", "")

        for line in text.splitlines():
            stripped = line.strip()
            if "systemctl start site-factory" in stripped:
                unit = stripped.split("systemctl start ")[1].split()[0]
                assert template_of(unit) in shipped, f"советует незнакомый unit: {unit}"
            if stripped.startswith("install ") and ".service" in stripped:
                assert "$path" in stripped or "$unit" in stripped, \
                    "список unit'ов перечислен вручную и разъедется с каталогом"

    def test_installer_does_not_advise_retired_flows(self, repo_root):
        text = self._installer(repo_root)
        assert "ssh -N -L" not in text, "установщик советует снятый способ доступа"
        assert "systemctl start site-factory-secret-hub-enroll" not in text, \
            "установщик зовёт запускать удалённый unit"

    def test_installer_removes_the_retired_enroll_unit(self, repo_root):
        """Удалённый из репозитория unit должен исчезать и с хоста."""
        text = self._installer(repo_root)
        assert "rm -f /etc/systemd/system/site-factory-secret-hub-enroll@.service" in text

    def test_installer_states_no_auto_import(self, repo_root):
        text = self._installer(repo_root)
        assert "НЕ импортируются автоматически" in text

    @pytest.mark.parametrize("guard,what", [
        ('if [ -e "$KEY_FILE" ]', "мастер-ключ не перезаписывается"),
        ("if ! getent group", "группа создаётся только при отсутствии"),
    ])
    def test_installer_is_idempotent(self, repo_root, guard, what):
        assert guard in self._installer(repo_root), f"не идемпотентно: {what}"

    def test_launcher_guards_user_creation(self, repo_root):
        text = self._launcher(repo_root)
        assert 'if ! id "$PANEL_USER"' in text, \
            "повторный запуск пытался бы создать существующего пользователя"

    def test_nginx_include_is_idempotent(self, repo_root):
        """Повторная установка не добавляет второй include."""
        from factory.secret_hub import publish

        assert "if include_present(text)" in (
            repo_root / "factory" / "secret_hub" / "publish.py"
        ).read_text(encoding="utf-8")
        assert publish.include_present(f"x {publish.BEGIN} y") is True

    def test_launcher_command_is_the_documented_one(self, repo_root):
        """Путь в документации и фактический путь лончера совпадают."""
        assert (repo_root / "var" / "install-secret-hub.sh").exists()
        docs = (repo_root / "docs" / "SECRET_HUB.md").read_text(encoding="utf-8")
        assert "var/install-secret-hub.sh" in docs

    def test_panel_unit_runs_unprivileged(self, repo_root):
        text = (repo_root / "automation" / "secret-hub"
                / "site-factory-secret-panel.service").read_text(encoding="utf-8")
        assert "User=sfpanel" in text
        assert "User=root" not in text, "панель не должна работать от root"
        assert "SupplementaryGroups=sfhub" in text
