"""Панель целиком: HTTP, сессии, CSRF, CSP, rate limit, сохранение credentials.

Тесты поднимают настоящий сервер панели и настоящий хаб на unix-сокете и ходят
по HTTP. Провайдер CDNVideoHub подменён — сети в тестах нет; всё остальное
работает как в бою, включая шифрование и разделение процессов на уровне API.
"""
from __future__ import annotations

import http.client
import json
import os
import threading

import pytest

from factory.secret_hub import crypto, service
from factory.secret_hub.panel import SESSION_COOKIE
from factory.secret_hub.panel.server import PanelConfig, build_server
from factory.secret_hub.panel.store import PanelStore
from factory.secret_hub.panel.ui import MARKER
from factory.secret_hub.registry import load as load_config
from factory.secret_hub.service import Hub
from factory.secret_hub.store import Store
from tests.unit.test_secret_hub_panel_auth import SoftAuthenticator

TOKEN = "МАРКЕР-ТОКЕНА-ПАНЕЛИ"
PUBLISHER = "publisher-panel"
PATH = "/__factory-secrets"
SERVER_NAME = "yummyani.site"


@pytest.fixture(autouse=True)
def offline_provider(monkeypatch):
    from factory.secret_hub import provider as provider_mod

    monkeypatch.setattr(
        provider_mod, "verify",
        lambda c, a, p, opener=None, portfolio="-": provider_mod.VerifyResult(
            provider_mod.Outcome.ACCEPTED, 200, "принято", True, c.url))


@pytest.fixture(autouse=True)
def no_real_apply(monkeypatch):
    from factory.secret_hub import consumers as consumers_mod

    def fake_apply(portfolio, values, **kwargs):
        report = consumers_mod.ApplyReport(portfolio.id, kwargs.get("version"))
        for consumer in portfolio.consumers:
            report.results.append(consumers_mod.ConsumerResult(consumer.id, "applied"))
        return report

    monkeypatch.setattr(consumers_mod, "apply_portfolio", fake_apply)


class Stand:
    """Хаб на сокете + панель на петле. Как в бою, но во временном каталоге."""

    def __init__(self, tmp_path, repo_root):
        key = tmp_path / "master.key"
        key.write_text(crypto.generate_master_key(), encoding="utf-8")
        os.chmod(key, 0o600)
        master = crypto.load_master_key(key, require_root_owner=False)

        base = load_config(repo_root / "config" / "secret-hub.json")
        # Учётная запись панели на этом хосте — та, от которой идёт тест: в бою
        # это `sfpanel`, а в тестовой среде такого пользователя нет. Хаб
        # сверяет uid пира сокета, и подменить его нельзя — можно только
        # честно назвать ту учётную запись, которой позволено писать.
        import getpass

        form = base.public_form
        self.panel_user = getpass.getuser()
        panel_form = type(form)(
            server_name=form.server_name, vhost=form.vhost, path=form.path,
            loopback_port=form.loopback_port, note=form.note,
            panel_user=self.panel_user, panel_state_dir=tmp_path / "panel",
        )
        self.hub_config = type(base)(
            source=base.source, store_dir=tmp_path / "hub",
            socket_path=tmp_path / "hub.sock", control_group=base.control_group,
            provider_name=base.provider_name, verify=base.verify,
            portfolios=base.portfolios, public_form=panel_form,
        )
        self.store = Store(self.hub_config.db_path, master)
        self.hub = Hub(self.hub_config, master, self.store)

        ready = threading.Event()
        self.hub_thread = threading.Thread(
            target=lambda: service.serve(self.hub_config, master=master, ready=ready),
            daemon=True)
        self.hub_thread.start()
        assert ready.wait(10), "хаб не поднялся"

        self.panel_store = PanelStore(tmp_path / "panel" / "panel.sqlite3")
        self.config = PanelConfig(
            base_path=PATH, server_name=SERVER_NAME,
            socket_path=self.hub_config.socket_path,
            state_dir=tmp_path / "panel", host="127.0.0.1", port=0,
        )
        self.server = build_server(self.config, self.panel_store)
        self.port = self.server.server_address[1]
        self.panel_thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
        self.panel_thread.start()

        self.cookie = ""
        self.csrf = ""

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.panel_store.close()
        with __import__("contextlib").suppress(OSError):
            self.hub_config.socket_path.unlink()

    # --- HTTP ------------------------------------------------------------
    def _conn(self):
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)

    def get(self, path: str = PATH) -> tuple[int, str, dict]:
        conn = self._conn()
        try:
            headers = {"Cookie": self.cookie} if self.cookie else {}
            conn.request("GET", path, headers=headers)
            r = conn.getresponse()
            body = r.read().decode("utf-8", "replace")
            head = dict(r.getheaders())
            self._absorb(r)
            if 'name="csrf" content="' in body:
                self.csrf = body.split('name="csrf" content="')[1].split('"')[0]
            return r.status, body, head
        finally:
            conn.close()

    def post(self, path: str, payload: dict, *, csrf: str | None = None,
             raw: bytes | None = None) -> tuple[int, dict]:
        conn = self._conn()
        try:
            body = raw if raw is not None else json.dumps(payload).encode()
            headers = {"Content-Type": "application/json",
                       "X-CSRF-Token": self.csrf if csrf is None else csrf}
            if self.cookie:
                headers["Cookie"] = self.cookie
            conn.request("POST", PATH + path, body, headers)
            r = conn.getresponse()
            text = r.read().decode("utf-8", "replace")
            self._absorb(r)
            try:
                return r.status, json.loads(text)
            except json.JSONDecodeError:
                return r.status, {"raw": text}
        finally:
            conn.close()

    def _absorb(self, response) -> None:
        for key, value in response.getheaders():
            if key.lower() == "set-cookie" and value.startswith(SESSION_COOKIE + "="):
                self.cookie = value.split(";")[0]

    # --- сценарии --------------------------------------------------------
    def enroll_and_login(self) -> SoftAuthenticator:
        """Первичная регистрация passkey по коду + вход."""
        code = self.panel_store.create_enrollment(ttl_seconds=900)
        self.get()
        authenticator = SoftAuthenticator(rp_id=SERVER_NAME,
                                          origin=f"https://{SERVER_NAME}")
        status, begin = self.post("/api/register/begin", {"enrollment_code": code})
        assert status == 200, begin
        credential = authenticator.create(begin["publicKey"]["challenge"])
        status, done = self.post("/api/register/finish",
                                 {"challenge_id": begin["challenge_id"],
                                  "credential": credential})
        assert status == 200, done
        self.recovery_codes = done.get("recovery_codes") or []
        self.get()
        return authenticator


@pytest.fixture
def stand(tmp_path, repo_root):
    built = Stand(tmp_path, repo_root)
    try:
        yield built
    finally:
        built.stop()


class TestGate:
    def test_anonymous_sees_login_page_not_panel(self, stand):
        status, body, _ = stand.get()
        assert status == 200
        assert MARKER in body
        assert "Вход только по ключу устройства" in body
        assert "CDNVideoHub API Token" not in body, "панель показана без входа"

    def test_no_basic_auth_challenge_is_ever_sent(self, stand):
        for path in (PATH, PATH + "/app.js", PATH + "/nope"):
            _, _, headers = stand.get(path)
            assert "WWW-Authenticate" not in headers

    def test_security_headers_are_present(self, stand):
        _, _, headers = stand.get()
        csp = headers.get("Content-Security-Policy", "")
        assert "default-src 'none'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert headers.get("X-Frame-Options") == "DENY"
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert "noindex" in headers.get("X-Robots-Tag", "")
        assert "no-store" in headers.get("Cache-Control", "")

    def test_session_cookie_is_secure_httponly_samesite(self, stand):
        conn = http.client.HTTPConnection("127.0.0.1", stand.port, timeout=10)
        conn.request("GET", PATH)
        response = conn.getresponse()
        response.read()
        cookies = [v for k, v in response.getheaders() if k.lower() == "set-cookie"]
        conn.close()
        assert cookies, "сессионная cookie не выдана"
        cookie = cookies[0]
        assert cookie.startswith("__Secure-")
        assert "Secure" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=Strict" in cookie
        assert f"Path={PATH}" in cookie, "cookie уходила бы на страницы самого сайта"

    def test_unknown_path_is_404(self, stand):
        assert stand.get(PATH + "/secret")[0] == 404
        assert stand.get("/")[0] == 404

    def test_query_string_is_refused(self, stand):
        assert stand.get(PATH + "?x=1")[0] == 404

    def test_script_is_served_separately_without_inline(self, stand):
        status, body, headers = stand.get(PATH + "/app.js")
        assert status == 200
        assert "javascript" in headers.get("Content-Type", "")
        assert "const BASE = " in body
        _, page, _ = stand.get()
        assert "<script>" not in page


class TestRegistrationAndLogin:
    def test_enrollment_code_lets_owner_register_and_enter(self, stand):
        stand.enroll_and_login()
        _, body, _ = stand.get()
        assert "CDNVideoHub API Token" in body, "панель не открылась после регистрации"
        assert "Yami" in body or "yami" in body

    def test_recovery_codes_are_shown_once_at_first_registration(self, stand):
        stand.enroll_and_login()
        assert len(stand.recovery_codes) == 10
        # Повторный вход кодов больше не показывает.
        assert stand.panel_store.recovery_status()["total"] == 10

    def test_registration_without_code_or_session_is_refused(self, stand):
        stand.get()
        status, body = stand.post("/api/register/begin", {})
        assert status == 400
        assert "код восстановления" in body["error"]

    def test_login_with_registered_passkey(self, stand):
        authenticator = stand.enroll_and_login()
        stand.cookie = ""
        stand.get()
        status, begin = stand.post("/api/login/begin", {})
        assert status == 200
        credential = authenticator.get(begin["publicKey"]["challenge"])
        status, _ = stand.post("/api/login/finish",
                               {"challenge_id": begin["challenge_id"],
                                "credential": credential})
        assert status == 200
        _, body, _ = stand.get()
        assert "CDNVideoHub API Token" in body

    def test_recovery_code_allows_adding_a_key(self, stand):
        stand.enroll_and_login()
        code = stand.recovery_codes[0]
        stand.cookie = ""
        stand.get()
        second = SoftAuthenticator(rp_id=SERVER_NAME, origin=f"https://{SERVER_NAME}")
        status, begin = stand.post("/api/register/begin", {"recovery_code": code})
        assert status == 200, begin
        credential = second.create(begin["publicKey"]["challenge"])
        status, _ = stand.post("/api/register/finish",
                               {"challenge_id": begin["challenge_id"],
                                "credential": credential})
        assert status == 200
        assert len(stand.panel_store.passkeys()) == 2

    def test_used_recovery_code_does_not_work_twice(self, stand):
        stand.enroll_and_login()
        code = stand.recovery_codes[0]
        stand.cookie = ""
        stand.get()
        stand.post("/api/register/begin", {"recovery_code": code})
        stand.cookie = ""
        stand.get()
        status, body = stand.post("/api/register/begin", {"recovery_code": code})
        assert status == 400
        assert "использован" in body["error"] or "неверен" in body["error"]


class TestCsrf:
    def test_post_without_csrf_is_refused(self, stand):
        stand.enroll_and_login()
        status, body = stand.post("/api/portfolio/apply", {"portfolio": "yami"}, csrf="")
        assert status == 403
        assert "устарела" in body["error"]

    def test_post_with_wrong_csrf_is_refused(self, stand):
        stand.enroll_and_login()
        # Латиница: HTTP-заголовок кодируется latin-1, и кириллица в нём
        # падает у клиента, не доходя до сервера. Проверяем именно отказ
        # сервера, а не ограничение http.client.
        status, _ = stand.post("/api/portfolio/apply", {"portfolio": "yami"},
                               csrf="someone-elses-token")
        assert status == 403

    def test_post_without_session_is_refused(self, stand):
        stand.get()
        saved = stand.cookie
        stand.cookie = ""
        status, _ = stand.post("/api/login/begin", {})
        assert status == 401
        stand.cookie = saved


class TestBodyLimit:
    def test_oversized_body_is_refused(self, stand):
        stand.enroll_and_login()
        from factory.secret_hub.panel import MAX_BODY_BYTES

        payload = json.dumps({"portfolio": "yami", "api_token": "x" * MAX_BODY_BYTES,
                              "publisher_id": "p"}).encode()
        status, _ = stand.post("/api/portfolio/save", {}, raw=payload)
        assert status == 413


class TestSavingCredentials:
    def test_save_stores_and_applies(self, stand):
        stand.enroll_and_login()
        status, body = stand.post("/api/portfolio/save", {
            "portfolio": "yami", "api_token": TOKEN, "publisher_id": PUBLISHER,
            "request_id": "req-1", "apply": True})
        assert status == 200, body
        assert body["ok"] is True
        assert "применено" in body["message"]
        assert stand.store.state("yami").configured is True

    def test_saved_value_is_never_returned(self, stand):
        stand.enroll_and_login()
        _, body = stand.post("/api/portfolio/save", {
            "portfolio": "yami", "api_token": TOKEN, "publisher_id": PUBLISHER,
            "request_id": "req-2"})
        assert TOKEN not in json.dumps(body, ensure_ascii=False)
        _, page, _ = stand.get()
        assert TOKEN not in page, "значение попало в HTML панели"
        assert PUBLISHER not in page

    def test_fingerprint_is_shown_but_value_is_not(self, stand):
        stand.enroll_and_login()
        stand.post("/api/portfolio/save", {
            "portfolio": "yami", "api_token": TOKEN, "publisher_id": PUBLISHER,
            "request_id": "req-3"})
        _, page, _ = stand.get()
        fingerprint = stand.store.state("yami").fingerprint
        assert fingerprint in page
        assert TOKEN not in page

    def test_repeated_request_id_is_idempotent(self, stand):
        """Двойной клик или обновление страницы не создают вторую версию."""
        stand.enroll_and_login()
        first = stand.post("/api/portfolio/save", {
            "portfolio": "yami", "api_token": TOKEN, "publisher_id": PUBLISHER,
            "request_id": "same"})
        version_after_first = stand.store.state("yami").active_version
        second = stand.post("/api/portfolio/save", {
            "portfolio": "yami", "api_token": TOKEN, "publisher_id": PUBLISHER,
            "request_id": "same"})
        assert first[1] == second[1]
        assert stand.store.state("yami").active_version == version_after_first

    def test_replacing_creates_a_new_version_and_keeps_the_old(self, stand):
        stand.enroll_and_login()
        stand.post("/api/portfolio/save", {"portfolio": "yami", "api_token": "первый",
                                           "publisher_id": PUBLISHER, "request_id": "a"})
        first_fingerprint = stand.store.state("yami").fingerprint
        stand.post("/api/portfolio/save", {"portfolio": "yami", "api_token": "второй",
                                           "publisher_id": PUBLISHER, "request_id": "b"})
        state = stand.store.state("yami")
        assert state.active_version == 2
        assert state.fingerprint != first_fingerprint
        assert len(state.versions) == 2, "предыдущая версия обязана остаться для отката"

    def test_rollback_returns_the_previous_value(self, stand):
        stand.enroll_and_login()
        stand.post("/api/portfolio/save", {"portfolio": "yami", "api_token": "старый",
                                           "publisher_id": PUBLISHER, "request_id": "a"})
        stand.post("/api/portfolio/save", {"portfolio": "yami", "api_token": "новый",
                                           "publisher_id": PUBLISHER, "request_id": "b"})
        stand.store.rollback("yami")
        assert stand.store.reveal_for_apply("yami")["api_token"].reveal() == "старый"

    def test_rejected_token_is_not_stored(self, stand, monkeypatch):
        from factory.secret_hub import provider as provider_mod

        monkeypatch.setattr(provider_mod, "verify",
                            lambda c, a, p, opener=None, portfolio="-":
                            provider_mod.VerifyResult(provider_mod.Outcome.REJECTED, 401,
                                                      "провайдер отверг credentials", True,
                                                      c.url))
        stand.enroll_and_login()
        status, body = stand.post("/api/portfolio/save", {
            "portfolio": "yami", "api_token": "плохой", "publisher_id": PUBLISHER,
            "request_id": "bad"})
        assert status == 200
        assert body["ok"] is False
        assert "не принял" in body["message"]
        assert stand.store.state("yami").configured is False

    def test_empty_fields_are_refused(self, stand):
        stand.enroll_and_login()
        status, body = stand.post("/api/portfolio/save", {
            "portfolio": "yami", "api_token": "", "publisher_id": PUBLISHER,
            "request_id": "empty"})
        assert body["ok"] is False
        assert stand.store.state("yami").configured is False

    def test_saving_requires_login(self, stand):
        stand.get()
        status, body = stand.post("/api/portfolio/save", {
            "portfolio": "yami", "api_token": TOKEN, "publisher_id": PUBLISHER})
        assert status == 400
        assert "вход" in body["error"].lower()
        assert stand.store.state("yami").configured is False


class TestAmedia:
    def test_amedia_can_be_configured_but_not_applied(self, stand):
        """Задание разрешает сохранить Amedia заранее: configured, not applied."""
        stand.enroll_and_login()
        status, body = stand.post("/api/portfolio/save", {
            "portfolio": "amedia", "api_token": TOKEN, "publisher_id": PUBLISHER,
            "request_id": "am", "apply": True})
        assert status == 200, body
        assert body["ok"] is True
        assert "применять пока некуда" in body["message"].lower()
        assert stand.store.state("amedia").configured is True


class TestPortfolioIsolation:
    def test_saving_yami_does_not_touch_lords(self, stand):
        stand.enroll_and_login()
        stand.post("/api/portfolio/save", {"portfolio": "lords", "api_token": "lords-token",
                                           "publisher_id": PUBLISHER, "request_id": "l"})
        lords_before = stand.store.state("lords").as_dict()
        stand.post("/api/portfolio/save", {"portfolio": "yami", "api_token": "yami-token",
                                           "publisher_id": PUBLISHER, "request_id": "y"})
        assert stand.store.state("lords").as_dict() == lords_before
        assert stand.store.reveal_for_apply("lords")["api_token"].reveal() == "lords-token"
        assert stand.store.reveal_for_apply("yami")["api_token"].reveal() == "yami-token"

    def test_applying_yami_restarts_only_yami_units(self, stand, monkeypatch):
        from factory.secret_hub import consumers as consumers_mod

        touched: list[str] = []

        def record(portfolio, values, **kwargs):
            touched.append(portfolio.id)
            report = consumers_mod.ApplyReport(portfolio.id, kwargs.get("version"))
            for consumer in portfolio.consumers:
                report.results.append(consumers_mod.ConsumerResult(consumer.id, "applied"))
            return report

        monkeypatch.setattr(consumers_mod, "apply_portfolio", record)
        stand.enroll_and_login()
        stand.post("/api/portfolio/save", {"portfolio": "yami", "api_token": TOKEN,
                                           "publisher_id": PUBLISHER, "request_id": "y"})
        assert touched == ["yami"]


class TestNoSecretsAnywhere:
    def test_value_is_not_in_the_script(self, stand):
        stand.enroll_and_login()
        stand.post("/api/portfolio/save", {"portfolio": "yami", "api_token": TOKEN,
                                           "publisher_id": PUBLISHER, "request_id": "s"})
        _, script, _ = stand.get(PATH + "/app.js")
        assert TOKEN not in script
        assert PUBLISHER not in script

    def test_value_is_not_in_the_panel_database(self, stand):
        stand.enroll_and_login()
        stand.post("/api/portfolio/save", {"portfolio": "yami", "api_token": TOKEN,
                                           "publisher_id": PUBLISHER, "request_id": "d"})
        blob = stand.panel_store.db_path.read_bytes()
        for suffix in ("-wal", "-shm"):
            extra = stand.panel_store.db_path.with_name(
                stand.panel_store.db_path.name + suffix)
            if extra.exists():
                blob += extra.read_bytes()
        assert TOKEN.encode() not in blob, "значение осело в базе панели"
        assert PUBLISHER.encode() not in blob

    def test_hub_api_never_returns_the_value(self, stand):
        stand.enroll_and_login()
        stand.post("/api/portfolio/save", {"portfolio": "yami", "api_token": TOKEN,
                                           "publisher_id": PUBLISHER, "request_id": "h"})
        for op in ("list", "status", "verify"):
            payload = {"op": op} if op == "list" else {"op": op, "portfolio": "yami"}
            reply = service.request(stand.hub_config.socket_path, payload)
            assert TOKEN not in json.dumps(reply, ensure_ascii=False)

    def test_store_operation_returns_no_value(self, stand):
        reply = service.request(stand.hub_config.socket_path, {
            "op": "store", "portfolio": "yami", "api_token": TOKEN,
            "publisher_id": PUBLISHER})
        serialized = json.dumps(reply, ensure_ascii=False)
        assert TOKEN not in serialized
        assert PUBLISHER not in serialized


class TestRateLimit:
    def test_save_is_rate_limited(self, stand):
        from factory.secret_hub.panel.server import SAVE_MAX_ATTEMPTS

        stand.enroll_and_login()
        for index in range(SAVE_MAX_ATTEMPTS):
            stand.post("/api/portfolio/save", {
                "portfolio": "yami", "api_token": TOKEN, "publisher_id": PUBLISHER,
                "request_id": f"rl-{index}"})
        status, body = stand.post("/api/portfolio/save", {
            "portfolio": "yami", "api_token": TOKEN, "publisher_id": PUBLISHER,
            "request_id": "rl-over"})
        assert status == 429
        assert "часто" in body["error"]


class TestWriteGate:
    """Право писать credentials проверяется по uid пира, а не по группе."""

    def test_non_panel_uid_cannot_store(self, stand, monkeypatch):
        """Учётная запись агента состоит в группе управления — и всё равно не пишет.

        Проверяется подменой ожидаемого uid панели на заведомо другой: сам uid
        пира приходит от ядра и подделке не поддаётся, поэтому «чужим» в тесте
        делается ожидание, а не факт.
        """
        from factory.secret_hub import service as service_mod

        monkeypatch.setattr(service_mod, "_panel_uid", lambda user: 999_999)
        reply = service_mod.request(stand.hub_config.socket_path, {
            "op": "store", "portfolio": "yami", "api_token": TOKEN,
            "publisher_id": PUBLISHER})
        assert reply["ok"] is False
        assert reply["error"] == "BLOCKED_AUTHORIZATION"
        assert "только процессу панели" in reply["reason"]
        assert stand.store.state("yami").configured is False

    def test_read_operations_still_work_for_others(self, stand, monkeypatch):
        """Запрет касается записи, а не чтения состояния."""
        from factory.secret_hub import service as service_mod

        monkeypatch.setattr(service_mod, "_panel_uid", lambda user: 999_999)
        reply = service_mod.request(stand.hub_config.socket_path, {"op": "status"})
        assert reply.get("ok") is not False
        assert "portfolios" in reply

    def test_store_is_the_only_panel_only_operation(self):
        from factory.secret_hub import service as service_mod

        assert {"store"} == service_mod.PANEL_ONLY_OPERATIONS

    def test_no_read_operation_exists_at_all(self):
        from factory.secret_hub import service as service_mod

        for forbidden in ("get", "read", "reveal", "show", "export", "dump"):
            assert forbidden not in service_mod.OPERATIONS
