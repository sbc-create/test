"""REQ-LORDS-LIVE: сборка живого каталога и сценарий активации.

Здесь проверяются две вещи: что живая сборка отказывается публиковать
непригодный результат, и что активатор устроен так, как обещано, — без боевых
секретов и без обращения к сети.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from factory.lords import content_live, live_build, player
from factory.paths import PATHS

ACTIVATOR = PATHS.root / "automation/host/activate-lords-live.sh"
PUBLISHER = "4321"


def fake_fetcher_factory(pages, contract):
    from tests.unit.test_lords_content_api_live import FakeApi

    def factory(_site):
        api = FakeApi(pages())
        return content_live.Fetcher(
            contract=contract, token="not-a-real-credential",
            opener=api.opener, sleep=lambda _s: None, monotonic=lambda: 0.0,
        )
    return factory


@pytest.fixture(scope="module")
def contract():
    return content_live.load_live_contract()


# ---------------------------------------------------------------------------
# Учётные данные
# ---------------------------------------------------------------------------
class TestCredentials:
    def test_missing_secrets_block_the_build(self):
        with pytest.raises(live_build.LiveBuildError, match="не переданы"):
            live_build.Credentials.from_env({})

    def test_a_non_numeric_publisher_id_blocks_the_build(self):
        with pytest.raises(live_build.LiveBuildError, match="положительным целым"):
            live_build.Credentials.from_env({
                "CDNVIDEOHUB_API_TOKEN": "t", "CDNVIDEOHUB_PUBLISHER_ID": "abc",
            })

    def test_a_public_publisher_variable_blocks_the_build(self):
        with pytest.raises(player.PublicPublisherIdError):
            live_build.Credentials.from_env({
                "CDNVIDEOHUB_API_TOKEN": "t",
                "CDNVIDEOHUB_PUBLISHER_ID": "1",
                player.FORBIDDEN_PUBLIC_ENV: "1",
            })

    def test_valid_credentials_are_accepted(self):
        creds = live_build.Credentials.from_env({
            "CDNVIDEOHUB_API_TOKEN": "t", "CDNVIDEOHUB_PUBLISHER_ID": PUBLISHER,
        })
        assert creds.publisher_id == PUBLISHER


# ---------------------------------------------------------------------------
# Пригодность результата
# ---------------------------------------------------------------------------
class TestReportVerification:
    def _report(self, **site):
        base = {
            "status": content_live.FRESH, "item_count": 5,
            "sections_enabled": ["movies"], "playable_count": 3,
        }
        base.update(site)
        return {"sites": {"lords-01": base}}

    def test_a_good_report_passes(self):
        assert live_build.verify_report(self._report()) == []

    def test_an_empty_catalog_is_refused(self):
        problems = live_build.verify_report(self._report(item_count=0))
        assert any("пуст" in p for p in problems)

    def test_a_stale_source_is_refused_for_activation(self):
        """Переключаться на устаревший кэш нельзя: это не живой каталог."""
        problems = live_build.verify_report(self._report(status=content_live.STALE))
        assert any("статус источника" in p for p in problems)

    def test_a_blocked_source_is_refused(self):
        problems = live_build.verify_report(self._report(status=content_live.BLOCKED_SOURCE))
        assert problems

    def test_a_site_without_sections_is_refused(self):
        problems = live_build.verify_report(self._report(sections_enabled=[]))
        assert any("раздел" in p for p in problems)

    def test_a_catalog_without_playable_titles_is_refused(self):
        """Без пары агрегатор/идентификатор плеер показать нечего."""
        problems = live_build.verify_report(self._report(playable_count=0))
        assert any("агрегатор" in p for p in problems)

    def test_an_empty_report_is_refused(self):
        assert live_build.verify_report({"sites": {}})


# ---------------------------------------------------------------------------
# Сборка на поддельном источнике
# ---------------------------------------------------------------------------
class TestBuild:
    def test_three_sites_are_built_and_kept_separate(self, contract, tmp_path, monkeypatch):
        from tests.unit.test_lords_content_api_live import page, title

        monkeypatch.setattr(live_build, "_catalog_dir", lambda: tmp_path)
        pages = lambda: [page([title("a"), title("b", kind="series")])]  # noqa: E731
        report = live_build.build_live(
            credentials=live_build.Credentials.from_env({
                "CDNVIDEOHUB_API_TOKEN": "t", "CDNVIDEOHUB_PUBLISHER_ID": PUBLISHER,
            }),
            contract=contract,
            fetcher_factory=fake_fetcher_factory(pages, contract),
            now_ms=1_000,
        )
        assert sorted(report["sites"]) == ["lords-01", "lords-02", "lords-03"]
        for entry in report["sites"].values():
            assert entry["status"] == content_live.FRESH
            assert entry["item_count"] == 2
        # У каждого сайта свой файл кэша: каталоги не делятся.
        caches = sorted(p.name for p in (tmp_path / "lords" / "catalog-cache").iterdir())
        assert caches == ["lords-01.json", "lords-02.json", "lords-03.json"]

    def test_the_report_carries_no_secret(self, contract, tmp_path, monkeypatch):
        from tests.unit.test_lords_content_api_live import page, title

        monkeypatch.setattr(live_build, "_catalog_dir", lambda: tmp_path)
        pages = lambda: [page([title("a")])]  # noqa: E731
        report = live_build.build_live(
            credentials=live_build.Credentials.from_env({
                "CDNVIDEOHUB_API_TOKEN": "super-secret-value",
                "CDNVIDEOHUB_PUBLISHER_ID": PUBLISHER,
            }),
            contract=contract,
            fetcher_factory=fake_fetcher_factory(pages, contract),
            now_ms=1,
        )
        text = live_build.redact(report)
        assert "super-secret-value" not in text
        assert json.loads(text)["api_token_present"] is True

    def test_an_empty_source_produces_an_unusable_report(self, contract, tmp_path, monkeypatch):
        from tests.unit.test_lords_content_api_live import page

        monkeypatch.setattr(live_build, "_catalog_dir", lambda: tmp_path)
        pages = lambda: [page([])]  # noqa: E731
        report = live_build.build_live(
            credentials=live_build.Credentials.from_env({
                "CDNVIDEOHUB_API_TOKEN": "t", "CDNVIDEOHUB_PUBLISHER_ID": PUBLISHER,
            }),
            contract=contract,
            fetcher_factory=fake_fetcher_factory(pages, contract),
            now_ms=1,
        )
        assert live_build.verify_report(report), "пустой источник обязан быть непригоден"


# ---------------------------------------------------------------------------
# Активатор
# ---------------------------------------------------------------------------
class TestActivatorScript:
    @pytest.fixture(scope="class")
    def text(self):
        return ACTIVATOR.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def code(self):
        """Только исполняемые строки, продолжения склеены.

        Построчный разбор здесь врал дважды: комментарий, описывающий запрет,
        выглядел как нарушение, а curl, разнесённый на три строки обратными
        слешами, выглядел как вызов без --resolve.
        """
        joined = ACTIVATOR.read_text(encoding="utf-8").replace("\\\n", " ")
        return [
            line for line in joined.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def test_it_parses(self):
        result = subprocess.run(["/bin/bash", "-n", str(ACTIVATOR)],
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr

    def test_it_refuses_to_run_without_root(self):
        result = subprocess.run(["/bin/bash", str(ACTIVATOR)],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode != 0
        assert "нужен root" in result.stderr

    def test_the_token_prompt_is_hidden(self, text):
        assert "read -rsp" in text, "токен читается без скрытия ввода"

    def test_the_publisher_id_is_validated_as_a_number(self, text):
        assert "^[1-9][0-9]*$" in text

    def test_rights_confirmation_is_required(self, text):
        assert "RIGHTS_CONFIRMED=yes" in text

    def test_the_token_is_probed_before_any_mutation(self, text):
        probe = text.index("проверка токена")
        snapshot = text.index("снимок текущего стенда")
        assert probe < snapshot, "токен проверяется после начала изменений"

    def test_secrets_are_written_with_the_required_mode(self, text):
        assert "chmod 0600" in text
        assert "chown root:root" in text
        assert "install -d -m 0700" in text

    def test_secrets_are_written_atomically(self, text):
        assert 'mv -f "${TOKEN_FILE}.tmp" "${TOKEN_FILE}"' in text

    def test_no_secret_is_echoed(self, code):
        for line in code:
            stripped = line.strip()
            if stripped.startswith(("log ", "warn ", "echo ")):
                assert "${API_TOKEN}" not in stripped, stripped
                assert "${PUBLISHER_ID}" not in stripped, stripped

    def test_the_token_is_not_passed_in_argv(self, text):
        """argv виден в ps любому пользователю."""
        assert 'CDNVIDEOHUB_API_TOKEN="${API_TOKEN}"' in text
        assert "--token" not in text

    def test_seed_and_reset_are_absent(self, code):
        """Проверяются исполняемые строки: в комментарии запрет описан намеренно."""
        for line in code:
            lowered = line.lower()
            for forbidden in ("db push", "accept-data-loss", "db reset", "db seed"):
                assert forbidden not in lowered, line

    def test_only_the_three_lords_units_are_restarted(self, text):
        restarts = [line for line in text.splitlines() if "systemctl restart" in line]
        assert restarts, "юниты не перезапускаются"
        for line in restarts:
            assert "yummy" not in line.lower()

    def test_rollback_runs_once_via_a_file_marker(self, text):
        assert "ROLLBACK_MARKER" in text
        assert "noclobber" in text

    def test_the_handler_disarms_the_trap_before_rolling_back(self, text):
        handler = text.split("on_error() {", 1)[1].split("\n}", 1)[0]
        assert "trap - ERR" in handler
        assert handler.index("trap - ERR") < handler.index("rollback")

    def test_acceptance_pins_to_the_local_origin(self, code):
        started = False
        for line in code:
            if 'stage "публичная приёмка"' in line:
                started = True
            if started and "https://" in line and "curl" in line:
                assert "pin[@]" in line or "--resolve" in line, line
        assert started, "блок приёмки не найден"

    def test_tls_verification_is_never_disabled(self, code):
        for line in code:
            if "curl" in line:
                assert " -k" not in line and "--insecure" not in line, line

    def test_it_checks_the_expected_sha(self, text):
        assert "EXPECT_SHA" in text
        assert "rev-parse HEAD" in text

    def test_the_expected_sha_is_required_not_defaulted(self, text):
        """Пускатель обязан передать SHA: молчаливого значения по умолчанию нет.

        Проверка живёт после проверки root, иначе запуск без прав сообщал бы
        не о том, чего не хватает.
        """
        assert "не передан LORDS_EXPECT_SHA" in text
        assert text.index("нужен root") < text.index("не передан LORDS_EXPECT_SHA")

    def test_it_lives_in_a_tracked_path(self):
        """var/ в .gitignore: сценарий там не дошёл бы до CI и не проверялся бы."""
        import subprocess
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(ACTIVATOR.relative_to(PATHS.root))],
            capture_output=True, text=True, cwd=PATHS.root, timeout=60,
        )
        assert result.returncode == 0, "активатор не отслеживается git"

    def test_it_verifies_indexing_stays_closed(self, text):
        assert "noindex" in text
        assert "Disallow: /" in text

    def test_it_checks_the_neighbour_is_untouched(self, text):
        assert "yummyani.biz" in text

    def test_it_does_not_touch_certificates_or_basic_auth(self, text):
        lowered = text.lower()
        assert "certbot" not in lowered
        assert "htpasswd" not in lowered

    def test_rollback_restores_the_previous_release(self, text):
        rollback = text.split("rollback() {", 1)[1].split("\non_error()", 1)[0]
        assert "previous-release" in rollback
        assert "current" in rollback

    def test_rollback_removes_secrets_that_did_not_exist_before(self, text):
        rollback = text.split("rollback() {", 1)[1].split("\non_error()", 1)[0]
        assert "secrets-existed" in rollback
        assert 'rm -f "${TOKEN_FILE}"' in rollback
