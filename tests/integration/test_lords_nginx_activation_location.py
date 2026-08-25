"""REQ-LORDS-WEB-INTAKE: форма открыта без пароля, остальной сайт — под паролем.

Это единственный набор, который поднимает настоящий nginx. Причина конкретная:
разбор текста конфигурации уже один раз соврал. Сниппет с временным адресом
лежал на месте, `nginx -t` проходил, сценарий рапортовал об успехе — а форма
всё равно спрашивала логин и пароль, потому что в развёрнутом
`/etc/nginx/lords/lords-01.conf` не было строки include, и точный location
просто не существовал в работающей конфигурации.

Отсюда два свойства, которые проверяются исполнением, а не чтением:

* `/__lords-activate` отвечает 200 и без заголовка WWW-Authenticate;
* любой другой адрес сайта отвечает 401 и с этим заголовком.

nginx поднимается свой, на петле, с конфигурацией во временном каталоге.
Системный nginx не затрагивается: ни его конфигурация, ни его процессы.
"""

from __future__ import annotations

import http.client
import shutil
import socket
import ssl
import subprocess
import textwrap
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from factory.lords import staging as staging_mod

NGINX = "/usr/sbin/nginx"

pytestmark = pytest.mark.skipif(
    not (Path(NGINX).exists() and shutil.which(NGINX)),
    reason="на этой машине нет nginx: проверка поведения конфигурации невозможна",
)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Backend(BaseHTTPRequestHandler):
    """Заглушка вместо рантайма и приёмника. Отвечает, кто именно ответил."""

    def log_message(self, *args):  # noqa: ARG002
        pass

    def do_GET(self):  # noqa: N802
        body = f"backend:{self.server.server_port}".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_backend() -> tuple[ThreadingHTTPServer, int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def make_cert(tmp: Path, name: str) -> tuple[Path, Path]:
    crt, key = tmp / "site.crt", tmp / "site.key"
    subprocess.run(
        ["openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048", "-days", "2",
         "-keyout", str(key), "-out", str(crt), "-subj", f"/CN={name}",
         "-addext", f"subjectAltName=DNS:{name}"],
        capture_output=True, check=True, timeout=120,
    )
    return crt, key


def make_htpasswd(tmp: Path) -> Path:
    """Файл паролей. Значение неважно: проверяется факт требования пароля."""
    target = tmp / "htpasswd"
    result = subprocess.run(
        ["openssl", "passwd", "-apr1", "irrelevant-for-this-test"],
        capture_output=True, text=True, check=True, timeout=60,
    )
    target.write_text(f"lords:{result.stdout.strip()}\n", encoding="utf-8")
    return target


@pytest.fixture
def stand(tmp_path):
    """Настоящий nginx с настоящей конфигурацией сайта Lords.

    Серверный блок лежит отдельным файлом, который основной конфиг подключает.
    Так `render()` может перерисовать его целиком — ровно то, что делает
    сценарий на хосте, — и перечитать конфигурацию.
    """
    for name in ("logs", "client_body", "proxy", "fastcgi", "uwsgi", "scgi"):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)

    site = next(s for s in staging_mod.sites() if s.site_id == "lords-01")
    runtime, runtime_port = start_backend()
    intake, intake_port = start_backend()
    crt, key = make_cert(tmp_path, site.apex)
    htpasswd = make_htpasswd(tmp_path)
    https_port = free_port()
    http_port = free_port()
    site_conf = tmp_path / "site.conf"
    marker = "lords-form-testmarker"

    def render(*, basic_auth=True, activation_port=None):
        block = staging_mod.nginx_phase2(
            site, basic_auth=basic_auth, activation_port=activation_port, marker=marker
        )
        block = (
            block
            .replace(f"/etc/letsencrypt/live/{site.apex}/fullchain.pem", str(crt))
            .replace(f"/etc/letsencrypt/live/{site.apex}/privkey.pem", str(key))
            .replace(
                f"ssl_trusted_certificate /etc/letsencrypt/live/{site.apex}/chain.pem;", ""
            )
            .replace(staging_mod.HTPASSWD, str(htpasswd))
            .replace(f"http://127.0.0.1:{site.port}", f"http://127.0.0.1:{runtime_port}")
            .replace("listen 443 ssl http2;", f"listen 127.0.0.1:{https_port} ssl http2;")
            .replace("listen [::]:443 ssl http2;", "")
            .replace("listen 80;", f"listen 127.0.0.1:{http_port};")
            .replace("listen [::]:80;", "")
            .replace("/var/log/nginx/", str(tmp_path / "logs") + "/")
        )
        site_conf.write_text(block, encoding="utf-8")

    render()

    conf = tmp_path / "nginx.conf"
    conf.write_text(textwrap.dedent(f"""
        pid {tmp_path}/nginx.pid;
        error_log {tmp_path}/logs/error.log warn;
        events {{ worker_connections 64; }}
        http {{
          access_log {tmp_path}/logs/access.log;
          client_body_temp_path {tmp_path}/client_body;
          proxy_temp_path {tmp_path}/proxy;
          fastcgi_temp_path {tmp_path}/fastcgi;
          uwsgi_temp_path {tmp_path}/uwsgi;
          scgi_temp_path {tmp_path}/scgi;
          default_type text/plain;
          include {site_conf};
        }}
    """), encoding="utf-8")

    def nginx(*args):
        return subprocess.run(
            [NGINX, "-c", str(conf), "-p", str(tmp_path), *args],
            capture_output=True, text=True, timeout=120,
        )

    check = nginx("-t")
    assert check.returncode == 0, check.stderr
    started = nginx()
    assert started.returncode == 0, started.stderr
    for _ in range(40):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", https_port)) == 0:
                break
        time.sleep(0.1)

    yield {
        "port": https_port, "apex": site.apex, "intake_port": intake_port,
        "nginx": nginx, "tmp": tmp_path, "render": render, "marker": marker,
    }

    nginx("-s", "stop")
    runtime.shutdown()
    runtime.server_close()
    intake.shutdown()
    intake.server_close()


def request(stand_info, path):
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    connection = http.client.HTTPSConnection(
        "127.0.0.1", stand_info["port"], context=context, timeout=10
    )
    connection.request("GET", path, headers={"Host": stand_info["apex"]})
    response = connection.getresponse()
    body = response.read()
    headers = {k.lower(): v for k, v in response.getheaders()}
    connection.close()
    return response.status, headers, body


class TestWithoutTheSnippet:
    """Обычное состояние: временного адреса нет."""

    def test_the_main_site_requires_a_password(self, stand):
        status, headers, _body = request(stand, "/")
        assert status == 401
        assert "www-authenticate" in headers

    def test_the_activation_path_is_also_protected_when_absent(self, stand):
        """Пока сниппета нет, адрес обслуживает общий location — под паролем."""
        status, headers, _body = request(stand, "/__lords-activate")
        assert status == 401
        assert "www-authenticate" in headers


class TestDuringTheWindow:
    """Окно приёма: пароль снят со всего сайта, форма отвечает приёмником.

    Снятие пароля целиком — осознанный размен, а не упущение: форму нельзя
    показать под паролем, которого владелец не знает. Индексация при этом
    остаётся закрытой, и проверяется это здесь же.
    """

    def open_window(self, stand):
        stand["render"](basic_auth=False, activation_port=stand["intake_port"])
        assert stand["nginx"]("-t").returncode == 0
        assert stand["nginx"]("-s", "reload").returncode == 0
        time.sleep(0.5)

    def test_the_form_answers_200_without_basic_auth(self, stand):
        self.open_window(stand)
        status, headers, body = request(stand, "/__lords-activate")
        assert status == 200, f"форма отвечает {status}"
        assert "www-authenticate" not in headers, str(headers)
        assert body.startswith(b"backend:"), body

    def test_the_form_reaches_the_intake_not_the_site_runtime(self, stand):
        self.open_window(stand)
        _status, _headers, body = request(stand, "/__lords-activate")
        assert body.decode() == f"backend:{stand['intake_port']}"

    def test_the_form_carries_the_marker_header(self, stand):
        """По маркеру сценарий отличает приёмник от сайта."""
        self.open_window(stand)
        _status, headers, _body = request(stand, "/__lords-activate")
        assert headers.get("x-lords-form") == stand["marker"], headers

    @pytest.mark.parametrize("path", ["/", "/catalog/", "/movies/", "/title/x/"])
    def test_the_site_is_open_during_the_window(self, stand, path):
        self.open_window(stand)
        status, headers, _body = request(stand, path)
        assert status == 200, f"{path} отвечает {status}"
        assert "www-authenticate" not in headers

    def test_indexing_stays_closed_during_the_window(self, stand):
        """Пароль снят, но роботам сайт по-прежнему закрыт."""
        self.open_window(stand)
        _status, headers, _body = request(stand, "/")
        assert "noindex" in (headers.get("x-robots-tag") or "")


class TestAfterTeardown:
    """После снятия формы адрес снова закрыт, пароль сайта на месте."""

    def test_the_endpoint_disappears_again(self, stand):
        stand["render"](basic_auth=False, activation_port=stand["intake_port"])
        stand["nginx"]("-s", "reload")
        time.sleep(0.5)
        assert request(stand, "/__lords-activate")[0] == 200

        stand["render"]()  # обратно: пароль на месте, формы нет
        assert stand["nginx"]("-t").returncode == 0
        assert stand["nginx"]("-s", "reload").returncode == 0
        time.sleep(0.5)

        status, headers, _body = request(stand, "/__lords-activate")
        assert status == 401, "адрес остался открытым после снятия"
        assert "www-authenticate" in headers

    def test_auth_off_without_the_form_leaves_the_address_closed(self, stand):
        """После успеха: пароль снят навсегда, но формы уже нет."""
        stand["render"](basic_auth=False, activation_port=None)
        assert stand["nginx"]("-t").returncode == 0
        stand["nginx"]("-s", "reload")
        time.sleep(0.5)
        assert request(stand, "/")[0] == 200
        # Формы нет — адрес обслуживает рантайм, а не приёмник.
        _status, _headers, body = request(stand, "/__lords-activate")
        assert body.decode() != f"backend:{stand['intake_port']}"

    def test_the_site_survives_the_empty_include(self, stand):
        """Пустой каталог include — не ошибка конфигурации."""
        assert stand["nginx"]("-t").returncode == 0
        assert request(stand, "/")[0] == 401


class TestConfigShape:
    def test_the_form_is_absent_from_the_normal_config(self):
        site = next(s for s in staging_mod.sites() if s.site_id == "lords-01")
        assert staging_mod.ACTIVATION_PATH not in staging_mod.nginx_phase2(site)

    def test_the_window_config_has_the_form_and_no_password(self):
        site = next(s for s in staging_mod.sites() if s.site_id == "lords-01")
        config = staging_mod.nginx_phase2(
            site, basic_auth=False, activation_port=1234, marker="M"
        )
        assert f"location = {staging_mod.ACTIVATION_PATH} {{" in config
        assert 'auth_basic "Lords staging";' not in config

    def test_the_host_script_verifies_the_real_nginx_before_printing(self):
        from factory.paths import PATHS
        script = (PATHS.root / "automation/host/lords-web-activation.sh").read_text(
            encoding="utf-8"
        )
        assert script.index("проверяю фактический nginx хоста") < script.index("URL:   %s")
        assert "LIVE_FORM_VERIFIED=pass" in script
        assert "LIVE_FORM_VERIFIED=fail" in script
