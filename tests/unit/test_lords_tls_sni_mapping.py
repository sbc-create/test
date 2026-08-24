"""REQ-LORDS-STAGING: каждому домену — свой сертификат и свой SNI.

Приёмка падала на `lordfilm47.space` с ошибкой curl (60): предъявленный
сертификат не содержал этого имени. Причина не в конфигурации — три файла
phase2 структурно одинаковы, — а в том, что запрос обслуживал не тот server
block: при несовпадении SNI nginx отдаёт запрос в `default_server`, а он на
этом хосте принадлежит соседу и предъявляет его сертификат.

Здесь проверяется именно это соответствие, отдельно для каждого из трёх
доменов, и проверяется исполнением: поднимается настоящий TLS-сервер с
заданным сертификатом, и функции сценария спрашивают у него имя.

Отдельно закрывается ловушка, на которой такая проверка легко становится
пустышкой: `openssl x509 -checkhost` возвращает 0 и при совпадении, и при
несовпадении — вердикт есть только в выводе.
"""

from __future__ import annotations

import contextlib
import json
import socket
import ssl
import subprocess
import threading

import pytest

from factory.lords import staging as staging_mod
from factory.paths import PATHS

SCRIPT = PATHS.root / "automation/host/lords-staging-apply.sh"
HEADER_END = "[[ ${EUID} -eq 0 ]] || die"

DOMAINS = [
    ("lords-01", "lordfilm47.space", "www.lordfilm47.space"),
    ("lords-02", "lordserial33.biz", "www.lordserial33.biz"),
    ("lords-03", "1lordserials1.online", "www.1lordserials1.online"),
]


def header() -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    return text[: text.index(HEADER_END)]


def make_cert(tmp_path, names, stem):
    """Самоподписанный сертификат на перечисленные имена."""
    crt, key = tmp_path / f"{stem}.crt", tmp_path / f"{stem}.key"
    san = ",".join(f"DNS:{n}" for n in names)
    subprocess.run(
        ["openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048", "-days", "2",
         "-keyout", str(key), "-out", str(crt), "-subj", f"/CN={names[0]}",
         "-addext", f"subjectAltName={san}"],
        capture_output=True, check=True, timeout=120,
    )
    return crt, key


class TLSStand:
    """Настоящий TLS-сервер на петле: отвечает одним и тем же сертификатом."""

    def __init__(self, crt, key):
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(str(crt), str(key))
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def _handle(self, raw):
        # Таймаут обязателен: клиент завершает рукопожатие и может ничего не
        # прислать. Без него поток встал бы на recv и держал очередь.
        raw.settimeout(5)
        try:
            with self.context.wrap_socket(raw, server_side=True) as tls:
                with contextlib.suppress(TimeoutError, OSError):
                    tls.recv(1024)
                tls.sendall(b"HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n")
        except (ssl.SSLError, OSError):
            pass
        finally:
            with contextlib.suppress(OSError):
                raw.close()

    def _serve(self):
        self.sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                raw, _ = self.sock.accept()
            except (TimeoutError, OSError):
                continue
            # Каждое соединение — свой поток: проверки идут одна за другой, и
            # застрявшее рукопожатие не должно блокировать следующую.
            threading.Thread(target=self._handle, args=(raw,), daemon=True).start()

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=5)
        self.sock.close()


def call_helper(tmp_path, function, *args):
    """Вызывает функцию сценария как есть, подключив его заголовок."""
    header_file = tmp_path / "header.sh"
    header_file.write_text(header(), encoding="utf-8")
    quoted = " ".join(f'"{a}"' for a in args)
    script = f'source "{header_file}"\nif {function} {quoted}; then echo MATCH; else echo NOMATCH; fi\n'
    result = subprocess.run(
        ["/bin/bash", "-c", script], capture_output=True, text=True, timeout=120
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Ловушка openssl: код возврата ничего не значит
# ---------------------------------------------------------------------------
class TestCheckhostTrap:
    def test_openssl_checkhost_exits_zero_even_on_mismatch(self, tmp_path):
        """Если это когда-нибудь изменится, cert_covers можно упростить."""
        crt, _key = make_cert(tmp_path, ["a.example"], "a")
        result = subprocess.run(
            ["openssl", "x509", "-in", str(crt), "-noout", "-checkhost", "b.example"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, "поведение openssl изменилось"
        assert "does NOT match" in result.stdout

    def test_cert_covers_reads_the_verdict_not_the_exit_code(self, tmp_path):
        crt, _key = make_cert(tmp_path, ["a.example", "www.a.example"], "a")
        assert call_helper(tmp_path, "cert_covers", str(crt), "a.example") == "MATCH"
        assert call_helper(tmp_path, "cert_covers", str(crt), "www.a.example") == "MATCH"
        assert call_helper(tmp_path, "cert_covers", str(crt), "b.example") == "NOMATCH"

    def test_cert_covers_rejects_a_missing_file(self, tmp_path):
        assert call_helper(tmp_path, "cert_covers", str(tmp_path / "нет.pem"), "a.example") == "NOMATCH"

    def test_the_helpers_are_stable_under_pipefail(self, tmp_path):
        """Вердикт не должен зависеть от кода возврата звеньев конвейера.

        `openssl s_client` завершается ненулевым кодом и при успешном
        рукопожатии, а `set -o pipefail` в сценарии брал именно его. Из-за
        этого совпадение периодически превращалось в отказ — проверка была
        недетерминированной, а значит бесполезной.
        """
        crt, key = make_cert(tmp_path, ["a.example", "www.a.example"], "stable")
        with TLSStand(crt, key) as stand:
            endpoint = f"127.0.0.1:{stand.port}"
            verdicts = {
                call_helper(tmp_path, "origin_cert_covers", "a.example", endpoint)
                for _ in range(12)
            }
        assert verdicts == {"MATCH"}, f"вердикт нестабилен: {verdicts}"

    def test_helpers_do_not_end_in_a_grep_pipeline(self):
        """Конвейер здесь и делал проверку недетерминированной."""
        text = SCRIPT.read_text(encoding="utf-8")
        for name in ("cert_covers()", "origin_cert_covers()"):
            body = text.split(name, 1)[1].split("\n}", 1)[0]
            assert "| grep -q" not in body, f"{name} снова заканчивается конвейером"


# ---------------------------------------------------------------------------
# Соответствие SNI и сертификата — отдельно по каждому домену
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("site_id", "apex", "www"), DOMAINS, ids=[d[1] for d in DOMAINS])
class TestPerDomainMapping:
    def test_the_domain_gets_its_own_certificate(self, tmp_path, site_id, apex, www):
        """Свой сертификат — совпадает; чужие имена — нет."""
        crt, key = make_cert(tmp_path, [apex, www], site_id)
        with TLSStand(crt, key) as stand:
            endpoint = f"127.0.0.1:{stand.port}"
            assert call_helper(tmp_path, "origin_cert_covers", apex, endpoint) == "MATCH"
            assert call_helper(tmp_path, "origin_cert_covers", www, endpoint) == "MATCH"

            for _other_id, other_apex, _other_www in DOMAINS:
                if other_apex == apex:
                    continue
                assert call_helper(tmp_path, "origin_cert_covers", other_apex, endpoint) == "NOMATCH", (
                    f"сертификат {apex} принят за {other_apex}"
                )

    def test_the_neighbours_certificate_is_refused_for_this_domain(self, tmp_path, site_id, apex, www):
        """Ровно наблюдавшийся отказ: origin отдаёт сертификат соседа.

        При несовпадении SNI nginx уходит в default_server, а он принадлежит
        соседу. Проверка обязана это заметить, а не пропустить.
        """
        crt, key = make_cert(tmp_path, ["yummyani.site", "www.yummyani.site"], "neighbour")
        with TLSStand(crt, key) as stand:
            endpoint = f"127.0.0.1:{stand.port}"
            assert call_helper(tmp_path, "origin_cert_covers", apex, endpoint) == "NOMATCH"
            assert call_helper(tmp_path, "origin_cert_covers", www, endpoint) == "NOMATCH"

    def test_the_generated_config_points_at_this_domains_lineage(self, site_id, apex, www):
        """server_name и ssl_certificate в phase2 принадлежат одному домену."""
        site = next(s for s in staging_mod.sites() if s.site_id == site_id)
        config = staging_mod.nginx_phase2(site)

        assert f"server_name {apex};" in config, f"нет отдельного блока для {apex}"
        assert f"server_name {www};" in config, f"нет отдельного блока для {www}"

        lineages = {
            line.split()[-1].rstrip(";")
            for line in config.splitlines()
            if line.strip().startswith("ssl_certificate ")
        }
        assert lineages == {f"/etc/letsencrypt/live/{apex}/fullchain.pem"}, lineages

        # Ни одного упоминания чужого домена: конфигурация не должна их знать.
        for _other_id, other_apex, _other_www in DOMAINS:
            if other_apex != apex:
                assert other_apex not in config, f"{site_id} упоминает {other_apex}"

    def test_the_registry_agrees_with_the_config(self, site_id, apex, www):
        site = next(s for s in staging_mod.sites() if s.site_id == site_id)
        assert site.apex == apex
        assert site.www == www


# ---------------------------------------------------------------------------
# Как приёмка ходит в origin
# ---------------------------------------------------------------------------
class TestAcceptanceReachesTheOrigin:
    def test_every_https_check_pins_to_the_local_origin(self):
        """Проверяется настроенный nginx, а не то, что окажется на маршруте."""
        text = SCRIPT.read_text(encoding="utf-8")
        acceptance = text.split('stage "публичная приёмка"', 1)[1]
        for line in acceptance.splitlines():
            if "https://" in line and "curl" in line:
                assert "--resolve" in line or "curl_code" in line, line

    def test_tls_verification_is_never_disabled(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "curl" not in line:
                continue
            assert " -k" not in line, line
            assert "--insecure" not in line, line

    def test_the_resolve_target_is_the_loopback(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "--resolve" in line:
                assert ":443:127.0.0.1" in line, line

    def test_a_curl_failure_is_reported_instead_of_being_glued_to_the_status(self):
        """Прежняя форма давала «000000» и прятала настоящую ошибку.

        Смотрим только исполняемые строки: в комментарии прежний вид описан
        намеренно, чтобы причина не потерялась.
        """
        text = SCRIPT.read_text(encoding="utf-8")
        assert "curl-error:" in text
        code = [
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        ]
        for line in code:
            assert "|| echo 000" not in line, line

    def test_the_script_waits_for_tls_before_accepting(self):
        """Reload асинхронен: старые воркеры ещё отвечают старой конфигурацией."""
        text = SCRIPT.read_text(encoding="utf-8")
        assert "origin_cert_covers" in text
        wait = text.index("ожидание TLS после перезагрузки nginx")
        accept = text.index('stage "публичная приёмка"')
        assert wait < accept, "ожидание идёт после приёмки"


# ---------------------------------------------------------------------------
# Сертификаты переиспользуются, а не выпускаются заново
# ---------------------------------------------------------------------------
class TestCertificateReuse:
    def test_an_existing_covering_certificate_is_reused(self):
        text = SCRIPT.read_text(encoding="utf-8")
        block = text.split("stage \"выпуск сертификатов\"", 1)[1]
        assert "переиспользую" in block
        assert 'cert_covers "${chain}" "${apex}"' in block
        assert 'cert_covers "${chain}" "${www}"' in block

    def test_a_mismatched_lineage_is_refused_rather_than_reissued(self):
        """Перевыпуск съел бы лимит CA и потерял текущую линию."""
        text = SCRIPT.read_text(encoding="utf-8")
        block = text.split("stage \"выпуск сертификатов\"", 1)[1]
        assert "не покрывает" in block
        refusal = block.index("не покрывает")
        issuance = block.index("certbot certonly")
        assert refusal < issuance or "die" in block[:issuance], (
            "несовпавшая линия должна останавливать сценарий, а не перевыпускаться"
        )

    def test_certbot_keeps_what_is_still_valid(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "--keep-until-expiring" in text

    def test_the_three_lineages_are_distinct(self):
        paths = set()
        for site_id, _apex, _www in DOMAINS:
            site = next(s for s in staging_mod.sites() if s.site_id == site_id)
            config = staging_mod.nginx_phase2(site)
            paths |= {
                line.split()[-1].rstrip(";")
                for line in config.splitlines()
                if line.strip().startswith("ssl_certificate ")
            }
        assert len(paths) == 3, f"домены делят линии сертификатов: {paths}"


class TestRepeatRunIsIdempotent:
    """Повторный запуск после отката не выпускает сертификаты заново."""

    LOOP = """
set -Eeuo pipefail
source "{header}"
certbot() {{ printf 'ВЫЗВАН certbot %s\\n' "$*" >> "{calls}"; return 0; }}
chain="{chain}"
apex="{apex}"
www="{www}"
if [[ -s "${{chain}}" ]]; then
  if cert_covers "${{chain}}" "${{apex}}" && cert_covers "${{chain}}" "${{www}}"; then
    echo REUSED
    exit 0
  fi
  echo MISMATCH
  exit 0
fi
certbot certonly --webroot -d "${{apex}}" -d "${{www}}"
echo ISSUED
"""

    def _run(self, tmp_path, chain, apex, www):
        header_file = tmp_path / "header.sh"
        header_file.write_text(header(), encoding="utf-8")
        calls = tmp_path / "certbot-calls.log"
        calls.touch()
        script = self.LOOP.format(
            header=header_file, calls=calls, chain=chain, apex=apex, www=www
        )
        result = subprocess.run(
            ["/bin/bash", "-c", script], capture_output=True, text=True, timeout=120
        )
        return result.stdout.strip(), calls.read_text(encoding="utf-8")

    @pytest.mark.parametrize(("site_id", "apex", "www"), DOMAINS, ids=[d[1] for d in DOMAINS])
    def test_a_covering_certificate_is_reused_without_calling_certbot(
        self, tmp_path, site_id, apex, www
    ):
        crt, _key = make_cert(tmp_path, [apex, www], site_id)
        verdict, calls = self._run(tmp_path, crt, apex, www)
        assert verdict == "REUSED", verdict
        assert calls == "", f"certbot вызван при существующем сертификате: {calls}"

    def test_a_lineage_that_covers_only_the_apex_is_not_silently_accepted(self, tmp_path):
        """Именно такая линия и дала бы ошибку имени у www."""
        apex, www = "lordfilm47.space", "www.lordfilm47.space"
        crt, _key = make_cert(tmp_path, [apex], "apex-only")
        verdict, calls = self._run(tmp_path, crt, apex, www)
        assert verdict == "MISMATCH", verdict
        assert calls == "", "несовпавшая линия не должна перевыпускаться автоматически"

    def test_a_foreign_lineage_is_not_accepted(self, tmp_path):
        """Сертификат соседа на месте нашей линии — отказ, а не молчание."""
        crt, _key = make_cert(tmp_path, ["yummyani.site", "www.yummyani.site"], "foreign")
        verdict, _calls = self._run(
            tmp_path, crt, "lordfilm47.space", "www.lordfilm47.space"
        )
        assert verdict == "MISMATCH", verdict


def test_staging_payload_lists_exactly_the_three_domains():
    ids = [(s.site_id, s.apex, s.www) for s in staging_mod.sites()]
    assert ids == DOMAINS, json.dumps(ids, ensure_ascii=False)
