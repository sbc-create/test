"""Доведение сохранённого до потребителей одной командой, без клика владельца.

Симптом, ради которого написан модуль: Lords сохранён и проверен (версия 2), но
не применён ни к одному из трёх сайтов, и владельцу оставался отдельный клик
«Применить к сайтам». Расхождение между «сохранено» и «применено» должна
устранять машина.

Проверяется, что приведение к состоянию:

* не создаёт новых версий и не требует повторного ввода;
* доходит до всех потребителей направления;
* идемпотентно — применённое второй раз не перезапускает сайты;
* не печатает значений;
* проверяет результат на диске и в systemd, а не по собственному отчёту.
"""
from __future__ import annotations

import os
import stat as stat_mod

import pytest

from factory.secret_hub import consumers as consumers_mod
from factory.secret_hub import crypto, reconcile
from factory.secret_hub.registry import Consumer, Portfolio
from factory.secret_hub.registry import load as load_config
from factory.secret_hub.service import Hub
from factory.secret_hub.store import Store

TOKEN = "СОХРАНЁННЫЙ-ТОКЕН-V2"
PUBLISHER = "pub-lords"
LORDS_IDS = ("lords-01", "lords-02", "lords-03")


@pytest.fixture(autouse=True)
def offline_provider(monkeypatch):
    from factory.secret_hub import provider as provider_mod

    monkeypatch.setattr(
        provider_mod, "verify",
        lambda c, a, p, opener=None, portfolio="-": provider_mod.VerifyResult(
            provider_mod.Outcome.ACCEPTED, 200, "принято", True, c.url))


@pytest.fixture(autouse=True)
def fake_systemd(monkeypatch):
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = "active\n"

    monkeypatch.setattr(consumers_mod.subprocess, "run",
                        lambda cmd, **kw: (calls.append(list(cmd)), Result())[1])
    monkeypatch.setattr(consumers_mod, "_unit_exists", lambda unit: True)
    return calls


@pytest.fixture
def stand(tmp_path, repo_root, monkeypatch):
    """Хаб с направлением Lords, чьи цели лежат во временном дереве."""
    key = tmp_path / "master.key"
    key.write_text(crypto.generate_master_key(), encoding="utf-8")
    os.chmod(key, 0o600)
    master = crypto.load_master_key(key, require_root_owner=False)

    base = load_config(repo_root / "config" / "secret-hub.json")
    secrets = tmp_path / "etc" / "site-factory" / "secrets"
    secrets.mkdir(parents=True)

    source = base.portfolio("lords")
    lords = Portfolio(source.id, source.title, True, tuple(
        Consumer(**{**c.__dict__,
                    "directory": secrets / "lords" / c.id,
                    "dropin": tmp_path / "systemd" / f"{c.unit}.d" / "10-cred.conf"})
        for c in source.consumers))
    config = type(base)(base.source, tmp_path / "hub", tmp_path / "hub.sock",
                        base.control_group, base.provider_name, base.verify,
                        (lords,), base.public_form)
    hub = Hub(config, master, Store(config.db_path, master))
    # Две версии: активная — вторая, как на боевом хосте.
    for _ in range(2):
        hub.store.put("lords", {"api_token": crypto.Secret(TOKEN, "t"),
                                "publisher_id": crypto.Secret(PUBLISHER, "p")},
                      provider="cdnvideohub", verified_at="2026-08-25T00:00:00Z")
    return hub


class TestAppliesWithoutReentry:
    def test_saved_version_reaches_all_three(self, stand):
        report = reconcile.run(stand)
        assert report.ok, report.as_dict()
        result = report.results[0]
        assert result.action == "applied"
        assert result.applied == 3
        assert result.total == 3

    def test_version_is_not_changed(self, stand):
        """Повторный ввод не требуется — версия остаётся той же."""
        before = stand.store.state("lords").active_version
        assert before == 2
        reconcile.run(stand)
        assert stand.store.state("lords").active_version == 2

    def test_no_new_version_is_created(self, stand):
        before = len(stand.store.state("lords").versions)
        reconcile.run(stand)
        assert len(stand.store.state("lords").versions) == before

    def test_files_land_for_every_consumer(self, stand):
        reconcile.run(stand)
        for consumer in stand.config.portfolio("lords").consumers:
            for field in ("api_token", "publisher_id"):
                path = consumer.path_for(field)
                assert path.exists(), f"{consumer.id}: нет {field}"
                assert stat_mod.S_IMODE(path.stat().st_mode) == 0o400

    def test_dropin_has_loadcredential_without_values(self, stand):
        reconcile.run(stand)
        for consumer in stand.config.portfolio("lords").consumers:
            text = consumer.dropin.read_text(encoding="utf-8")
            assert "LoadCredential=" in text
            assert TOKEN not in text
            assert PUBLISHER not in text


class TestIdempotency:
    def test_second_run_does_not_reapply(self, stand, fake_systemd):
        reconcile.run(stand)
        fake_systemd.clear()
        second = reconcile.run(stand)
        assert second.results[0].action == "already"
        restarts = [c for c in fake_systemd if len(c) > 1 and c[1] == "restart"]
        assert restarts == [], "лишний перезапуск сайтов при повторном запуске"

    def test_force_reapplies(self, stand, fake_systemd):
        reconcile.run(stand)
        fake_systemd.clear()
        forced = reconcile.run(stand, force=True)
        assert forced.results[0].action == "applied"
        assert any(c[1] == "restart" for c in fake_systemd if len(c) > 1)

    def test_only_lords_units_are_restarted(self, stand, fake_systemd):
        reconcile.run(stand)
        restarted = [c[2] for c in fake_systemd if len(c) > 2 and c[1] == "restart"]
        assert restarted == [f"{i}.service" for i in LORDS_IDS]


class TestSkipsWhatItShould:
    def test_unconfigured_portfolio_is_skipped_not_prompted(self, stand, repo_root):
        """Ненастроенное направление не повод просить ввод."""
        base = load_config(repo_root / "config" / "secret-hub.json")
        stand.config = type(base)(
            base.source, stand.config.store_dir, stand.config.socket_path,
            base.control_group, base.provider_name, base.verify,
            base.portfolios, base.public_form)
        report = reconcile.run(stand, only="yami")
        result = report.results[0]
        assert result.action == "skipped"
        assert "вводить их здесь нечем" in result.reason

    def test_blocked_target_is_skipped_with_its_reason(self, stand, repo_root):
        base = load_config(repo_root / "config" / "secret-hub.json")
        stand.config = type(base)(
            base.source, stand.config.store_dir, stand.config.socket_path,
            base.control_group, base.provider_name, base.verify,
            base.portfolios, base.public_form)
        report = reconcile.run(stand, only="amedia")
        assert report.results[0].action == "skipped"
        assert report.results[0].reason


class TestNoSecretsInOutput:
    def test_report_has_no_values(self, stand):
        report = reconcile.run(stand)
        assert TOKEN not in str(report.as_dict())
        assert PUBLISHER not in str(report.as_dict())

    def test_printed_report_has_no_values(self, stand):
        text = reconcile.format_report(reconcile.run(stand))
        assert TOKEN not in text
        assert PUBLISHER not in text

    def test_audit_has_no_values(self, stand):
        reconcile.run(stand)
        result = reconcile.audit(stand)
        assert TOKEN not in str(result)
        assert PUBLISHER not in str(result)
        assert TOKEN not in reconcile.format_audit(result)


class TestAuditChecksTheHostNotTheReport:
    def test_audit_sees_files_modes_and_units(self, stand, monkeypatch):
        reconcile.run(stand)
        import subprocess as subprocess_mod

        class Result:
            stdout = "active\n"
            returncode = 0

        monkeypatch.setattr(subprocess_mod, "run", lambda *a, **k: Result())
        result = reconcile.audit(stand)
        assert len(result["consumers"]) == 3
        for row in result["consumers"]:
            assert row["directory_mode"] == "0700"
            assert row["dropin_has_loadcredential"] is True
            assert row["dropin_only_paths"] is True
            assert row["unit_state"] == "active"
            assert all(f["mode"] == "0400" and not f["empty"] for f in row["files"])

    def test_audit_reports_missing_files(self, stand, monkeypatch):
        reconcile.run(stand)
        consumer = stand.config.portfolio("lords").consumers[0]
        consumer.path_for("api_token").unlink()

        result = reconcile.audit(stand)
        assert result["ok"] is False
        problems = " ".join(p for r in result["consumers"] for p in r["problems"])
        assert "не создан" in problems

    def test_audit_flags_a_restart_loop(self, stand, monkeypatch):
        """`activating` у Type=simple — это цикл перезапуска, а не запуск."""
        reconcile.run(stand)
        import subprocess as subprocess_mod

        class Result:
            stdout = "activating\n"
            returncode = 0

        monkeypatch.setattr(subprocess_mod, "run", lambda *a, **k: Result())
        result = reconcile.audit(stand)
        assert result["ok"] is False
        problems = " ".join(p for r in result["consumers"] for p in r["problems"])
        assert "цикл перезапуска" in problems

    @pytest.mark.skipif(os.geteuid() == 0, reason="проверка смысла только не от root")
    def test_audit_is_strict_about_root_ownership(self, stand):
        """От не-root файлы не будут root:root — и проверка обязана это заметить."""
        reconcile.run(stand)
        result = reconcile.audit(stand)
        problems = " ".join(p for r in result["consumers"] for p in r["problems"])
        assert "root" in problems


class TestLauncherRunsReconcile:
    def test_launcher_calls_reconcile(self, repo_root):
        text = (repo_root / "var" / "install-secret-hub.sh").read_text(encoding="utf-8")
        assert "rootcmd reconcile" in text, \
            "владельцу остался бы отдельный клик «Применить к сайтам»"

    def test_reconcile_runs_after_the_panel_is_up(self, repo_root):
        text = (repo_root / "var" / "install-secret-hub.sh").read_text(encoding="utf-8")
        assert text.index("install-panel") < text.index("rootcmd reconcile")

    def test_launcher_failure_propagates(self, repo_root):
        text = (repo_root / "var" / "install-secret-hub.sh").read_text(encoding="utf-8")
        assert "reconcile_code" in text, "отказ применения потерялся бы"
