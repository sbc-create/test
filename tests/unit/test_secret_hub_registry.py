"""Реестр направлений: конфигурация вместо кода, изоляция, отсутствие значений.

Ключевое требование задания — «в будущем направления должны добавляться
конфигурацией без переписывания приложения». Тест
:meth:`TestNewPortfolioNeedsNoCode.test_new_portfolio_works_without_touching_code`
проверяет именно это: направление, которого нет ни в одной строке кода,
загружается, попадает в `status` и получает свои цели.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.errors import BlockedInput
from factory.secret_hub.registry import load


@pytest.fixture
def config(repo_root):
    return load(repo_root / "config" / "secret-hub.json")


def _document(repo_root: Path) -> dict:
    return json.loads((repo_root / "config" / "secret-hub.json").read_text(encoding="utf-8"))


def _write(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "secret-hub.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


class TestShippedRegistry:
    def test_three_portfolios_are_described(self, config):
        assert config.ids() == ("yami", "lords", "amedia")

    def test_registry_contains_no_secret_values(self, repo_root):
        """В git не должно попасть ни значения, ни отпечатка."""
        text = (repo_root / "config" / "secret-hub.json").read_text(encoding="utf-8")
        document = json.loads(text)
        for portfolio in document["portfolios"]:
            assert "api_token" not in json.dumps(portfolio.get("blocked_target") or {})
            for consumer in portfolio.get("consumers", []):
                # `files` — имена файлов; значения там быть не может по схеме.
                assert set(consumer["files"]) == {"api_token", "publisher_id"}
        assert "fingerprint" not in text
        assert "sha256:" not in text

    def test_store_dir_is_outside_the_repository(self, config, repo_root):
        assert not str(config.store_dir).startswith(str(repo_root))

    def test_yami_uses_file_mount_and_lords_uses_systemd(self, config):
        assert config.portfolio("yami").consumers[0].kind == "file_mount"
        assert {c.kind for c in config.portfolio("lords").consumers} == {"systemd_credential"}

    def test_one_credential_set_per_portfolio_not_per_domain(self, config):
        """Три сайта Lords делят один набор credentials — как и требует задание."""
        lords = config.portfolio("lords")
        assert len(lords.consumers) == 3
        assert len({c.files["api_token"] for c in lords.consumers}) == 1

    def test_no_secret_is_readable_by_the_world(self, config):
        """Единственное правило без исключений: мир секрет не читает.

        Прежде здесь требовались строго owner-only права. Требование выглядело
        безопасным и один раз уже стоило публичного каталога: файл лежал с
        0400 root:root, а читать его должен был процесс контейнера, который
        работает не от root. «Строго» и «правильно» разошлись.
        """
        for portfolio in config.portfolios:
            for consumer in portfolio.consumers:
                assert not (consumer.file_mode & 0o007), \
                    f"{consumer.id}: права файла {consumer.file_mode:04o}"

    def test_modes_stay_within_the_declared_contract(self, config):
        for portfolio in config.portfolios:
            for consumer in portfolio.consumers:
                assert consumer.file_mode in (0o400, 0o440, 0o600), \
                    f"{consumer.id}: права файла {consumer.file_mode:04o}"

    def test_group_access_is_only_granted_to_a_named_non_root_reader(self, config):
        """0440 существует ради конкретного читателя, а не «на всякий случай».

        Если группа осталась root, группового доступа никто не просил, и 0440
        отличается от 0400 только видимостью послабления.
        """
        for portfolio in config.portfolios:
            for consumer in portfolio.consumers:
                if consumer.file_mode & 0o040:
                    assert consumer.group != "root", \
                        f"{consumer.id}: группе открыт доступ, но группа — root"


class TestNewPortfolioNeedsNoCode:
    def test_new_portfolio_works_without_touching_code(self, repo_root, tmp_path):
        """Направление, которого нет в коде, обязано работать из конфигурации."""
        document = _document(repo_root)
        document["portfolios"].append({
            "id": "neweditorial",
            "title": "Новое направление",
            "enabled": True,
            "consumers": [{
                "id": "neweditorial-01",
                "kind": "systemd_credential",
                "title": "neweditorial-01.service",
                "unit": "neweditorial-01.service",
                "directory": "/etc/site-factory/secrets/neweditorial/01",
                "files": {"api_token": "api-token", "publisher_id": "publisher-id"},
                "owner": "root", "group": "root",
                "file_mode": "0400", "directory_mode": "0700",
                "dropin": "/etc/systemd/system/neweditorial-01.service.d/10-cred.conf",
                "credential_names": {"api_token": "cdnvideohub_api_token",
                                     "publisher_id": "cdnvideohub_publisher_id"},
                "reload": {"kind": "systemd"},
            }],
        })
        config = load(_write(tmp_path, document))

        assert "neweditorial" in config.ids()
        portfolio = config.portfolio("neweditorial")
        assert portfolio.deployable is True
        assert portfolio.units() == ("neweditorial-01.service",)

        from factory.secret_hub import consumers as consumers_mod

        rows = consumers_mod.describe(portfolio)
        assert rows[0]["consumer"] == "neweditorial-01"

    def test_portfolio_ids_are_not_hardcoded_in_the_package(self, repo_root):
        """В коде пакета не должно быть списка направлений."""
        package = repo_root / "factory" / "secret_hub"
        offenders: list[str] = []
        for path in package.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or '"""' in stripped:
                    continue
                # Литерал направления в условии — это ровно то «переписывание
                # приложения», которого задание требует избежать.
                for marker in ('== "yami"', '== "lords"', '== "amedia"',
                               '"yami":', '"lords":', '"amedia":'):
                    if marker in stripped:
                        offenders.append(f"{path.name}: {stripped}")
        assert offenders == [], "направления зашиты в код: " + "; ".join(offenders)


class TestIsolationIsEnforcedAtLoad:
    def test_shared_directory_between_portfolios_is_refused(self, repo_root, tmp_path):
        document = _document(repo_root)
        shared = document["portfolios"][0]["consumers"][0]["directory"]
        document["portfolios"][1]["consumers"][0]["directory"] = shared
        with pytest.raises(BlockedInput) as excinfo:
            load(_write(tmp_path, document))
        assert "ломает изоляцию" in excinfo.value.reason

    def test_shared_unit_between_portfolios_is_refused(self, repo_root, tmp_path):
        document = _document(repo_root)
        document["portfolios"][0]["consumers"][0].update({
            "kind": "systemd_credential",
            "unit": "lords-01.service",
            "dropin": "/etc/systemd/system/lords-01.service.d/20-x.conf",
            "credential_names": {"api_token": "a", "publisher_id": "b"},
            "directory_mode": "0700",
        })
        document["portfolios"][0]["consumers"][0].pop("compose_file", None)
        document["portfolios"][0]["consumers"][0].pop("expect_mount_target", None)
        with pytest.raises(BlockedInput) as excinfo:
            load(_write(tmp_path, document))
        assert "Unit" in excinfo.value.reason

    def test_duplicate_portfolio_id_is_refused(self, repo_root, tmp_path):
        document = _document(repo_root)
        document["portfolios"].append(dict(document["portfolios"][0]))
        with pytest.raises(BlockedInput) as excinfo:
            load(_write(tmp_path, document))
        assert "описано дважды" in excinfo.value.reason


class TestSchemaIsAuthoritative:
    def test_store_dir_inside_repository_is_refused(self, repo_root, tmp_path):
        document = _document(repo_root)
        document["store_dir"] = str(repo_root / "var" / "hub")
        with pytest.raises(BlockedInput) as excinfo:
            load(_write(tmp_path, document))
        assert "внутрь репозитория" in excinfo.value.reason

    def test_world_readable_file_mode_is_refused_by_schema(self, repo_root, tmp_path):
        document = _document(repo_root)
        document["portfolios"][0]["consumers"][0]["file_mode"] = "0644"
        with pytest.raises(BlockedInput) as excinfo:
            load(_write(tmp_path, document))
        assert "не соответствует схеме" in excinfo.value.reason

    def test_non_get_verification_is_refused_by_schema(self, repo_root, tmp_path):
        """Проверка обязана быть read-only. POST схема не принимает."""
        document = _document(repo_root)
        document["provider"]["verify"]["method"] = "POST"
        with pytest.raises(BlockedInput):
            load(_write(tmp_path, document))

    def test_empty_portfolio_must_declare_blocked_target(self, repo_root, tmp_path):
        """Направление без потребителей обязано объяснить, почему их нет."""
        document = _document(repo_root)
        document["portfolios"].append({"id": "quiet", "title": "Тихое", "enabled": True,
                                       "consumers": []})
        with pytest.raises(BlockedInput):
            load(_write(tmp_path, document))

    def test_systemd_consumer_must_name_its_unit(self, repo_root, tmp_path):
        document = _document(repo_root)
        del document["portfolios"][1]["consumers"][0]["unit"]
        with pytest.raises(BlockedInput):
            load(_write(tmp_path, document))

    def test_missing_registry_is_blocked_input(self, tmp_path):
        with pytest.raises(BlockedInput) as excinfo:
            load(tmp_path / "нет-такого.json")
        assert excinfo.value.status == "BLOCKED_INPUT"


class TestCli:
    def test_status_prints_no_values(self, capsys):
        from factory.secret_hub import cli

        cli._print_status({
            "master_key": {"stored_correctly": True, "problems": []},
            "store": {"path": "/var/lib/x", "permission_problems": []},
            "portfolios": [{
                "portfolio": "yami", "configured": True, "verified": True,
                "updated_at": "2026-08-25T00:00:00Z", "fingerprint": "sha256:abc",
                "version": 1, "consumers": [], "deployment": [],
            }],
        })
        out = capsys.readouterr().out
        assert "sha256:abc" in out
        assert "не могут быть получены через этот интерфейс" in out

    def test_actions_do_not_include_a_read_action(self):
        from factory.secret_hub import cli

        for forbidden in ("get", "read", "show", "reveal", "export"):
            assert forbidden not in cli.ACTIONS

    def test_mutating_actions_require_a_portfolio(self):
        from factory.secret_hub import cli

        for action in ("apply", "rotate", "revoke", "verify", "import", "enroll"):
            assert action in cli.NEEDS_PORTFOLIO
