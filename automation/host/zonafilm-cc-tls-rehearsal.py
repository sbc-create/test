#!/usr/bin/env python3
"""Репетиция TLS-терминации перед установкой vhost. Это НЕ публичный HTTPS.

Что это такое и чем не является
-------------------------------

Публичный `https://zonafilm.cc/` отсюда не поднимается: порт 443 требует root,
сертификат Let's Encrypt — либо root и порт 80 (HTTP-01), либо учётных данных
Cloudflare (DNS-01). Ни того, ни другого у этой сессии нет, а самоподписанный
сертификат, выданный за боевой, был бы имитацией.

Репетиция отвечает на другой, проверяемый вопрос: **как витрина поведёт себя
за TLS-терминатором**, когда владелец поставит vhost. Здесь поднимается
локальный терминатор на непривилегированном порту с одноразовым сертификатом,
который проксирует на витрину ровно те заголовки, что задаёт
`automation/host/nginx/zona-02.conf`:

    Host: zonafilm.cc
    X-Forwarded-Proto: https

и проверяется то, что ломается именно на этом стыке:

* нет петли редиректов (самая частая поломка связки «редирект на https» +
  «приложение не знает, что оно уже за https»);
* canonical содержит `https://zonafilm.cc`, а не `http://` и не чужое имя;
* `X-Robots-Tag: noindex, nofollow` доживает до клиента через прокси;
* обход дефекта с завершающим слэшом отрабатывает до витрины.

Сертификат одноразовый, живёт в каталоге, который удаляется в `finally`, и
нигде не объявляется доверенным.
"""

from __future__ import annotations

import argparse
import http.server
import json
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ВИТРИНА = ("127.0.0.1", 9123)
ДОМЕН = "zonafilm.cc"


def сделать_сертификат(каталог: Path) -> tuple[Path, Path]:
    ключ, серт = каталог / "key.pem", каталог / "cert.pem"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(ключ), "-out", str(серт), "-days", "1",
         "-subj", f"/CN={ДОМЕН}",
         "-addext", f"subjectAltName=DNS:{ДОМЕН},DNS:www.{ДОМЕН}"],
        check=True, capture_output=True)
    return ключ, серт


class Прокси(http.server.BaseHTTPRequestHandler):
    """Повторяет то, что делает vhost: слэш-редирект, затем проксирование."""

    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # тишина: вывод теста — это отчёт, а не access log
        pass

    def do_GET(self):
        путь = self.path
        разобрано = urllib.parse.urlsplit(путь)
        # Обход TEMPLATE_ZONA_BLOCKER-04 — тот же, что в location ~ ^(/[^.]*[^/])$
        if разобрано.path and разобрано.path != "/" and not разобрано.path.endswith("/") \
                and "." not in разобрано.path.rsplit("/", 1)[-1]:
            цель = разобрано.path + "/" + (("?" + разобрано.query) if разобрано.query else "")
            self.send_response(308)
            self.send_header("Location", f"https://{ДОМЕН}{цель}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        запрос = urllib.request.Request(
            f"http://{ВИТРИНА[0]}:{ВИТРИНА[1]}{путь}",
            headers={"Host": ДОМЕН, "X-Forwarded-Proto": "https",
                     "X-Forwarded-For": "127.0.0.1"})
        try:
            with urllib.request.urlopen(запрос, timeout=120) as r:
                тело, заголовки, код = r.read(), dict(r.headers), r.status
        except urllib.error.HTTPError as e:
            тело, заголовки, код = e.read(), dict(e.headers), e.code
        except Exception:
            self.send_response(502); self.send_header("Content-Length", "0")
            self.end_headers(); return
        self.send_response(код)
        for имя in ("Content-Type", "X-Robots-Tag", "X-Site-Factory-Build-Id",
                    "X-Site-Factory-Artifact-Sha256", "X-Catalog-Revision"):
            if заголовки.get(имя):
                self.send_header(имя, заголовки[имя])
        # Те же заголовки безопасности, что задаёт vhost.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Content-Length", str(len(тело)))
        self.end_headers()
        self.wfile.write(тело)


def свободный_порт() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); порт = s.getsockname()[1]; s.close()
    return порт


def пройти(url: str, контекст: ssl.SSLContext, предел: int = 6) -> dict:
    """Идёт по редиректам вручную, считая переходы: петля обязана быть видна."""
    цепочка = []
    текущий = url
    for _ in range(предел):
        разобрано = urllib.parse.urlsplit(текущий)
        conn = __import__("http.client", fromlist=["HTTPSConnection"]).HTTPSConnection(
            разобрано.hostname, разобрано.port, context=контекст, timeout=120)
        путь = разобрано.path + (("?" + разобрано.query) if разобрано.query else "")
        conn.request("GET", путь or "/", headers={"Host": ДОМЕН})
        ответ = conn.getresponse()
        тело = ответ.read()
        цепочка.append({"url": текущий, "status": ответ.status,
                        "location": ответ.getheader("Location"),
                        "x_robots_tag": ответ.getheader("X-Robots-Tag")})
        conn.close()
        if ответ.status in (301, 302, 307, 308):
            место = ответ.getheader("Location") or ""
            # Location указывает на публичное имя; в репетиции оно резолвится
            # в локальный терминатор, поэтому хост и порт подставляются обратно.
            м = urllib.parse.urlsplit(место)
            текущий = urllib.parse.urlunsplit(
                ("https", f"{разобрано.hostname}:{разобрано.port}", м.path, м.query, ""))
            continue
        return {"chain": цепочка, "final_status": ответ.status,
                "final_body": тело.decode("utf-8", "replace"), "hops": len(цепочка) - 1}
    return {"chain": цепочка, "final_status": None, "final_body": "",
            "hops": len(цепочка), "loop_suspected": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    каталог = Path(tempfile.mkdtemp(prefix="zona02-tls-"))
    отчёт: dict = {"kind": "TLS_TERMINATION_REHEARSAL",
                   "not_a_public_https": True,
                   "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    сервер = None
    try:
        ключ, серт = сделать_сертификат(каталог)
        порт = свободный_порт()
        сервер = http.server.ThreadingHTTPServer(("127.0.0.1", порт), Прокси)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=str(серт), keyfile=str(ключ))
        сервер.socket = ctx.wrap_socket(сервер.socket, server_side=True)
        threading.Thread(target=сервер.serve_forever, daemon=True).start()
        отчёт["terminator"] = f"https://127.0.0.1:{порт} (одноразовый сертификат)"

        клиентский = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        клиентский.load_verify_locations(cafile=str(серт))
        клиентский.check_hostname = False   # имя проверяется отдельной проверкой SAN ниже

        with open(серт, "rb") as f:
            отчёт["cert_san_covers_domain"] = ДОМЕН.encode() in f.read()

        проверки = {}
        for имя, путь in (("home", "/"), ("catalog", "/catalog/"),
                          ("title", "/title/razorennaya-no-obozhaemaya-princem/"),
                          ("no_slash", "/catalog")):
            r = пройти(f"https://127.0.0.1:{порт}{путь}", клиентский)
            канон = re.findall(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"',
                               r["final_body"])[:1]
            проверки[имя] = {
                "hops": r["hops"],
                "final_status": r["final_status"],
                "loop_suspected": r.get("loop_suspected", False),
                "canonical": канон,
                "x_robots_tag": r["chain"][-1]["x_robots_tag"],
                "chain": [{k: v for k, v in шаг.items() if k != "x_robots_tag"}
                          for шаг in r["chain"]],
            }
        отчёт["checks"] = проверки

        отчёт["verdict"] = {
            "no_redirect_loop": all(not v["loop_suspected"] and v["hops"] <= 1
                                    for v in проверки.values()),
            "all_200": all(v["final_status"] == 200 for v in проверки.values()),
            "canonical_https_own_domain": all(
                v["canonical"] and v["canonical"][0].startswith(f"https://{ДОМЕН}")
                for v in проверки.values()),
            "noindex_survives_proxy": all(
                (v["x_robots_tag"] or "").replace(" ", "") == "noindex,nofollow"
                for v in проверки.values()),
            "slash_fix_applied_before_origin": проверки["no_slash"]["hops"] == 1,
        }
    finally:
        if сервер is not None:
            сервер.shutdown()
        shutil.rmtree(каталог, ignore_errors=True)
        отчёт["cert_removed"] = not каталог.exists()
        отчёт["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(отчёт, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(json.dumps({"verdict": отчёт.get("verdict"),
                          "cert_removed": отчёт["cert_removed"]},
                         ensure_ascii=False, indent=2))
    return 0 if all((отчёт.get("verdict") or {}).values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
