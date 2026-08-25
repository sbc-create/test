"""REQ-LORDS-LIVE: production читает credentials только через LoadCredential.

Запасной путь через переменные окружения убран намеренно. Переменные видны в
`systemctl show` и в `/proc/<pid>/environ`, поэтому существующий запасной путь
рано или поздно означал бы, что им воспользовались в production.

Фикстурам настоящие значения не нужны, поэтому у них свой явный режим
предпросмотра с заглушкой, которую нельзя принять за настоящий токен.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.lords import live_build


class TestNoEnvironmentFallback:
    def test_environment_variables_are_ignored(self):
        """Даже полный набор переменных не открывает production-путь."""
        with pytest.raises(live_build.LiveBuildError, match="CREDENTIALS_DIRECTORY"):
            live_build.Credentials.from_credentials_dir(env={
                "CDNVIDEOHUB_API_TOKEN": "не-должен-сработать",
                "CDNVIDEOHUB_PUBLISHER_ID": "4321",
            })

    def test_an_empty_credentials_directory_is_refused(self):
        """Пустая строка превратилась бы в Path('.') и прошла бы проверку."""
        with pytest.raises(live_build.LiveBuildError, match="CREDENTIALS_DIRECTORY"):
            live_build.Credentials.from_credentials_dir(env={"CREDENTIALS_DIRECTORY": ""})

    def test_there_is_no_from_env_constructor(self):
        assert not hasattr(live_build.Credentials, "from_env")

    def test_the_module_names_no_value_environment_variable(self):
        """В коде остаются имена credential'ов, но не имена переменных со значениями."""
        source = Path(live_build.__file__).read_text(encoding="utf-8")
        assert '"CDNVIDEOHUB_API_TOKEN"' not in source
        assert '"CDNVIDEOHUB_PUBLISHER_ID"' not in source

    def test_the_cli_uses_only_the_credentials_directory(self):
        from factory import cli
        source = Path(cli.__file__).read_text(encoding="utf-8")
        block = source.split("def cmd_lords_live", 1)[1].split("\ndef ", 1)[0]
        assert "from_credentials_dir" in block
        assert "from_env" not in block


class TestCredentialsDirectory:
    def test_values_are_read_from_files(self, tmp_path):
        (tmp_path / "cdnvideohub_api_token").write_text("живой-токен", encoding="utf-8")
        (tmp_path / "cdnvideohub_publisher_id").write_text("4321", encoding="utf-8")
        creds = live_build.Credentials.from_credentials_dir(tmp_path, env={})
        assert creds.publisher_id == "4321"
        assert creds.token == "живой-токен"
        assert not creds.is_preview

    def test_credential_names_come_from_the_dropin(self, tmp_path):
        """Имена задаёт drop-in Secret Hub, а не зашитая строка."""
        (tmp_path / "своё-имя-токена").write_text("t", encoding="utf-8")
        (tmp_path / "своё-имя-издателя").write_text("7", encoding="utf-8")
        creds = live_build.Credentials.from_credentials_dir(tmp_path, env={
            live_build.TOKEN_CREDENTIAL_ENV: "своё-имя-токена",
            live_build.PUBLISHER_CREDENTIAL_ENV: "своё-имя-издателя",
        })
        assert creds.publisher_id == "7"

    def test_a_missing_file_is_a_clear_refusal(self, tmp_path):
        with pytest.raises(live_build.LiveBuildError, match="не прочитать"):
            live_build.Credentials.from_credentials_dir(tmp_path, env={})

    def test_an_empty_value_is_refused(self, tmp_path):
        (tmp_path / "cdnvideohub_api_token").write_text("", encoding="utf-8")
        (tmp_path / "cdnvideohub_publisher_id").write_text("4321", encoding="utf-8")
        with pytest.raises(live_build.LiveBuildError, match="пустое"):
            live_build.Credentials.from_credentials_dir(tmp_path, env={})

    @pytest.mark.parametrize("value", ["0", "-1", "abc", "007"])
    def test_a_bad_publisher_id_is_refused(self, tmp_path, value):
        (tmp_path / "cdnvideohub_api_token").write_text("t", encoding="utf-8")
        (tmp_path / "cdnvideohub_publisher_id").write_text(value, encoding="utf-8")
        with pytest.raises(live_build.LiveBuildError):
            live_build.Credentials.from_credentials_dir(tmp_path, env={})


class TestPreviewMode:
    def test_preview_needs_no_real_secret(self):
        creds = live_build.Credentials.for_preview()
        assert creds.is_preview
        assert creds.token == live_build.PREVIEW_TOKEN

    def test_the_preview_token_cannot_be_mistaken_for_a_real_one(self):
        assert "PREVIEW" in live_build.PREVIEW_TOKEN
        assert "NOT-A-REAL" in live_build.PREVIEW_TOKEN

    def test_preview_still_validates_the_publisher_id(self):
        with pytest.raises(live_build.LiveBuildError):
            live_build.Credentials.for_preview("0")

    def test_a_real_credentials_object_is_not_preview(self, tmp_path):
        (tmp_path / "cdnvideohub_api_token").write_text("t", encoding="utf-8")
        (tmp_path / "cdnvideohub_publisher_id").write_text("1", encoding="utf-8")
        assert not live_build.Credentials.from_credentials_dir(tmp_path, env={}).is_preview
