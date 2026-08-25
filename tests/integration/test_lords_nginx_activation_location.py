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
    """Настоящий nginx с настоящей конфигурацией сайта Lords."""
    for name in ("logs", "client_body", "proxy", "fastcgi", "uwsgi", "scgi"):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)

    site = next(s for s in staging_mod.sites() if s.site_id == "lords-01")
    runtime, runtime_port = start_backend()
    intake, intake_port = start_backend()
    crt, key = make_cert(tmp_path, site.apex)
    htpasswd = make_htpasswd(tmp_path)
    activation_dir = tmp_path / "activation"
    activation_dir.mkdir()
    https_port = free_port()

    # Берётся конфигурация, которую фабрика генерирует на самом деле. Меняются
    # только пути и порты — то, что на тестовой машине обязано отличаться.
    server_block = staging_mod.nginx_phase2(site)
    server_block = (
        server_block
        .replace(f"/etc/letsencrypt/live/{site.apex}/fullchain.pem", str(crt))
        .replace(f"/etc/letsencrypt/live/{site.apex}/privkey.pem", str(key))
        .replace(f"ssl_trusted_certificate /etc/letsencrypt/live/{site.apex}/chain.pem;", "")
        .replace(staging_mod.HTPASSWD, str(htpasswd))
        .replace(f"{staging_mod.ACTIVATION_DIR}/*.conf", f"{activation_dir}/*.conf")
        .replace(f"http://127.0.0.1:{site.port}", f"http://127.0.0.1:{runtime_port}")
        .replace("listen 443 ssl http2;", f"listen 127.0.0.1:{https_port} ssl http2;")
        .replace("listen [::]:443 ssl http2;", "")
        .replace("listen 80;", f"listen 127.0.0.1:{free_port()};")
        .replace("listen [::]:80;", "")
        .replace("/var/log/nginx/", str(tmp_path / "logs") + "/")
    )

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
        {server_block}
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
        "port": https_port, "apex": site.apex, "activation_dir": activation_dir,
        "intake_port": intake_port, "nginx": nginx, "tmp": tmp_path,
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


def install_snippet(stand_info) -> None:
    """Тот же сниппет, который пишет сценарий на хосте."""
    (stand_info["activation_dir"] / "intake.conf").write_text(
        textwrap.dedent(f"""
            location = /__lords-activate {{
                auth_basic off;
                access_log off;
                client_max_body_size 8k;
                client_body_buffer_size 8k;
                proxy_pass http://127.0.0.1:{stand_info["intake_port"]};
                proxy_http_version 1.1;
                proxy_set_header Host $host;
            }}
        """), encoding="utf-8")


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


class TestWithTheSnippet:
    """Во время приёма: форма открыта, остальное закрыто."""

    def test_the_form_answers_200_without_basic_auth(self, stand):
        install_snippet(stand)
        assert stand["nginx"]("-s", "reload").returncode == 0
        time.sleep(0.5)

        status, headers, body = request(stand, "/__lords-activate")
        assert status == 200, f"форма отвечает {status}"
        assert "www-authenticate" not in headers, (
            "форма всё ещё требует пароль: " + str(headers)
        )
        assert body.startswith(b"backend:"), body

    def test_the_form_reaches_the_intake_not_the_site_runtime(self, stand):
        install_snippet(stand)
        stand["nginx"]("-s", "reload")
        time.sleep(0.5)
        _status, _headers, body = request(stand, "/__lords-activate")
        assert body.decode() == f"backend:{stand['intake_port']}", (
            "запрос ушёл не в приёмник"
        )

    def test_the_main_page_still_requires_a_password(self, stand):
        install_snippet(stand)
        stand["nginx"]("-s", "reload")
        time.sleep(0.5)

        status, headers, _body = request(stand, "/")
        assert status == 401, "Basic Auth сайта снят вместе с формой"
        assert "www-authenticate" in headers

    @pytest.mark.parametrize("path", ["/catalog/", "/movies/", "/title/x/", "/robots.txt"])
    def test_other_paths_stay_protected(self, stand, path):
        install_snippet(stand)
        stand["nginx"]("-s", "reload")
        time.sleep(0.5)
        status, _headers, _body = request(stand, path)
        assert status == 401, f"{path} открылся без пароля"

    def test_a_near_miss_path_is_not_opened(self, stand):
        """Точный location открывает ровно один адрес, а не префикс."""
        install_snippet(stand)
        stand["nginx"]("-s", "reload")
        time.sleep(0.5)
        for path in ("/__lords-activate/", "/__lords-activate/x", "/__lords-activateX"):
            status, _headers, _body = request(stand, path)
            assert status == 401, f"{path} открылся без пароля"


class TestAfterTeardown:
    """После снятия формы адрес снова закрыт, пароль сайта на месте."""

    def test_the_endpoint_is_protected_again(self, stand):
        install_snippet(stand)
        stand["nginx"]("-s", "reload")
        time.sleep(0.5)
        assert request(stand, "/__lords-activate")[0] == 200

        (stand["activation_dir"] / "intake.conf").unlink()
        assert stand["nginx"]("-t").returncode == 0
        assert stand["nginx"]("-s", "reload").returncode == 0
        time.sleep(0.5)

        status, headers, _body = request(stand, "/__lords-activate")
        assert status == 401, "адрес остался открытым после снятия"
        assert "www-authenticate" in headers

    def test_the_site_survives_the_empty_include(self, stand):
        """Пустой каталог include — не ошибка конфигурации."""
        assert stand["nginx"]("-t").returncode == 0
        assert request(stand, "/")[0] == 401


class TestConfigShape:
    def test_the_generated_config_carries_the_include_hook(self):
        site = next(s for s in staging_mod.sites() if s.site_id == "lords-01")
        assert f"include {staging_mod.ACTIVATION_DIR}/*.conf;" in staging_mod.nginx_phase2(site)

    def test_the_include_sits_at_server_level_not_inside_location(self):
        """Внутри `location` include подключал бы адрес под тот же пароль.

        Проверяется глубина вложенности, а не порядок строк: в файле несколько
        серверных блоков, и сравнение с первым попавшимся `location /` смотрело
        бы на блок перенаправления с порта 80, а не на нужный.
        """
        site = next(s for s in staging_mod.sites() if s.site_id == "lords-01")
        config = staging_mod.nginx_phase2(site)

        depth = 0
        found = []
        for line in config.splitlines():
            stripped = line.strip()
            if stripped.startswith("include ") and staging_mod.ACTIVATION_DIR in stripped:
                found.append(depth)
            depth += line.count("{") - line.count("}")

        assert found, "в конфигурации нет include каталога временных адресов"
        # Глубина 1 — внутри server{} и не глубже: любой location дал бы 2.
        assert all(level == 1 for level in found), (
            f"include не на уровне server: глубины {found}"
        )

    def test_the_host_script_sets_auth_basic_off(self):
        from factory.paths import PATHS
        script = (PATHS.root / "automation/host/lords-web-activation.sh").read_text(
            encoding="utf-8"
        )
        snippet = script.split('cat > "${SNIPPET}"', 1)[1]
        assert "auth_basic off;" in snippet

    def test_the_host_script_verifies_the_include_is_deployed(self):
        """Развёрнутая конфигурация могла быть записана до появления include."""
        from factory.paths import PATHS
        script = (PATHS.root / "automation/host/lords-web-activation.sh").read_text(
            encoding="utf-8"
        )
        assert "нет include" in script
        assert "lords-staging" in script, "сценарий не переустанавливает конфигурацию"

    def test_the_host_script_checks_behaviour_not_only_config(self):
        from factory.paths import PATHS
        script = (PATHS.root / "automation/host/lords-web-activation.sh").read_text(
            encoding="utf-8"
        )
        assert "FORM_CODE" in script and "MAIN_CODE" in script
