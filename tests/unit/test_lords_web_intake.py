"""REQ-LORDS-WEB-INTAKE: одноразовая веб-форма приёма учётных данных.

Форма нужна там, где секрет нельзя перепечатать руками. Значит, к ней
предъявляются требования, которых нет к обычной странице: секрет не должен
оказаться нигде, кроме файла 0600.

Здесь поднимается настоящий приёмный сервер и с ним разговаривают по HTTP.
Боевые секреты не нужны: проверяется поведение, а не доступность провайдера —
обращение к CDNVideoHub подменяется.
"""

from __future__ import annotations

import http.client
import re
import subprocess
import time
import urllib.parse

import pytest

from factory.lords import web_intake
from factory.paths import PATHS

SCRIPT = PATHS.root / "automation/host/lords-web-activation.sh"
ACTIVATOR = PATHS.root / "automation/host/activate-lords-live.sh"

TOKEN = "cdnvh-live-token-value-that-must-never-leak"
PUBLISHER = "4321"


class Client:
    """Минимальный HTTP-клиент к приёмному серверу."""

    def __init__(self, port: int):
        self.port = port
        self.cookie = ""

    def get(self, path="/__lords-activate"):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("GET", path)
        r = c.getresponse()
        body = r.read().decode("utf-8", "replace")
        for header, value in r.getheaders():
            if header.lower() == "set-cookie":
                self.cookie = value.split(";", 1)[0]
        c.close()
        return r.status, body

    def post(self, fields: dict, path="/__lords-activate", raw: str | None = None):
        payload = raw if raw is not None else urllib.parse.urlencode(fields)
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        c.request("POST", path, body=payload, headers=headers)
        r = c.getresponse()
        body = r.read().decode("utf-8", "replace")
        c.close()
        return r.status, body


def csrf_of(html: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', html)
    return match.group(1) if match else ""


@pytest.fixture
def stand(tmp_path):
    """Приёмный сервер с подменённой проверкой токена."""
    accepted = {"count": 0}
    probes: list[str] = []

    def probe(request, _timeout):
        probes.append(request.get_header("Authorization", ""))
        # Верным считается только наш токен.
        return 200 if request.get_header("Authorization") == f"Bearer {TOKEN}" else 401

    intake = web_intake.Intake(
        code="ABCD2345",
        token_file=tmp_path / "secrets" / "api-token",
        publisher_file=tmp_path / "secrets" / "publisher-id",
        probe_url="https://example.invalid/api/v1/titles?limit=1",
        ttl_seconds=900,
    )
    intake.probe = probe
    server, port = web_intake.serve(
        intake, on_accept=lambda: accepted.__setitem__("count", accepted["count"] + 1)
    )
    yield intake, Client(port), accepted, probes
    server.shutdown()
    server.server_close()


def submit(client, intake, **overrides):
    _status, html = client.get()
    fields = {
        "csrf": csrf_of(html),
        "code": intake.code,
        "token": TOKEN,
        "publisher": PUBLISHER,
        "rights": "RIGHTS_CONFIRMED=yes",
    }
    fields.update(overrides)
    return client.post(fields)


# ---------------------------------------------------------------------------
# Успешный путь
# ---------------------------------------------------------------------------
class TestHappyPath:
    def test_the_form_is_served_over_get(self, stand):
        _intake, client, _accepted, _probes = stand
        status, html = client.get()
        assert status == 200
        assert 'type="password"' in html, "токен вводится не скрытым полем"
        assert 'name="csrf"' in html

    def test_correct_submission_writes_both_secrets(self, stand):
        intake, client, accepted, _probes = stand
        status, html = submit(client, intake)
        assert status == 200, html
        assert intake.state == web_intake.STATE_ACCEPTED
        assert intake.token_file.read_text(encoding="utf-8") == TOKEN
        assert intake.publisher_file.read_text(encoding="utf-8") == PUBLISHER
        # Активация запускается ровно один раз.
        time.sleep(0.3)
        assert accepted["count"] == 1

    def test_the_secret_files_are_0600_and_the_directory_0700(self, stand):
        intake, client, _accepted, _probes = stand
        submit(client, intake)
        assert oct(intake.token_file.stat().st_mode)[-3:] == "600"
        assert oct(intake.publisher_file.stat().st_mode)[-3:] == "600"
        assert oct(intake.token_file.parent.stat().st_mode)[-3:] == "700"

    def test_no_temporary_file_survives(self, stand):
        intake, client, _accepted, _probes = stand
        submit(client, intake)
        leftovers = [p.name for p in intake.token_file.parent.iterdir()
                     if p.name.startswith(".")]
        assert leftovers == [], leftovers

    def test_the_token_goes_in_a_header_not_a_url(self, stand):
        intake, client, _accepted, probes = stand
        submit(client, intake)
        assert probes and probes[0] == f"Bearer {TOKEN}"
        assert TOKEN not in intake.probe_url


# ---------------------------------------------------------------------------
# Секрет не утекает
# ---------------------------------------------------------------------------
class TestNoLeak:
    def test_the_secret_is_absent_from_every_response(self, stand):
        intake, client, _accepted, _probes = stand
        _status, before = client.get()
        _status, after = submit(client, intake)
        for html in (before, after):
            assert TOKEN not in html
            assert PUBLISHER not in html

    def test_a_rejected_submission_does_not_echo_the_secret(self, stand):
        """Перерисовывать введённый токен обратно в форму незачем."""
        intake, client, _accepted, _probes = stand
        _status, html = submit(client, intake, token="wrong-token-value")
        assert "wrong-token-value" not in html
        assert TOKEN not in html

    def test_the_server_writes_no_request_log(self, stand, capfd):
        intake, client, _accepted, _probes = stand
        submit(client, intake)
        captured = capfd.readouterr()
        assert TOKEN not in captured.out and TOKEN not in captured.err
        assert "__lords-activate" not in captured.err, "журнал запросов не отключён"

    def test_the_status_report_carries_no_secret(self, stand):
        intake, client, _accepted, _probes = stand
        submit(client, intake)
        report = web_intake.status_json(intake)
        assert TOKEN not in report
        assert intake.code not in report

    def test_get_never_accepts_values(self, stand):
        """Сохранение только POST: query попадает в журналы и историю."""
        intake, client, _accepted, _probes = stand
        status, _html = client.get(
            f"/__lords-activate?token={TOKEN}&publisher={PUBLISHER}"
        )
        assert status == 200
        assert not intake.token_file.exists(), "GET сохранил значения"


# ---------------------------------------------------------------------------
# Код доступа
# ---------------------------------------------------------------------------
class TestAccessCode:
    def test_a_wrong_code_changes_nothing(self, stand):
        intake, client, _accepted, _probes = stand
        status, html = submit(client, intake, code="WRONGXXX")
        assert status == 200
        assert "код неверен" in html
        assert not intake.token_file.exists()

    def test_attempts_are_limited(self, stand):
        intake, client, _accepted, _probes = stand
        last = ""
        # Ровно столько, сколько разрешено: последняя попытка и закрывает приём.
        for _ in range(web_intake.MAX_CODE_ATTEMPTS):
            _status, last = submit(client, intake, code="WRONGXXX")
        assert intake.state == web_intake.STATE_LOCKED
        assert "Исчерпаны попытки" in last
        assert not intake.token_file.exists()

    def test_after_lockout_the_correct_code_no_longer_works(self, stand):
        intake, client, _accepted, _probes = stand
        for _ in range(web_intake.MAX_CODE_ATTEMPTS):
            submit(client, intake, code="WRONGXXX")
        _status, html = submit(client, intake)
        assert intake.state == web_intake.STATE_LOCKED
        assert not intake.token_file.exists(), "после блокировки приём продолжился"
        assert "закрыт" in html.lower()

    def test_the_code_alphabet_avoids_confusable_characters(self):
        for confusable in ("0", "O", "1", "I", "L"):
            assert confusable not in web_intake.CODE_ALPHABET

    def test_generated_codes_differ(self):
        assert len({web_intake.generate_code() for _ in range(20)}) > 15


# ---------------------------------------------------------------------------
# CSRF и метод
# ---------------------------------------------------------------------------
class TestCsrf:
    def test_a_post_without_csrf_is_refused(self, stand):
        intake, client, _accepted, _probes = stand
        client.get()
        status, html = client.post({
            "code": intake.code, "token": TOKEN,
            "publisher": PUBLISHER, "rights": "RIGHTS_CONFIRMED=yes",
        })
        assert status == 200
        assert "устарела" in html
        assert not intake.token_file.exists()

    def test_a_foreign_csrf_is_refused(self, stand):
        intake, client, _accepted, _probes = stand
        client.get()
        status, html = client.post({
            "csrf": "not-the-issued-token", "code": intake.code,
            "token": TOKEN, "publisher": PUBLISHER, "rights": "RIGHTS_CONFIRMED=yes",
        })
        assert "устарела" in html
        assert not intake.token_file.exists()

    def test_a_csrf_without_the_session_cookie_is_refused(self, stand):
        intake, client, _accepted, _probes = stand
        _status, html = client.get()
        client.cookie = ""  # токен есть, сессии нет
        status, body = client.post({
            "csrf": csrf_of(html), "code": intake.code, "token": TOKEN,
            "publisher": PUBLISHER, "rights": "RIGHTS_CONFIRMED=yes",
        })
        assert not intake.token_file.exists()
        assert "устарела" in body


# ---------------------------------------------------------------------------
# Проверка значений
# ---------------------------------------------------------------------------
class TestValidation:
    @pytest.mark.parametrize("value", ["0", "-1", "abc", "1.5", "007", ""])
    def test_a_bad_publisher_id_is_refused(self, stand, value):
        intake, client, _accepted, _probes = stand
        submit(client, intake, publisher=value)
        assert not intake.token_file.exists()

    def test_missing_rights_confirmation_is_refused(self, stand):
        intake, client, _accepted, _probes = stand
        _status, html = submit(client, intake, rights="no")
        assert "RIGHTS_CONFIRMED=yes" in html
        assert not intake.token_file.exists()

    def test_an_oversized_body_is_refused(self, stand):
        intake, client, _accepted, _probes = stand
        client.get()
        status, _html = client.post({}, raw="x" * (web_intake.MAX_BODY_BYTES + 100))
        assert status == 413
        assert not intake.token_file.exists()


# ---------------------------------------------------------------------------
# Неверный токен
# ---------------------------------------------------------------------------
class TestBadToken:
    def test_a_rejected_token_changes_nothing_and_keeps_the_form_open(self, stand):
        intake, client, _accepted, _probes = stand
        _status, html = submit(client, intake, token="not-the-right-token")
        assert not intake.token_file.exists(), "секрет записан при отклонённом токене"
        assert intake.state == web_intake.STATE_WAITING, "форма закрылась"
        assert "отклонил" in html
        # Повторный ввод возможен и срабатывает.
        submit(client, intake)
        assert intake.token_file.read_text(encoding="utf-8") == TOKEN

    def test_an_unreachable_source_changes_nothing(self, stand):
        intake, client, _accepted, _probes = stand

        def broken(_request, _timeout):
            raise OSError("сеть недоступна")

        intake.probe = broken
        _status, html = submit(client, intake)
        assert not intake.token_file.exists()
        assert "недоступен" in html


# ---------------------------------------------------------------------------
# Срок действия
# ---------------------------------------------------------------------------
class TestTtl:
    def test_an_expired_form_refuses_get_and_post(self, stand):
        intake, client, _accepted, _probes = stand
        intake.started_at -= intake.ttl_seconds + 1

        status, html = client.get()
        assert status == 410
        assert "истёк" in html

        status, _html = client.post({"csrf": "x", "code": intake.code, "token": TOKEN,
                                     "publisher": PUBLISHER, "rights": "RIGHTS_CONFIRMED=yes"})
        assert status == 410
        assert not intake.token_file.exists()

    def test_seconds_left_reaches_zero(self, stand):
        intake, _client, _accepted, _probes = stand
        intake.started_at -= intake.ttl_seconds + 5
        assert intake.seconds_left() == 0
        assert intake.expired()

    def test_the_default_ttl_is_fifteen_minutes(self):
        assert web_intake.DEFAULT_TTL_SECONDS == 15 * 60


# ---------------------------------------------------------------------------
# Повторное использование
# ---------------------------------------------------------------------------
class TestSingleUse:
    def test_a_second_submission_is_refused(self, stand):
        intake, client, _accepted, _probes = stand
        submit(client, intake)
        assert intake.state == web_intake.STATE_ACCEPTED
        status, html = client.get()
        assert status == 410
        assert "завершён" in html

    def test_sessions_are_cleared_after_acceptance(self, stand):
        intake, client, _accepted, _probes = stand
        submit(client, intake)
        assert intake.sessions == {}


# ---------------------------------------------------------------------------
# Сценарий на хосте
# ---------------------------------------------------------------------------
class TestHostScript:
    @pytest.fixture(scope="class")
    def text(self):
        return SCRIPT.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def code(self):
        joined = SCRIPT.read_text(encoding="utf-8").replace("\\\n", " ")
        return [line for line in joined.splitlines()
                if line.strip() and not line.lstrip().startswith("#")]

    def test_it_parses(self):
        result = subprocess.run(["/bin/bash", "-n", str(SCRIPT)],
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr

    def test_it_refuses_without_root(self):
        result = subprocess.run(["/bin/bash", str(SCRIPT)],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode != 0
        assert "нужен root" in result.stderr

    def test_access_log_is_off_for_the_endpoint(self, text):
        assert "access_log off;" in text

    def test_the_body_size_is_capped(self, text):
        assert "client_max_body_size" in text

    def test_it_uses_the_existing_certificate(self, text):
        assert "/etc/letsencrypt/live/" in text
        assert "certbot" not in text.lower(), "сценарий выпускает сертификаты"

    def test_basic_auth_is_disabled_only_inside_the_exact_location(self, text):
        """Пароль снимается ровно на одном адресе и нигде больше.

        Прежняя редакция запрещала `auth_basic off` во всём файле. Это было
        верно ровно до того, как выяснилось, что снимать пароль на точном
        location всё-таки нужно: он не наследует auth_basic из `location /`,
        но унаследовал бы его с уровня server. Поэтому проверяется место, а не
        наличие строки.
        """
        snippet = text.split('cat > "${SNIPPET}"', 1)[1].split("\nCONF\n", 1)[0]
        assert "auth_basic off;" in snippet, "на форме остался пароль сайта"
        assert text.count("auth_basic off") == 1, "пароль снят где-то ещё"

    def test_the_snippet_opens_exactly_one_address(self, text):
        """Префиксный location открыл бы весь раздел, а не одну страницу."""
        snippet = text.split('cat > "${SNIPPET}"', 1)[1].split("\nCONF\n", 1)[0]
        assert "location = ${LOCATION_PATH}" in snippet, "location не точный"

    def test_the_site_password_file_is_not_touched(self, text):
        assert "htpasswd" not in text.lower()

    def test_the_endpoint_is_a_location_not_a_duplicate_server(self, text):
        """Два server{} с одним именем — молчаливый выбор первого."""
        snippet = text.split("cat > \"${SNIPPET}\"", 1)[1].split("CONF\n", 2)[1]
        assert "location = ${LOCATION_PATH}" in snippet
        assert "server {" not in snippet

    def test_teardown_removes_the_snippet_and_reloads(self, text):
        teardown = text.split("teardown() {", 1)[1].split("\n}", 1)[0]
        assert 'rm -f "${SNIPPET}"' in teardown
        assert "nginx -t" in teardown
        assert "systemctl reload nginx" in teardown

    def test_teardown_runs_once_and_on_every_exit(self, text):
        assert "trap 'teardown' EXIT" in text
        teardown = text.split("teardown() {", 1)[1].split("\n}", 1)[0]
        assert "TEARDOWN_DONE" in teardown

    def test_the_activator_is_called_non_interactively(self, text):
        assert "LORDS_NONINTERACTIVE=1" in text
        assert "LORDS_KEEP_SECRETS_ON_ROLLBACK=1" in text

    def test_no_secret_is_printed(self, code):
        for line in code:
            stripped = line.strip()
            if stripped.startswith(("log ", "warn ", "echo ", "printf ")):
                assert "TOKEN" not in stripped or "TOKEN_FILE" in stripped, stripped

    def test_the_token_is_never_an_argument(self, code):
        for line in code:
            assert "--token " not in line, line

    def test_it_checks_the_expected_sha(self, text):
        assert "LORDS_EXPECT_SHA" in text
        assert "rev-parse HEAD" in text

    def test_it_prints_only_the_four_promised_lines(self, text):
        block = text.split("То, что видит владелец", 1)[1].split("Ожидание", 1)[0]
        assert "URL:" in block and "Код:" in block
        assert "Срок:" in block and "Статус:" in block


class TestActivatorNonInteractiveMode:
    @pytest.fixture(scope="class")
    def text(self):
        return ACTIVATOR.read_text(encoding="utf-8")

    def test_non_interactive_reads_the_secret_files(self, text):
        assert "LORDS_NONINTERACTIVE" in text
        assert 'cat "${TOKEN_FILE}"' in text

    def test_non_interactive_still_requires_rights(self, text):
        assert "LORDS_RIGHTS_CONFIRMED" in text

    def test_rollback_can_keep_correctly_saved_credentials(self, text):
        rollback = text.split("rollback() {", 1)[1].split("\non_error()", 1)[0]
        assert "LORDS_KEEP_SECRETS_ON_ROLLBACK" in rollback


class TestNginxIncludeHook:
    def test_the_site_config_includes_the_activation_directory(self):
        from factory.lords import staging
        site = next(s for s in staging.sites() if s.site_id == "lords-01")
        assert f"include {staging.ACTIVATION_DIR}/*.conf;" in staging.nginx_phase2(site)

    def test_the_directory_is_inside_the_lords_tree(self):
        from factory.lords import staging
        assert staging.ACTIVATION_DIR.startswith("/etc/nginx/lords")


def test_write_secret_atomic_never_leaves_a_readable_window(tmp_path):
    """Права выставляются до записи содержимого, а не после."""
    target = tmp_path / "deep" / "secret"
    web_intake.write_secret_atomic(target, "value")
    assert target.read_text(encoding="utf-8") == "value"
    assert oct(target.stat().st_mode)[-3:] == "600"
    assert oct(target.parent.stat().st_mode)[-3:] == "700"


def test_write_secret_atomic_is_idempotent(tmp_path):
    target = tmp_path / "secret"
    web_intake.write_secret_atomic(target, "first")
    web_intake.write_secret_atomic(target, "second")
    assert target.read_text(encoding="utf-8") == "second"
    assert len(list(tmp_path.iterdir())) == 1, "остались временные файлы"
