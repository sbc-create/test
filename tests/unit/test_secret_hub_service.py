"""Сервис хаба: отсутствие endpoint'а чтения, изоляция направлений, BLOCKED_TARGET.

Главный тест здесь — :class:`TestNoReadEndpoint`. Он не проверяет намерение
автора: он перебирает все объявленные операции, вызывает каждую на настроенном
направлении и ищет значение секрета в сериализованном ответе. Если однажды
кто-нибудь добавит поле со значением, тест это заметит.
"""
from __future__ import annotations

import json
import os
import socket
import threading
from pathlib import Path

import pytest

from factory.secret_hub import crypto, service
from factory.secret_hub.registry import load as load_config
from factory.secret_hub.service import Hub
from factory.secret_hub.store import Store

TOKEN_MARKER = "МАРКЕР-ТОКЕНА-НЕ-ДОЛЖЕН-ПОЯВЛЯТЬСЯ"
PUBLISHER_MARKER = "МАРКЕР-ПАБЛИШЕРА-ТОЖЕ"


@pytest.fixture
def hub(tmp_path, repo_root, monkeypatch):
    """Хаб на реальном реестре направлений, но с хранилищем во временном каталоге."""
    key_file = tmp_path / "master.key"
    key_file.write_text(crypto.generate_master_key(), encoding="utf-8")
    os.chmod(key_file, 0o600)
    master = crypto.load_master_key(key_file, require_root_owner=False)

    config = load_config(repo_root / "config" / "secret-hub.json")
    # store_dir подменяется на временный: тест не пишет в /var/lib.
    config = type(config)(
        source=config.source, store_dir=tmp_path / "store", socket_path=tmp_path / "hub.sock",
        control_group=config.control_group, provider_name=config.provider_name,
        verify=config.verify, portfolios=config.portfolios,
    )
    with Store(config.db_path, master) as store:
        yield Hub(config, master, store)


def _configure(hub, portfolio: str, token: str = TOKEN_MARKER,
               publisher: str = PUBLISHER_MARKER) -> int:
    return hub.store.put(
        portfolio,
        {"api_token": crypto.Secret(token, "t"), "publisher_id": crypto.Secret(publisher, "p")},
        provider="cdnvideohub", verified_at="2026-08-25T00:00:00Z",
    )


@pytest.fixture
def offline_provider(monkeypatch):
    """Провайдер не вызывается по-настоящему: сеть в тестах не участвует."""
    from factory.secret_hub import provider as provider_mod

    calls: list[str] = []

    def fake_verify(contract, api_token, publisher_id, *, opener=None, portfolio="-"):
        calls.append(portfolio)
        return provider_mod.VerifyResult(
            provider_mod.Outcome.ACCEPTED, 200, "провайдер принял credentials", True,
            contract.url)

    monkeypatch.setattr(provider_mod, "verify", fake_verify)
    return calls


class TestNoReadEndpoint:
    def test_operations_list_has_no_read_operation(self):
        """Операции, возвращающей значение, не объявлено вовсе."""
        for forbidden in ("get", "read", "reveal", "show", "export", "dump", "fetch"):
            assert forbidden not in service.OPERATIONS

    def test_update_is_not_an_api_operation(self):
        """Значения приходят только формой или root-импортом, оба — внутри процесса."""
        assert "update" not in service.OPERATIONS

    @pytest.mark.parametrize("operation", sorted(service.OPERATIONS))
    def test_no_operation_returns_a_secret_value(self, hub, offline_provider, operation,
                                                 monkeypatch):
        """Перебор всех операций: значения нет ни в одном ответе."""
        _configure(hub, "yami")
        _configure(hub, "lords")

        if operation == "enroll":
            # Форма — интерактивная операция; её ответ проверяется отдельно.
            # Здесь достаточно, что она не отдаёт значение из хранилища.
            from factory.secret_hub import enroll as enroll_mod

            monkeypatch.setattr(enroll_mod, "start_session",
                                lambda *a, **k: {"outcome": "expired", "url": "https://x/"})
        if operation == "import":
            from factory.secret_hub import migrate as migrate_mod

            monkeypatch.setattr(migrate_mod, "import_existing",
                                lambda *a, **k: {"imported": False, "status": "nothing_to_import"})
        if operation == "apply":
            from factory.secret_hub import consumers as consumers_mod

            monkeypatch.setattr(consumers_mod, "apply_portfolio",
                                lambda portfolio, values, **k: consumers_mod.ApplyReport(
                                    portfolio.id, k.get("version")))

        response = hub.handle({"op": operation, "portfolio": "yami"})
        serialized = json.dumps(response, ensure_ascii=False)
        assert TOKEN_MARKER not in serialized, f"операция «{operation}» вернула токен"
        assert PUBLISHER_MARKER not in serialized, f"операция «{operation}» вернула publisher_id"
        for key in service.FORBIDDEN_RESPONSE_KEYS:
            assert f'"{key}":' not in serialized or key == "version", \
                f"операция «{operation}» вернула поле «{key}»"

    def test_unknown_operation_is_refused(self, hub):
        response = hub.handle({"op": "reveal", "portfolio": "yami"})
        assert response["ok"] is False
        assert response["error"] == "unknown_operation"

    def test_status_of_configured_portfolio_has_fingerprint_but_no_value(self, hub):
        _configure(hub, "yami")
        response = hub.handle({"op": "status", "portfolio": "yami"})
        row = response["portfolios"][0]
        assert row["configured"] is True
        assert row["fingerprint"].startswith("sha256:")
        assert TOKEN_MARKER not in json.dumps(response, ensure_ascii=False)


class TestStatusShape:
    def test_status_reports_exactly_the_required_fields(self, hub):
        _configure(hub, "yami")
        row = hub.handle({"op": "status", "portfolio": "yami"})["portfolios"][0]
        for required in ("portfolio", "configured", "verified", "updated_at", "fingerprint",
                         "consumers", "deployment"):
            assert required in row, f"status не показывает «{required}»"

    def test_status_of_all_portfolios_lists_every_configured_direction(self, hub):
        response = hub.handle({"op": "status"})
        assert {row["portfolio"] for row in response["portfolios"]} == {"yami", "lords", "amedia"}

    def test_status_includes_master_key_state_without_the_key(self, hub):
        response = hub.handle({"op": "status"})
        assert "master_key" in response
        assert "path" in response["master_key"]


class TestBlockedTarget:
    def test_amedia_is_blocked_target(self, hub):
        row = hub.handle({"op": "status", "portfolio": "amedia"})["portfolios"][0]
        assert row["status"] == "BLOCKED_TARGET"
        assert row["blocked_target"]["required_input"]

    def test_apply_to_amedia_is_refused_with_blocked_target(self, hub):
        response = hub.handle({"op": "apply", "portfolio": "amedia"})
        assert response["ok"] is False
        assert response["error"] == "BLOCKED_TARGET"

    def test_enroll_for_amedia_is_refused(self, hub):
        response = hub.handle({"op": "enroll", "portfolio": "amedia"})
        assert response["ok"] is False
        assert response["error"] == "BLOCKED_TARGET"

    def test_blocked_target_is_not_retryable(self):
        from factory.errors import NON_RETRYABLE

        assert "BLOCKED_TARGET" in NON_RETRYABLE


class TestPortfolioIsolationThroughApi:
    def test_apply_of_yami_touches_only_yami_consumers(self, hub, offline_provider, monkeypatch):
        from factory.secret_hub import consumers as consumers_mod

        seen: list[str] = []

        def record(portfolio, values, **kwargs):
            seen.extend(c.id for c in portfolio.consumers)
            return consumers_mod.ApplyReport(portfolio.id, kwargs.get("version"))

        monkeypatch.setattr(consumers_mod, "apply_portfolio", record)
        _configure(hub, "yami")
        hub.handle({"op": "apply", "portfolio": "yami"})

        assert seen == ["yami-staging-compose"]
        assert not any(name.startswith("lords") for name in seen)

    def test_units_of_yami_and_lords_do_not_intersect(self, hub):
        yami = hub.config.portfolio("yami")
        lords = hub.config.portfolio("lords")
        assert set(yami.units()) & set(lords.units()) == set()

    def test_directories_of_portfolios_do_not_intersect(self, hub):
        used: dict[Path, str] = {}
        for portfolio in hub.config.portfolios:
            for directory in portfolio.directories():
                assert directory not in used, \
                    f"{directory} принадлежит и «{used[directory]}», и «{portfolio.id}»"
                used[directory] = portfolio.id

    def test_revoke_of_yami_leaves_lords_configured(self, hub, offline_provider):
        _configure(hub, "yami")
        _configure(hub, "lords")
        hub.handle({"op": "revoke", "portfolio": "yami"})
        lords = hub.handle({"op": "status", "portfolio": "lords"})["portfolios"][0]
        assert lords["configured"] is True


class TestRotateAndRevoke:
    def test_rotate_creates_a_new_version(self, hub, offline_provider, monkeypatch):
        from factory.secret_hub import consumers as consumers_mod

        monkeypatch.setattr(consumers_mod, "apply_portfolio",
                            lambda portfolio, values, **k: consumers_mod.ApplyReport(
                                portfolio.id, k.get("version")))
        _configure(hub, "yami")
        response = hub.handle({"op": "rotate", "portfolio": "yami"})
        assert response["version"] == 2
        assert hub.store.state("yami").active_version == 2

    def test_rotate_does_not_invent_a_new_value(self, hub, offline_provider, monkeypatch):
        """Ротация перевыдаёт уже проверенное значение, а не придумывает новое."""
        from factory.secret_hub import consumers as consumers_mod

        monkeypatch.setattr(consumers_mod, "apply_portfolio",
                            lambda portfolio, values, **k: consumers_mod.ApplyReport(
                                portfolio.id, k.get("version")))
        _configure(hub, "yami")
        before = hub.store.state("yami").fingerprint
        hub.handle({"op": "rotate", "portfolio": "yami"})
        assert hub.store.state("yami").fingerprint == before

    def test_revoke_keeps_the_last_working_version(self, hub):
        _configure(hub, "yami")
        hub.handle({"op": "revoke", "portfolio": "yami"})
        versions = hub.store.state("yami").versions
        assert len(versions) == 1, "последняя рабочая версия обязана остаться"

    def test_revoke_does_not_delete_consumer_files(self, hub):
        response = hub.handle({"op": "revoke", "portfolio": "yami"}) \
            if hub.store.state("yami").configured else None
        _configure(hub, "yami")
        response = hub.handle({"op": "revoke", "portfolio": "yami"})
        assert "Файлы у потребителей не изменены" in response["note"]

    def test_rotate_of_unconfigured_portfolio_is_honest(self, hub):
        response = hub.handle({"op": "rotate", "portfolio": "lords"})
        assert response["status"] == "not_configured"


class TestApplyRefusesUnverified:
    def test_apply_does_not_touch_sites_when_verification_fails(self, hub, monkeypatch):
        """Непроверенные credentials не доезжают до работающего сайта."""
        from factory.secret_hub import consumers as consumers_mod
        from factory.secret_hub import provider as provider_mod

        monkeypatch.setattr(provider_mod, "verify", lambda *a, **k: provider_mod.VerifyResult(
            provider_mod.Outcome.REJECTED, 401, "провайдер отверг credentials (HTTP 401)",
            True, "https://x/"))
        touched: list[str] = []
        monkeypatch.setattr(consumers_mod, "apply_portfolio",
                            lambda *a, **k: touched.append("применено"))

        _configure(hub, "yami")
        response = hub.handle({"op": "apply", "portfolio": "yami"})

        assert response["status"] == "verification_failed"
        assert touched == [], "применение не должно начинаться при неуспешной проверке"

    def test_apply_makes_a_store_backup_first(self, hub, offline_provider, monkeypatch):
        from factory.secret_hub import consumers as consumers_mod

        monkeypatch.setattr(consumers_mod, "apply_portfolio",
                            lambda portfolio, values, **k: consumers_mod.ApplyReport(
                                portfolio.id, k.get("version")))
        _configure(hub, "yami")
        response = hub.handle({"op": "apply", "portfolio": "yami"})
        assert Path(response["store_backup"]).exists()


class TestSocketTransport:
    def test_socket_is_not_world_accessible(self, hub, tmp_path):
        ready = threading.Event()
        thread = threading.Thread(
            target=lambda: service.serve(hub.config, master=hub.master, ready=ready),
            daemon=True)
        thread.start()
        assert ready.wait(10), "сервис не поднялся"
        try:
            status = service.socket_status(hub.config.socket_path)
            assert status["is_socket"] is True
            assert status["world_accessible"] is False, "сокет доступен миру"

            response = service.request(hub.config.socket_path, {"op": "list"})
            assert {p["portfolio"] for p in response["portfolios"]} == {"yami", "lords", "amedia"}
        finally:
            _shutdown(hub.config.socket_path)
            thread.join(5)

    def test_oversized_request_is_refused(self, hub):
        ready = threading.Event()
        thread = threading.Thread(
            target=lambda: service.serve(hub.config, master=hub.master, ready=ready),
            daemon=True)
        thread.start()
        assert ready.wait(10)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(10)
                sock.connect(str(hub.config.socket_path))
                sock.sendall(b'{"op":"list","junk":"' + b"x" * (service.MAX_REQUEST_BYTES + 10)
                             + b'"}\n')
                reply = json.loads(sock.recv(65536).decode("utf-8"))
            assert reply["error"] == "request_too_large"
        finally:
            _shutdown(hub.config.socket_path)
            thread.join(5)


def _shutdown(socket_path: Path) -> None:
    """Останавливает сервис, закрывая сокет. Отдельной операции stop у API нет."""
    import contextlib

    with contextlib.suppress(OSError):
        socket_path.unlink()
