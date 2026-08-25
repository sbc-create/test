"""nginx-слой панели: снимки конфигурации, правка боевого vhost, живая проверка.

Про саму форму ввода здесь больше ничего нет: одноразовая форма заменена
постоянной панелью, и её поведение проверяется в
``test_secret_hub_panel_server.py``. Осталось то, что от замены не зависит —
как location попадает в конфигурацию сайта и как результат проверяется на
настоящем nginx.
"""
from __future__ import annotations

import pytest

from factory.secret_hub import publish

PATH = "/__factory-secrets"


class TestNginxSnippets:
    def test_idle_snippet_returns_404_and_disables_auth(self):
        """Снимок «панель не установлена» отвечает 404, а не 401."""
        text = publish.IDLE_SNIPPET
        assert "return 404;" in text
        assert "auth_basic off;" in text, \
            "без явного отключения адрес отвечал бы 401 вместо 404"
        assert "access_log off;" in text

    def test_panel_snippet_proxies_to_loopback_only(self):
        text = publish.PANEL_SNIPPET.format(port=8459, path=PATH)
        assert "proxy_pass http://127.0.0.1:8459;" in text
        assert "auth_basic off;" in text
        assert "access_log off;" in text
        assert "client_max_body_size 8k;" in text

    def test_snippets_never_configure_basic_auth(self):
        for text in (publish.IDLE_SNIPPET, publish.PANEL_SNIPPET.format(port=1, path=PATH)):
            assert "auth_basic_user_file" not in text
            assert "htpasswd" not in text

    def test_snippets_keep_noindex(self):
        for text in (publish.IDLE_SNIPPET, publish.PANEL_SNIPPET.format(port=1, path=PATH)):
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
    def test_all_required_checks_are_covered(self, monkeypatch, tmp_path):
        """Все заявленные проверки обязаны быть в отчёте.

        Ответы различаются по адресу: единый ответ на всё сделал бы проверку
        API бессмысленной — она затем и добавлена, что страница может прийти
        не от панели.
        """
        snippet = tmp_path / "enroll.conf"
        snippet.write_text(publish.PANEL_SNIPPET.format(port=1, path=PATH), encoding="utf-8")
        monkeypatch.setattr(publish, "SNIPPET", snippet)
        monkeypatch.setattr(publish, "certificate_subject", lambda *a, **k: (True, "ok"))

        def fetch(url, timeout=15):
            if url.endswith("/app.js"):
                return 200, {}, 'const BASE = "/x";', ""
            if "/api/" in url:
                return 405, {}, "", ""
            return 200, {}, "<!-- МЕТКА -->", ""

        monkeypatch.setattr(publish, "_fetch", fetch)

        result = publish.verify_live("example.test", "МЕТКА", path=PATH)
        names = " ".join(c.name for c in result.checks)
        for expected in ("200", "Basic Auth", "marker", "основной сайт",
                         "сертификат", "access_log", "API панели", "дочерние пути"):
            assert expected in names, f"нет проверки: {expected}"
        assert result.ok, result.failures()

    def test_www_authenticate_fails_verification(self, monkeypatch, tmp_path):
        snippet = tmp_path / "enroll.conf"
        snippet.write_text(publish.PANEL_SNIPPET.format(port=1, path=PATH), encoding="utf-8")
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
        snippet.write_text(publish.PANEL_SNIPPET.format(port=1, path=PATH), encoding="utf-8")
        monkeypatch.setattr(publish, "SNIPPET", snippet)
        monkeypatch.setattr(publish, "certificate_subject", lambda *a, **k: (True, "ok"))
        monkeypatch.setattr(publish, "_fetch",
                            lambda url, timeout=15: (200, {}, "<html>чужая страница</html>", ""))
        result = publish.verify_live("example.test", "МЕТКА", path=PATH)
        assert not result.ok
        assert any("marker" in f for f in result.failures())

    def test_bad_certificate_fails_verification(self, monkeypatch, tmp_path):
        snippet = tmp_path / "enroll.conf"
        snippet.write_text(publish.PANEL_SNIPPET.format(port=1, path=PATH), encoding="utf-8")
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
