"""Одноразовая форма ввода: TTL, CSRF, пять попыток, POST-only, 404 после закрытия.

Тесты поднимают настоящий HTTPS-сервер на эфемерном порту и разговаривают с ним
по сети. Проверять форму подделкой её внутренних вызовов бессмысленно: смысл
формы — в том, что она отвечает внешнему клиенту.
"""
from __future__ import annotations

import http.client
import json
import ssl
import threading
import time
import urllib.parse

import pytest

from factory.secret_hub import enroll


class FakeHub:
    """Хаб, который записывает то, что ему дали, и помнит, о чём его просили.

    Провайдер здесь не участвует: живой запрос проверяется в тестах провайдера,
    а тут проверяется поведение формы.
    """

    def __init__(self, *, accept: bool = True) -> None:
        self.accept = accept
        self.calls: list[tuple[str, str, str]] = []

    def store_verified(self, portfolio: str, values: dict) -> dict:
        self.calls.append((portfolio, values["api_token"].reveal(),
                           values["publisher_id"].reveal()))
        if not self.accept:
            return {"stored": False, "reason": "провайдер отверг credentials (HTTP 401)"}
        return {"stored": True, "version": 1, "fingerprint": "sha256:тест"}


class Form:
    """Запущенная форма и клиент к ней."""

    def __init__(self, hub, *, ttl_seconds: int = 900, base_path: str = "/",
                 tls: bool = True, portfolios=("yami",)) -> None:
        self.captured: dict = {}
        self.base_path = base_path
        self.tls = tls
        self.portfolios = tuple(portfolios)

        def announce(session, url, port, fingerprint, ttl):
            # Код доступа существует только здесь: в ответе операции его нет.
            self.captured = {"code": session.code, "csrf": session.csrf,
                             "port": port, "fingerprint": fingerprint,
                             "marker": session.marker, "url": url}

        started = threading.Event()
        self.result: dict = {}

        def run():
            self.result = enroll.start_session(
                hub, self.portfolios, ttl_seconds=ttl_seconds, host="127.0.0.1", port=0,
                base_path=self.base_path, tls=self.tls,
                announce=lambda *a: (announce(*a), started.set()), serve=True)

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        assert started.wait(10), "форма не поднялась"
        self.port = self.captured["port"]

    def _connection(self):
        if not self.tls:
            return http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return http.client.HTTPSConnection("127.0.0.1", self.port, timeout=10, context=context)

    def get(self, path: str | None = None) -> tuple[int, str]:
        path = self.base_path if path is None else path
        connection = self._connection()
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8", "replace")
        finally:
            connection.close()

    def post(self, fields: dict, *, path: str | None = None, raw: bytes | None = None,
             content_length: int | None = None) -> tuple[int, str]:
        path = self.base_path if path is None else path
        body = raw if raw is not None else urllib.parse.urlencode(fields).encode("utf-8")
        connection = self._connection()
        try:
            connection.putrequest("POST", path)
            connection.putheader("Content-Type", "application/x-www-form-urlencoded")
            connection.putheader("Content-Length",
                                 str(content_length if content_length is not None else len(body)))
            connection.endheaders()
            connection.send(body)
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8", "replace")
        finally:
            connection.close()

    def valid_fields(self, **overrides) -> dict:
        fields = {
            "csrf": self.captured["csrf"],
            "code": self.captured["code"],
            "portfolio": self.portfolios[0],
            "api_token": "живой-токен-провайдера",
            "publisher_id": "publisher-42",
        }
        fields.update(overrides)
        return fields

    def wait_closed(self, timeout: float = 10) -> dict:
        self.thread.join(timeout)
        assert not self.thread.is_alive(), "форма не закрылась"
        return self.result


class TestLimitsAreDeclaredCorrectly:
    def test_ttl_never_exceeds_fifteen_minutes(self):
        assert enroll.MAX_TTL_SECONDS == 15 * 60

    def test_attempts_limit_is_five(self):
        assert enroll.MAX_ATTEMPTS == 5

    def test_body_limit_is_eight_kib(self):
        assert enroll.MAX_BODY_BYTES == 8 * 1024

    def test_requested_ttl_cannot_exceed_the_cap(self):
        """Запрос может попросить меньше, но не больше."""
        hub = FakeHub()
        result = enroll.start_session(hub, ("yami",), ttl_seconds=99999, host="127.0.0.1", port=0,
                                      announce=lambda *a: None, serve=False)
        try:
            assert result["ttl_seconds"] == enroll.MAX_TTL_SECONDS
        finally:
            result["server"].server_close()

    def test_default_host_is_loopback_only(self):
        assert enroll.DEFAULT_HOST == "127.0.0.1"


class TestCodeIsNotDisclosed:
    def test_response_of_start_session_has_no_code_or_csrf(self):
        hub = FakeHub()
        result = enroll.start_session(hub, ("yami",), host="127.0.0.1", port=0,
                                      announce=lambda *a: None, serve=False)
        try:
            session = result.pop("session")
            result.pop("server")
            serialized = json.dumps(result, ensure_ascii=False)
            assert session.code not in serialized
            assert session.csrf not in serialized
        finally:
            pass

    def test_session_repr_does_not_contain_the_code(self):
        hub = FakeHub()
        result = enroll.start_session(hub, ("yami",), host="127.0.0.1", port=0,
                                      announce=lambda *a: None, serve=False)
        session = result["session"]
        try:
            assert session.code not in repr(session)
        finally:
            result["server"].server_close()

    def test_form_page_does_not_contain_the_code(self):
        hub = FakeHub()
        form = Form(hub)
        try:
            status, page = form.get("/")
            assert status == 200
            assert form.captured["code"] not in page
            # CSRF-токен в странице быть обязан: он для того и нужен.
            assert form.captured["csrf"] in page
        finally:
            form.post(form.valid_fields())
            form.wait_closed()


class TestHappyPath:
    def test_correct_input_is_stored_and_form_disappears(self):
        hub = FakeHub()
        form = Form(hub)
        status, page = form.post(form.valid_fields())
        assert status == 200
        assert "Сохранено" in page

        result = form.wait_closed()
        assert result["outcome"] == "stored"
        assert hub.calls == [("yami", "живой-токен-провайдера", "publisher-42")]

    def test_password_fields_are_masked_in_markup(self):
        hub = FakeHub()
        form = Form(hub)
        try:
            _, page = form.get("/")
            assert 'id="api_token" name="api_token" type="password"' in page
            assert 'id="code" name="code" type="password"' in page
            # Publisher ID — отдельное поле, и оно не пароль по контракту.
            assert 'id="publisher_id" name="publisher_id" type="text"' in page
        finally:
            form.post(form.valid_fields())
            form.wait_closed()

    def test_form_posts_without_query_string(self):
        hub = FakeHub()
        form = Form(hub)
        try:
            _, page = form.get("/")
            assert 'method="POST" action="/"' in page
        finally:
            form.post(form.valid_fields())
            form.wait_closed()


class TestCsrf:
    def test_missing_csrf_is_rejected(self):
        hub = FakeHub()
        form = Form(hub)
        try:
            status, page = form.post(form.valid_fields(csrf=""))
            assert status == 400
            assert "CSRF" in page
            assert hub.calls == [], "значения не должны доходить до хранилища"
        finally:
            form.post(form.valid_fields())
            form.wait_closed()

    def test_wrong_csrf_is_rejected(self):
        hub = FakeHub()
        form = Form(hub)
        try:
            status, _ = form.post(form.valid_fields(csrf="чужой-токен"))
            assert status == 400
            assert hub.calls == []
        finally:
            form.post(form.valid_fields())
            form.wait_closed()


class TestAttempts:
    def test_five_wrong_codes_close_the_form(self):
        hub = FakeHub()
        form = Form(hub)
        statuses = []
        for _ in range(enroll.MAX_ATTEMPTS):
            statuses.append(form.post(form.valid_fields(code="НЕВЕРНЫЙ-КОД"))[0])

        assert statuses[:-1] == [400] * (enroll.MAX_ATTEMPTS - 1)
        assert statuses[-1] == 404, "пятая неудача обязана закрыть endpoint"

        result = form.wait_closed()
        assert result["outcome"] == "too_many_attempts"
        assert result["attempts"] == enroll.MAX_ATTEMPTS
        assert hub.calls == []

    def test_sixth_request_gets_404(self):
        hub = FakeHub()
        form = Form(hub)
        for _ in range(enroll.MAX_ATTEMPTS):
            form.post(form.valid_fields(code="НЕВЕРНЫЙ"))
        form.wait_closed()

        with pytest.raises(OSError):
            # Сервер закрыт: соединение больше не устанавливается вовсе.
            form.get("/")

    def test_correct_code_after_failed_attempts_still_works(self):
        hub = FakeHub()
        form = Form(hub)
        for _ in range(enroll.MAX_ATTEMPTS - 1):
            assert form.post(form.valid_fields(code="НЕВЕРНЫЙ"))[0] == 400
        assert form.post(form.valid_fields())[0] == 200
        assert form.wait_closed()["outcome"] == "stored"


class TestRejectedCredentialsAreNotStored:
    def test_provider_rejection_does_not_store_and_costs_an_attempt(self):
        hub = FakeHub(accept=False)
        form = Form(hub)
        try:
            status, page = form.post(form.valid_fields())
            assert status == 400
            assert "Не сохранено" in page
            assert len(hub.calls) == 1, "проверка выполнялась"
        finally:
            for _ in range(enroll.MAX_ATTEMPTS):
                try:
                    form.post(form.valid_fields())
                except OSError:
                    break
            form.wait_closed()

    def test_empty_fields_are_refused(self):
        hub = FakeHub()
        form = Form(hub)
        try:
            status, page = form.post(form.valid_fields(api_token=""))
            assert status == 400
            assert "обязательны" in page
            assert hub.calls == []
        finally:
            form.post(form.valid_fields())
            form.wait_closed()


class TestPaths:
    def test_get_on_other_path_is_404(self):
        hub = FakeHub()
        form = Form(hub)
        try:
            assert form.get("/other-path")[0] == 404
            assert form.get("/?code=leak")[0] == 404
        finally:
            form.post(form.valid_fields())
            form.wait_closed()

    def test_post_on_other_path_is_404(self):
        hub = FakeHub()
        form = Form(hub)
        try:
            assert form.post(form.valid_fields(), path="/submit")[0] == 404
            assert hub.calls == []
        finally:
            form.post(form.valid_fields())
            form.wait_closed()


class TestBodyLimit:
    def test_body_over_eight_kib_is_refused(self):
        hub = FakeHub()
        form = Form(hub)
        try:
            oversized = form.valid_fields(api_token="Я" * enroll.MAX_BODY_BYTES)
            status, _ = form.post(oversized)
            assert status == 413
            assert hub.calls == []
        finally:
            form.post(form.valid_fields())
            form.wait_closed()

    def test_lying_content_length_is_refused(self):
        """Заголовку верить нельзя: объявленный размер проверяется отдельно."""
        hub = FakeHub()
        form = Form(hub)
        try:
            status, _ = form.post({}, raw=b"api_token=x",
                                  content_length=enroll.MAX_BODY_BYTES + 1)
            assert status == 413
        finally:
            form.post(form.valid_fields())
            form.wait_closed()


class TestTtl:
    def test_expired_form_answers_404_and_closes(self):
        hub = FakeHub()
        form = Form(hub, ttl_seconds=1)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and form.thread.is_alive():
            time.sleep(0.2)

        result = form.wait_closed()
        assert result["outcome"] == "expired"
        assert hub.calls == []

    def test_input_after_expiry_is_not_stored(self):
        hub = FakeHub()
        form = Form(hub, ttl_seconds=1)
        form.wait_closed(timeout=15)
        with pytest.raises(OSError):
            form.post(form.valid_fields())
        assert hub.calls == []


class TestNoAccessLog:
    def test_handler_logging_is_disabled(self):
        """access_log off: обработчик не пишет ни строки о запросе."""
        assert enroll._Handler.log_message is not None
        written: list[str] = []

        handler = enroll._Handler.__new__(enroll._Handler)
        handler.log_message("%s", "путь-с-секретом")
        handler.log_request(200, 10)
        assert written == []
