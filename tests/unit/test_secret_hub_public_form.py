"""Публичный режим формы: путь, выбор направления, метка, отсутствие TLS внутри.

Отдельно от `test_secret_hub_enroll.py`: там проверяется поведение формы как
таковой, здесь — то, что появилось ради публикации на работающем домене.
"""
from __future__ import annotations

import http.client
import threading
import urllib.parse

import pytest

from factory.secret_hub import enroll, publish

PATH = "/__factory-secrets"


class FakeHub:
    def __init__(self, *, accept: bool = True) -> None:
        self.accept = accept
        self.calls: list[tuple[str, str, str]] = []

    def store_verified(self, portfolio: str, values: dict) -> dict:
        self.calls.append((portfolio, values["api_token"].reveal(),
                           values["publisher_id"].reveal()))
        if not self.accept:
            return {"stored": False, "reason": "провайдер отверг credentials"}
        return {"stored": True, "version": 1, "fingerprint": "sha256:тест"}


class PublicForm:
    """Форма в том виде, в каком её видит nginx: обычный HTTP на петле."""

    def __init__(self, hub, portfolios=("yami", "lords", "amedia")) -> None:
        self.captured: dict = {}
        started = threading.Event()
        self.result: dict = {}
        self.portfolios = tuple(portfolios)

        def announce(session, url, port, fingerprint, ttl):
            self.captured = {"code": session.code, "csrf": session.csrf, "port": port,
                             "marker": session.marker, "url": url}

        def run():
            self.result = enroll.start_session(
                hub, self.portfolios, host="127.0.0.1", port=0, base_path=PATH,
                tls=False, public_url="https://example.test" + PATH,
                announce=lambda *a: (announce(*a), started.set()), serve=True)

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        assert started.wait(10), "форма не поднялась"
        self.port = self.captured["port"]

    def get(self, path: str = PATH) -> tuple[int, str, dict]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("GET", path)
            r = conn.getresponse()
            return r.status, r.read().decode("utf-8", "replace"), dict(r.getheaders())
        finally:
            conn.close()

    def post(self, fields: dict, path: str = PATH) -> tuple[int, str]:
        body = urllib.parse.urlencode(fields).encode("utf-8")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("POST", path, body,
                         {"Content-Type": "application/x-www-form-urlencoded"})
            r = conn.getresponse()
            return r.status, r.read().decode("utf-8", "replace")
        finally:
            conn.close()

    def fields(self, **over) -> dict:
        base = {"csrf": self.captured["csrf"], "code": self.captured["code"],
                "portfolio": self.portfolios[0],
                "api_token": "токен", "publisher_id": "publisher-1"}
        base.update(over)
        return base

    def finish(self) -> dict:
        self.post(self.fields())
        self.thread.join(10)
        return self.result


class TestPublicPath:
    def test_form_is_served_on_the_public_path(self):
        form = PublicForm(FakeHub())
        try:
            status, body, _ = form.get(PATH)
            assert status == 200
            assert f'action="{PATH}"' in body, "форма отправляется не на публичный путь"
        finally:
            form.finish()

    def test_root_is_404_in_public_mode(self):
        """Публичный режим отвечает только по своему пути.

        Иначе форма отвечала бы и на «/», то есть на корень чужого сайта, если
        location когда-нибудь окажется шире задуманного.
        """
        form = PublicForm(FakeHub())
        try:
            assert form.get("/")[0] == 404
        finally:
            form.finish()

    def test_query_string_is_refused(self):
        form = PublicForm(FakeHub())
        try:
            assert form.get(PATH + "?code=leak")[0] == 404
        finally:
            form.finish()


class TestPortfolioChoice:
    def test_all_three_portfolios_are_offered(self):
        form = PublicForm(FakeHub())
        try:
            _, body, _ = form.get()
            for name in ("yami", "lords", "amedia"):
                assert f'<option value="{name}">' in body, f"нет варианта {name}"
        finally:
            form.finish()

    def test_chosen_portfolio_is_the_one_stored(self):
        hub = FakeHub()
        form = PublicForm(hub)
        status, _ = form.post(form.fields(portfolio="lords"))
        form.thread.join(10)
        assert status == 200
        assert hub.calls[0][0] == "lords"

    def test_portfolio_outside_the_list_is_refused(self):
        """Подставленное в POST имя не должно записать секрет куда попало."""
        hub = FakeHub()
        form = PublicForm(hub, portfolios=("yami",))
        try:
            status, body = form.post(form.fields(portfolio="lords"))
            assert status == 400
            assert "не входит в список" in body
            assert hub.calls == []
        finally:
            form.finish()

    def test_missing_portfolio_is_refused(self):
        hub = FakeHub()
        form = PublicForm(hub)
        try:
            status, _ = form.post(form.fields(portfolio=""))
            assert status == 400
            assert hub.calls == []
        finally:
            form.finish()


class TestMarker:
    def test_marker_is_present_in_html(self):
        form = PublicForm(FakeHub())
        try:
            _, body, _ = form.get()
            assert form.captured["marker"] in body
        finally:
            form.finish()

    def test_marker_is_unique_per_session(self):
        first = PublicForm(FakeHub())
        first_marker = first.captured["marker"]
        first.finish()
        second = PublicForm(FakeHub())
        try:
            assert second.captured["marker"] != first_marker
        finally:
            second.finish()

    def test_marker_is_not_a_secret_but_is_not_the_code(self):
        form = PublicForm(FakeHub())
        try:
            assert form.captured["code"] not in form.captured["marker"]
            assert form.captured["csrf"] not in form.captured["marker"]
        finally:
            form.finish()


class TestHeaders:
    def test_noindex_is_sent(self):
        form = PublicForm(FakeHub())
        try:
            _, body, headers = form.get()
            assert "noindex" in headers.get("X-Robots-Tag", "")
            assert 'content="noindex, nofollow"' in body
        finally:
            form.finish()

    def test_no_store_and_no_referrer(self):
        form = PublicForm(FakeHub())
        try:
            _, _, headers = form.get()
            assert "no-store" in headers.get("Cache-Control", "")
            assert headers.get("Referrer-Policy") == "no-referrer"
        finally:
            form.finish()

    def test_form_never_sends_www_authenticate(self):
        """Форма не использует Basic Auth — ни в каком ответе."""
        form = PublicForm(FakeHub())
        try:
            for status_path in (PATH, "/", PATH + "?x=1"):
                _, _, headers = form.get(status_path)
                assert "WWW-Authenticate" not in headers
        finally:
            form.finish()


class TestNginxSnippets:
    def test_idle_snippet_returns_404_and_disables_auth(self):
        text = publish.IDLE_SNIPPET
        assert "return 404;" in text
        assert "auth_basic off;" in text, \
            "без явного отключения адрес отвечал бы 401 вместо 404"
        assert "access_log off;" in text

    def test_active_snippet_proxies_to_loopback_only(self):
        text = publish.ACTIVE_SNIPPET.format(port=8459, path=PATH)
        assert "proxy_pass http://127.0.0.1:8459;" in text
        assert "auth_basic off;" in text
        assert "access_log off;" in text
        assert "client_max_body_size 8k;" in text

    def test_snippets_never_configure_basic_auth(self):
        for text in (publish.IDLE_SNIPPET, publish.ACTIVE_SNIPPET.format(port=1, path=PATH)):
            assert "auth_basic_user_file" not in text
            assert "htpasswd" not in text

    def test_snippets_keep_noindex(self):
        for text in (publish.IDLE_SNIPPET, publish.ACTIVE_SNIPPET.format(port=1, path=PATH)):
            assert "noindex" in text

    def test_path_is_a_single_segment(self):
        """Чем длиннее путь, тем выше шанс пересечься с маршрутом самого сайта."""
        assert publish.DEFAULT_PATH.count("/") == 1
        assert publish.DEFAULT_PATH.startswith("/__")


class TestVhostPatching:
    VHOST = """
server {
    listen 80;
    server_name example.test;
    location / { return 308 https://example.test$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name www.example.test;
    location / { return 308 https://example.test$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name example.test;

    location / {
        auth_basic "staging";
        auth_basic_user_file /etc/nginx/x.htpasswd;
        proxy_pass http://127.0.0.1:3101;
    }
}
"""

    def test_include_lands_in_the_https_apex_block(self, tmp_path, monkeypatch):
        vhost = tmp_path / "example.test.conf"
        vhost.write_text(self.VHOST, encoding="utf-8")
        monkeypatch.setattr(publish, "nginx_test", lambda: (True, ""))
        monkeypatch.setattr(publish, "BACKUP_DIR", tmp_path / "backups")

        publish.ensure_include(vhost, "example.test")
        text = vhost.read_text(encoding="utf-8")

        apex_start, apex_end = publish._apex_server_span(text, "example.test")
        assert publish.BEGIN in text[apex_start:apex_end], \
            "include попал не в тот server-блок"
        # В блоке www и в HTTP-блоке include быть не должно.
        assert text.count(publish.BEGIN) == 1

    def test_include_is_idempotent(self, tmp_path, monkeypatch):
        vhost = tmp_path / "example.test.conf"
        vhost.write_text(self.VHOST, encoding="utf-8")
        monkeypatch.setattr(publish, "nginx_test", lambda: (True, ""))
        monkeypatch.setattr(publish, "BACKUP_DIR", tmp_path / "backups")

        publish.ensure_include(vhost, "example.test")
        first = vhost.read_text(encoding="utf-8")
        second_result = publish.ensure_include(vhost, "example.test")

        assert second_result["changed"] is False
        assert vhost.read_text(encoding="utf-8") == first

    def test_remove_include_restores_original(self, tmp_path, monkeypatch):
        vhost = tmp_path / "example.test.conf"
        vhost.write_text(self.VHOST, encoding="utf-8")
        monkeypatch.setattr(publish, "nginx_test", lambda: (True, ""))
        monkeypatch.setattr(publish, "BACKUP_DIR", tmp_path / "backups")

        publish.ensure_include(vhost, "example.test")
        publish.remove_include(vhost)

        assert publish.BEGIN not in vhost.read_text(encoding="utf-8")
        assert "proxy_pass http://127.0.0.1:3101;" in vhost.read_text(encoding="utf-8")

    def test_backup_is_made_before_patching(self, tmp_path, monkeypatch):
        vhost = tmp_path / "example.test.conf"
        vhost.write_text(self.VHOST, encoding="utf-8")
        backups = tmp_path / "backups"
        monkeypatch.setattr(publish, "nginx_test", lambda: (True, ""))
        monkeypatch.setattr(publish, "BACKUP_DIR", backups)

        result = publish.ensure_include(vhost, "example.test")
        assert result["backup"] is not None
        copies = list(backups.glob("example.test.conf.*"))
        assert copies, "бэкап боевого vhost не сделан"
        assert self.VHOST.strip() in copies[0].read_text(encoding="utf-8")

    def test_rejected_config_is_rolled_back(self, tmp_path, monkeypatch):
        """nginx -t отказал — боевой файл обязан вернуться как был."""
        vhost = tmp_path / "example.test.conf"
        vhost.write_text(self.VHOST, encoding="utf-8")
        monkeypatch.setattr(publish, "nginx_test", lambda: (False, "искусственный отказ"))
        monkeypatch.setattr(publish, "BACKUP_DIR", tmp_path / "backups")

        with pytest.raises(publish.PublishError):
            publish.ensure_include(vhost, "example.test")

        assert vhost.read_text(encoding="utf-8") == self.VHOST
        assert publish.BEGIN not in vhost.read_text(encoding="utf-8")

    def test_unknown_server_name_is_refused(self, tmp_path, monkeypatch):
        """Правка вслепую опаснее отказа."""
        vhost = tmp_path / "example.test.conf"
        vhost.write_text(self.VHOST, encoding="utf-8")
        monkeypatch.setattr(publish, "nginx_test", lambda: (True, ""))
        monkeypatch.setattr(publish, "BACKUP_DIR", tmp_path / "backups")

        with pytest.raises(publish.PublishError) as excinfo:
            publish.ensure_include(vhost, "нет-такого.test")
        assert "не найден" in str(excinfo.value)
        assert vhost.read_text(encoding="utf-8") == self.VHOST


class TestLiveVerificationShape:
    def test_all_five_required_checks_are_covered(self, monkeypatch, tmp_path):
        """Задание перечисляет пять проверок — все обязаны быть в отчёте."""
        snippet = tmp_path / "enroll.conf"
        snippet.write_text(publish.ACTIVE_SNIPPET.format(port=1, path=PATH), encoding="utf-8")
        monkeypatch.setattr(publish, "SNIPPET", snippet)
        monkeypatch.setattr(publish, "certificate_subject", lambda *a, **k: (True, "ok"))
        monkeypatch.setattr(publish, "_fetch",
                            lambda url, timeout=15: (200, {}, "<!-- МЕТКА -->", ""))

        result = publish.verify_live("example.test", "МЕТКА", path=PATH)
        names = " ".join(c.name for c in result.checks)
        for expected in ("200", "Basic Auth", "marker", "основной сайт",
                         "сертификат", "access_log"):
            assert expected in names, f"нет проверки: {expected}"
        assert result.ok

    def test_www_authenticate_fails_verification(self, monkeypatch, tmp_path):
        snippet = tmp_path / "enroll.conf"
        snippet.write_text(publish.ACTIVE_SNIPPET.format(port=1, path=PATH), encoding="utf-8")
        monkeypatch.setattr(publish, "SNIPPET", snippet)
        monkeypatch.setattr(publish, "certificate_subject", lambda *a, **k: (True, "ok"))
        monkeypatch.setattr(publish, "_fetch",
                            lambda url, timeout=15: (401, {"WWW-Authenticate": 'Basic realm="x"'},
                                                     "", ""))
        result = publish.verify_live("example.test", "МЕТКА", path=PATH)
        assert not result.ok
        assert any("Basic Auth" in f for f in result.failures())

    def test_missing_marker_fails_verification(self, monkeypatch, tmp_path):
        """Страница без метки этой сессии — не наша страница."""
        snippet = tmp_path / "enroll.conf"
        snippet.write_text(publish.ACTIVE_SNIPPET.format(port=1, path=PATH), encoding="utf-8")
        monkeypatch.setattr(publish, "SNIPPET", snippet)
        monkeypatch.setattr(publish, "certificate_subject", lambda *a, **k: (True, "ok"))
        monkeypatch.setattr(publish, "_fetch",
                            lambda url, timeout=15: (200, {}, "<html>чужая страница</html>", ""))
        result = publish.verify_live("example.test", "МЕТКА", path=PATH)
        assert not result.ok
        assert any("marker" in f for f in result.failures())

    def test_bad_certificate_fails_verification(self, monkeypatch, tmp_path):
        snippet = tmp_path / "enroll.conf"
        snippet.write_text(publish.ACTIVE_SNIPPET.format(port=1, path=PATH), encoding="utf-8")
        monkeypatch.setattr(publish, "SNIPPET", snippet)
        monkeypatch.setattr(publish, "certificate_subject",
                            lambda *a, **k: (False, "сертификат другого домена"))
        monkeypatch.setattr(publish, "_fetch",
                            lambda url, timeout=15: (200, {}, "<!-- МЕТКА -->", ""))
        result = publish.verify_live("example.test", "МЕТКА", path=PATH)
        assert not result.ok

    def test_access_log_off_is_checked_in_the_snippet(self, monkeypatch, tmp_path):
        snippet = tmp_path / "enroll.conf"
        snippet.write_text("location /x { proxy_pass http://127.0.0.1:1; }", encoding="utf-8")
        monkeypatch.setattr(publish, "SNIPPET", snippet)
        monkeypatch.setattr(publish, "certificate_subject", lambda *a, **k: (True, "ok"))
        monkeypatch.setattr(publish, "_fetch",
                            lambda url, timeout=15: (200, {}, "<!-- МЕТКА -->", ""))
        result = publish.verify_live("example.test", "МЕТКА", path=PATH)
        assert not result.ok
        assert any("access_log" in f for f in result.failures())

    def test_verify_gone_expects_404(self, monkeypatch):
        monkeypatch.setattr(publish, "_fetch", lambda url, timeout=15: (404, {}, "", ""))
        assert publish.verify_gone("example.test", path=PATH).ok

    def test_verify_gone_rejects_401(self, monkeypatch):
        """401 вместо 404 означает, что запрос ушёл в location с паролем."""
        monkeypatch.setattr(publish, "_fetch",
                            lambda url, timeout=15: (401, {"WWW-Authenticate": "Basic"}, "", ""))
        assert not publish.verify_gone("example.test", path=PATH).ok
