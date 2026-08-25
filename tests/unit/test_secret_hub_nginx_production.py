"""Разбор боевого 401 и защита от его повторения.

Живая установка на claude-control-01 вернула:

    https://yummyani.site/__factory-secrets → HTTP 401
    WWW-Authenticate: Basic realm="YummyAnime staging"
    marker Secret Hub отсутствует

Выглядело как «location панели проиграл `location /`». Измерение на хосте
показало другое: location правильный и работает — `/__factory-secrets` и
`/__factory-secrets/app.js` отдают 404 из снимка простоя **без** запроса
пароля, то есть уверенно обходят Basic Auth основного сайта.

Настоящая причина — во времени. `systemctl reload nginx` лишь посылает сигнал
мастеру и возвращается немедленно; прежние рабочие процессы продолжают
отвечать по старой конфигурации. Проверка запускалась сразу после reload и
попадала на них: запрос уходил в `location /` и получал 401.

Тесты ниже проверяют обе стороны: разбор и вставку — на ФАКТИЧЕСКОЙ
конфигурации домена, а ожидание перезагрузки — на подставном ответе, который
воспроизводит ровно тот 401.
"""
from __future__ import annotations

import re

import pytest

from factory.secret_hub import publish
from factory.secret_hub.panel.ui import MARKER

PATH = "/__factory-secrets"
SERVER_NAME = "yummyani.site"


@pytest.fixture
def production_vhost(repo_root):
    """Фактическая конфигурация домена, снятая с боевого хоста."""
    path = repo_root / "tests" / "fixtures" / "nginx-yummyani-site-production.conf"
    return path.read_text(encoding="utf-8")


class TestProductionFixtureIsTheRealThing:
    def test_fixture_has_three_server_blocks(self, production_vhost):
        """:80 redirect, :443 www → apex, :443 apex. Именно эта структура."""
        assert len(re.findall(r"^server \{", production_vhost, re.M)) == 3

    def test_fixture_has_basic_auth_on_the_main_location(self, production_vhost):
        """Основной сайт под паролем — это и есть условие задачи."""
        assert 'auth_basic "YummyAnime staging"' in production_vhost

    def test_fixture_has_acme_location_with_auth_off(self, production_vhost):
        """`auth_basic off` встречается и вне панели — прежний тест на этом ошибся."""
        assert "auth_basic off;" in production_vhost

    def test_fixture_contains_no_secrets(self, production_vhost):
        for pattern in (r"-----BEGIN", r"\$2[aby]\$", r"apr1", r"\$apr1\$"):
            assert not re.search(pattern, production_vhost), \
                "в фикстуре оказался секрет"

    def test_fixture_is_pre_installation(self, production_vhost):
        assert "secret-hub" not in production_vhost


class TestInsertionIntoTheRealConfig:
    def test_include_lands_in_the_apex_https_block(self, production_vhost):
        start, end = publish._apex_server_span(production_vhost, SERVER_NAME)
        block = production_vhost[start:end]

        names = re.search(r"server_name\s+([^;]+);", block).group(1).split()
        assert names == [SERVER_NAME], f"выбран блок для {names}"
        assert re.search(r"\blisten\s+443\b", block)
        assert "listen 80;" not in block
        # Это именно тот блок, где стоит Basic Auth и проксирование сайта.
        assert 'auth_basic "YummyAnime staging"' in block
        assert "proxy_pass" in block

    def test_www_block_is_not_chosen(self, production_vhost):
        """Блок www увёл бы панель за 308-редирект."""
        start, end = publish._apex_server_span(production_vhost, SERVER_NAME)
        block = production_vhost[start:end]
        assert "www.yummyani.site" not in re.search(
            r"server_name\s+([^;]+);", block).group(1)

    def test_insertion_keeps_braces_balanced(self, production_vhost):
        start, end = publish._apex_server_span(production_vhost, SERVER_NAME)
        block = production_vhost[start:end]
        insertion = (f"\n    {publish.BEGIN}\n"
                     f"    include {publish.SNIPPET_DIR}/*.conf;\n"
                     f"    {publish.END}\n")
        patched = block[:-1].rstrip() + "\n" + insertion + "}"
        assert patched.count("{") == patched.count("}")
        # include обязан оказаться ВНУТРИ блока, а не после его закрытия:
        # location на уровне http nginx не примет вовсе.
        assert patched.rstrip().endswith("}")
        assert patched.index(publish.BEGIN) < patched.rindex("}")


class TestLocationBeatsBasicAuth:
    """Почему location панели обязан выигрывать у `location /`."""

    def test_panel_location_uses_the_caret_tilde_modifier(self):
        """`^~` — не украшение: он же отсекает и regex-локации."""
        for snippet in (publish.IDLE_SNIPPET,
                        publish.PANEL_SNIPPET.format(port=1, path=PATH)):
            assert f"location ^~ {PATH}" in snippet

    def test_panel_location_disables_basic_auth_explicitly(self):
        """Соседний location не наследует auth_basic, но полагаться на это нельзя.

        Если пароль когда-нибудь переедет из `location /` в `server`-блок,
        наследование начнётся — и без явного `off` панель окажется за паролем,
        которого у владельца нет.
        """
        for snippet in (publish.IDLE_SNIPPET,
                        publish.PANEL_SNIPPET.format(port=1, path=PATH)):
            assert "auth_basic off;" in snippet

    def test_prefix_covers_child_paths(self):
        """API панели живёт под тем же префиксом и обязан обслуживаться им же."""
        snippet = publish.PANEL_SNIPPET.format(port=8459, path=PATH)
        assert f"location ^~ {PATH} " in snippet or f"location ^~ {PATH}{{" in snippet
        # proxy_pass без завершающего слэша сохраняет полный URI, включая
        # /__factory-secrets/api/... — панель разбирает путь сама.
        assert "proxy_pass http://127.0.0.1:8459;" in snippet
        assert "proxy_pass http://127.0.0.1:8459/;" not in snippet


class TestWaitUntilServing:
    """Ожидание, которого не хватало: reload возвращается раньше применения."""

    def test_returns_true_when_marker_appears(self, monkeypatch):
        monkeypatch.setattr(publish, "_fetch",
                            lambda url, timeout=15: (200, {}, f"<!-- {MARKER} -->", ""))
        ok, detail = publish.wait_until_serving(SERVER_NAME, PATH, MARKER, timeout=2)
        assert ok is True
        assert "панель отвечает" in detail

    def test_waits_out_the_old_configuration(self, monkeypatch):
        """Ровно боевой сценарий: сперва 401 от `location /`, потом панель."""
        answers = [
            (401, {"WWW-Authenticate": 'Basic realm="YummyAnime staging"'}, "", ""),
            (401, {"WWW-Authenticate": 'Basic realm="YummyAnime staging"'}, "", ""),
            (200, {}, f"<!-- {MARKER} -->", ""),
        ]
        monkeypatch.setattr(publish, "RELOAD_POLL_SECONDS", 0.01)
        monkeypatch.setattr(publish, "_fetch",
                            lambda url, timeout=15: answers.pop(0) if answers
                            else (200, {}, f"<!-- {MARKER} -->", ""))
        ok, detail = publish.wait_until_serving(SERVER_NAME, PATH, MARKER, timeout=5)
        assert ok is True, detail

    def test_gives_up_and_names_the_old_configuration(self, monkeypatch):
        """Если 401 не проходит — причина должна быть названа прямо."""
        monkeypatch.setattr(publish, "RELOAD_POLL_SECONDS", 0.01)
        monkeypatch.setattr(
            publish, "_fetch",
            lambda url, timeout=15: (401, {"WWW-Authenticate": 'Basic realm="x"'}, "", ""))
        ok, detail = publish.wait_until_serving(SERVER_NAME, PATH, MARKER, timeout=1)
        assert ok is False
        assert "прежняя конфигурация" in detail

    def test_marker_not_status_is_the_signal(self, monkeypatch):
        """200 от постороннего обработчика не считается успехом."""
        monkeypatch.setattr(publish, "RELOAD_POLL_SECONDS", 0.01)
        monkeypatch.setattr(publish, "_fetch",
                            lambda url, timeout=15: (200, {}, "<html>чужая страница</html>", ""))
        ok, detail = publish.wait_until_serving(SERVER_NAME, PATH, MARKER, timeout=1)
        assert ok is False
        assert "без метки панели" in detail


class TestVerifyLiveCoversTheApi:
    """Проверять только 200 оказалось мало."""

    def _snippet(self, tmp_path, monkeypatch):
        snippet = tmp_path / "enroll.conf"
        snippet.write_text(publish.PANEL_SNIPPET.format(port=1, path=PATH),
                           encoding="utf-8")
        monkeypatch.setattr(publish, "SNIPPET", snippet)
        monkeypatch.setattr(publish, "certificate_subject", lambda *a, **k: (True, "ok"))
        return snippet

    def _responder(self, *, js_body="const BASE = \"/x\";", js_status=200,
                   child_headers=None):
        def fetch(url, timeout=15):
            if url.endswith("/app.js"):
                return js_status, {}, js_body, ""
            if "/api/" in url:
                return 405, dict(child_headers or {}), "", ""
            if url.endswith(PATH):
                return 200, {}, f"<!-- {MARKER} -->", ""
            return 401, {"WWW-Authenticate": "Basic"}, "", ""
        return fetch

    def test_api_check_is_part_of_verification(self, tmp_path, monkeypatch):
        self._snippet(tmp_path, monkeypatch)
        monkeypatch.setattr(publish, "_fetch", self._responder())
        result = publish.verify_live(SERVER_NAME, MARKER, path=PATH)
        names = " ".join(c.name for c in result.checks)
        assert "API панели отвечает" in names
        assert "дочерние пути не требуют Basic Auth" in names
        assert result.ok, result.failures()

    def test_missing_panel_script_fails_verification(self, tmp_path, monkeypatch):
        """Страница есть, а скрипт отдаёт кто-то другой — это не панель."""
        self._snippet(tmp_path, monkeypatch)
        monkeypatch.setattr(publish, "_fetch",
                            self._responder(js_body="<html>не скрипт</html>"))
        result = publish.verify_live(SERVER_NAME, MARKER, path=PATH)
        assert not result.ok
        assert any("API панели" in f for f in result.failures())

    def test_child_path_behind_basic_auth_fails_verification(self, tmp_path, monkeypatch):
        """Именно этот случай и был в бою — только на корневом пути."""
        self._snippet(tmp_path, monkeypatch)
        monkeypatch.setattr(
            publish, "_fetch",
            self._responder(child_headers={"WWW-Authenticate":
                                           'Basic realm="YummyAnime staging"'}))
        result = publish.verify_live(SERVER_NAME, MARKER, path=PATH)
        assert not result.ok
        assert any("дочерние пути" in f for f in result.failures())


class TestIdempotencyAfterRollback:
    """Установка после отката обязана продолжаться, а не спотыкаться."""

    def test_existing_include_is_not_duplicated(self, production_vhost, tmp_path,
                                                monkeypatch):
        vhost = tmp_path / "yummyani.site.conf"
        vhost.write_text(production_vhost, encoding="utf-8")
        monkeypatch.setattr(publish, "nginx_test", lambda: (True, ""))
        monkeypatch.setattr(publish, "BACKUP_DIR", tmp_path / "backups")

        publish.ensure_include(vhost, SERVER_NAME)
        after_first = vhost.read_text(encoding="utf-8")
        # Состояние после отката: include остался, снимок — простоя.
        second = publish.ensure_include(vhost, SERVER_NAME)

        assert second["changed"] is False
        assert vhost.read_text(encoding="utf-8") == after_first
        assert after_first.count(publish.BEGIN) == 1

    def test_idle_snippet_answers_404_without_password(self):
        """Состояние после отката: адрес отвечает 404, а не 401.

        Проверено и на живом хосте: `/__factory-secrets` и
        `/__factory-secrets/app.js` возвращают 404 без WWW-Authenticate.
        """
        assert "return 404;" in publish.IDLE_SNIPPET
        assert "auth_basic off;" in publish.IDLE_SNIPPET
