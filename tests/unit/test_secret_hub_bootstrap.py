"""Приёмочный сценарий: импорт раньше формы, форма только для недостающего.

Главное требование задания, которое здесь проверяется: «до запроса повторного
ввода проверь наличие существующих credentials». Форма — последнее средство, а
не первое, и открывается ровно для тех направлений, которых не хватило.
"""
from __future__ import annotations

import os

import pytest

from factory.secret_hub import bootstrap, crypto
from factory.secret_hub.registry import load as load_config
from factory.secret_hub.service import Hub
from factory.secret_hub.store import Store

TOKEN = "МАРКЕР-ТОКЕНА-ПРИЁМКИ"
PUBLISHER = "publisher-приёмка"


@pytest.fixture
def hub(tmp_path, repo_root, monkeypatch):
    """Хаб с временным хранилищем и потребителями во временных каталогах."""
    key = tmp_path / "master.key"
    key.write_text(crypto.generate_master_key(), encoding="utf-8")
    os.chmod(key, 0o600)
    master = crypto.load_master_key(key, require_root_owner=False)

    base = load_config(repo_root / "config" / "secret-hub.json")
    config = type(base)(
        source=base.source, store_dir=tmp_path / "store", socket_path=tmp_path / "hub.sock",
        control_group=base.control_group, provider_name=base.provider_name,
        verify=base.verify, portfolios=base.portfolios, public_form=base.public_form,
    )
    with Store(config.db_path, master) as store:
        yield Hub(config, master, store)


@pytest.fixture(autouse=True)
def offline_provider(monkeypatch):
    """Провайдер отвечает «принято», сети в тестах нет."""
    from factory.secret_hub import provider as provider_mod

    monkeypatch.setattr(provider_mod, "verify", lambda c, a, p, opener=None, portfolio="-":
                        provider_mod.VerifyResult(provider_mod.Outcome.ACCEPTED, 200,
                                                  "принято", True, c.url))


@pytest.fixture(autouse=True)
def no_real_apply(monkeypatch):
    """Применение к настоящим каталогам хоста в тестах не выполняется."""
    from factory.secret_hub import consumers as consumers_mod

    def fake_apply(portfolio, values, **kwargs):
        report = consumers_mod.ApplyReport(portfolio.id, kwargs.get("version"))
        for consumer in portfolio.consumers:
            report.results.append(consumers_mod.ConsumerResult(consumer.id, "applied"))
        return report

    monkeypatch.setattr(consumers_mod, "apply_portfolio", fake_apply)


def _configure(hub, portfolio: str) -> None:
    hub.store.put(portfolio,
                  {"api_token": crypto.Secret(TOKEN, "t"),
                   "publisher_id": crypto.Secret(PUBLISHER, "p")},
                  provider="cdnvideohub", verified_at="2026-08-25T00:00:00Z")


class TestImportComesFirst:
    def test_existing_files_are_imported_without_a_form(self, hub, monkeypatch, tmp_path):
        """Нашли файлы — форма не нужна."""
        from factory.secret_hub import migrate as migrate_mod

        monkeypatch.setattr(migrate_mod, "discover", lambda config, pid=None: [
            migrate_mod.Found(pid or "yami", "api_token", tmp_path / "a", True,
                              "0400", 0, 40, ()),
            migrate_mod.Found(pid or "yami", "publisher_id", tmp_path / "b", True,
                              "0400", 0, 12, ()),
        ])
        def fake_import(h, pid, archive=False):
            # Настоящий импорт кладёт значение в хранилище; подделка, которая
            # этого не делает, проверяла бы не тот путь: следующий шаг —
            # применение — законно отказал бы «не настроено».
            _configure(h, pid)
            state = h.store.state(pid)
            return {"imported": True, "version": state.active_version,
                    "fingerprint": state.fingerprint, "portfolio": pid}

        monkeypatch.setattr(migrate_mod, "import_existing", fake_import)

        report = bootstrap.import_and_apply(hub)

        yami = report.outcomes["yami"]
        assert yami.existing == bootstrap.VERIFIED
        assert yami.configured is True
        assert yami.applied is True
        assert yami.fingerprint

    def test_form_is_not_opened_when_nothing_is_missing(self, hub, monkeypatch):
        for portfolio in hub.config.portfolios:
            if portfolio.blocked_target is None:
                _configure(hub, portfolio.id)
        # amedia настраиваем тоже: иначе он останется «недостающим».
        _configure(hub, "amedia")

        opened: list[str] = []
        from factory.secret_hub import enroll as enroll_mod

        monkeypatch.setattr(enroll_mod, "start_session",
                            lambda *a, **k: opened.append("открыта"))

        report = bootstrap.run(hub)
        assert opened == [], "форма открылась, хотя всё настроено"
        assert report.form["opened"] is False

    def test_form_offers_only_missing_portfolios(self, hub, monkeypatch):
        _configure(hub, "yami")
        captured: dict = {}
        from factory.secret_hub import enroll as enroll_mod

        def fake_start(hub_arg, portfolios, **kwargs):
            captured["portfolios"] = list(portfolios)
            raise RuntimeError("stop")

        monkeypatch.setattr(enroll_mod, "start_session", fake_start)
        monkeypatch.setattr(os, "geteuid", lambda: 0)

        with pytest.raises(RuntimeError):
            bootstrap.run(hub)

        assert "yami" not in captured["portfolios"], "настроенное направление снова предлагают"
        assert "lords" in captured["portfolios"]


class TestBlockedTarget:
    def test_amedia_is_reported_blocked_not_missing(self, hub):
        report = bootstrap.import_and_apply(hub)
        amedia = report.outcomes["amedia"]
        assert amedia.status == "BLOCKED_TARGET"
        assert amedia.applied is False

    def test_blocked_portfolio_is_not_applied(self, hub, monkeypatch):
        from factory.secret_hub import consumers as consumers_mod

        touched: list[str] = []
        monkeypatch.setattr(consumers_mod, "apply_portfolio",
                            lambda p, v, **k: touched.append(p.id))
        bootstrap.import_and_apply(hub)
        assert "amedia" not in touched


class TestNoLeaks:
    def test_report_contains_no_values(self, hub):
        _configure(hub, "yami")
        report = bootstrap.import_and_apply(hub)
        serialized = str(report.as_dict())
        assert TOKEN not in serialized
        assert PUBLISHER not in serialized

    def test_summary_contains_no_values(self, hub):
        _configure(hub, "yami")
        report = bootstrap.import_and_apply(hub)
        serialized = str(bootstrap.summarise(report, hub))
        assert TOKEN not in serialized
        assert PUBLISHER not in serialized

    def test_summary_shows_only_allowed_fields(self, hub):
        _configure(hub, "yami")
        summary = bootstrap.summarise(bootstrap.import_and_apply(hub), hub)
        allowed = {"portfolio", "existing", "configured", "verified", "applied",
                   "fingerprint", "status", "detail"}
        for row in summary["portfolios"]:
            assert set(row) <= allowed, f"лишние поля: {set(row) - allowed}"


class TestAlreadyConfigured:
    def test_configured_portfolio_is_not_reimported(self, hub, monkeypatch):
        """Настроенное направление не перезаписывается новой версией."""
        _configure(hub, "yami")
        before = hub.store.state("yami").active_version

        from factory.secret_hub import migrate as migrate_mod

        called: list[str] = []
        monkeypatch.setattr(migrate_mod, "import_existing",
                            lambda h, pid, archive=False: called.append(pid))

        bootstrap.import_and_apply(hub)
        assert "yami" not in called
        assert hub.store.state("yami").active_version == before


class TestLiveVerificationGatesTheUrl:
    def test_url_is_not_shown_when_live_check_fails(self, hub, monkeypatch):
        """Провалилась живая проверка — ни адреса, ни кода оператор не увидит."""
        from factory.secret_hub import enroll as enroll_mod
        from factory.secret_hub import publish as publish_mod

        class FakeServer:
            def serve_forever(self, poll_interval=0.2):
                return

            def shutdown(self):
                return

            def server_close(self):
                return

        class FakeSession:
            marker = "МЕТКА"
            portfolio = None
            outcome = "pending"
            attempts = 0
            finished = False

            def close(self, *a):
                self.finished = True

        monkeypatch.setattr(os, "geteuid", lambda: 0)
        monkeypatch.setattr(enroll_mod, "start_session",
                            lambda h, p, **k: {"server": FakeServer(),
                                               "session": FakeSession(),
                                               "ttl_seconds": 900, "marker": "МЕТКА"})
        monkeypatch.setattr(publish_mod, "activate", lambda *a, **k: {"changed": True})
        monkeypatch.setattr(publish_mod, "deactivate", lambda: {"idle": True})

        failing = publish_mod.LiveVerification()
        failing.add("endpoint отвечает 200", False, "HTTP 502")
        monkeypatch.setattr(publish_mod, "verify_live", lambda *a, **k: failing)

        announced: list = []
        monkeypatch.setattr(enroll_mod, "_announce_to_root_console",
                            lambda *a, **k: announced.append("напечатано"))

        report = bootstrap.run(hub)

        assert report.form["opened"] is False
        assert announced == [], "код напечатан несмотря на провал живой проверки"
        assert "живая проверка не пройдена" in report.form["reason"]

    def test_form_is_taken_down_after_failed_verification(self, hub, monkeypatch):
        from factory.secret_hub import enroll as enroll_mod
        from factory.secret_hub import publish as publish_mod

        class FakeServer:
            def serve_forever(self, poll_interval=0.2):
                return

            def shutdown(self):
                return

            def server_close(self):
                return

        class FakeSession:
            marker = "МЕТКА"
            portfolio = None
            outcome = "pending"
            attempts = 0
            finished = False

            def close(self, *a):
                self.finished = True

        taken_down: list[str] = []
        monkeypatch.setattr(os, "geteuid", lambda: 0)
        monkeypatch.setattr(enroll_mod, "start_session",
                            lambda h, p, **k: {"server": FakeServer(),
                                               "session": FakeSession(),
                                               "ttl_seconds": 900, "marker": "МЕТКА"})
        monkeypatch.setattr(publish_mod, "activate", lambda *a, **k: {"changed": True})
        monkeypatch.setattr(publish_mod, "deactivate",
                            lambda: taken_down.append("снята") or {"idle": True})
        failing = publish_mod.LiveVerification()
        failing.add("сертификат соответствует домену", False, "чужой сертификат")
        monkeypatch.setattr(publish_mod, "verify_live", lambda *a, **k: failing)
        monkeypatch.setattr(enroll_mod, "_announce_to_root_console", lambda *a, **k: None)

        bootstrap.run(hub)
        assert taken_down == ["снята"], "endpoint не снят после провала проверки"


class TestRootRequirement:
    def test_form_is_refused_without_root(self, hub, monkeypatch):
        monkeypatch.setattr(os, "geteuid", lambda: 1000)
        report = bootstrap.run(hub)
        assert report.form["opened"] is False
        assert "root" in report.form["reason"]
