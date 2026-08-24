#!/usr/bin/env python3
"""Локальный стенд направления Lords: четыре сайта на четырёх портах.

Скрипт поднимает по одному процессу-потоку на пакет и держит их, пока его не
остановят. Он нужен браузерной приёмке: проверять раскладку по HTML-строке
нельзя — перенос, переполнение и залипшая шапка видны только в движке.

Порты фиксированы и слушают только петлевой интерфейс: стенд не предназначен
никому, кроме проверяющего.
"""

from __future__ import annotations

import json
import socketserver
import sys
import threading
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

# Скрипт запускают по пути к файлу, поэтому корень репозитория в sys.path не
# попадает сам: без этой строки стенд не находит собственную фабрику.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.lords import preview as preview_mod  # noqa: E402

HOST = "127.0.0.1"
PORTS = {
    "lords-01": 8801,
    "lords-02": 8802,
    "lords-03": 8803,
    "lords-04": 8804,
}


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):  # noqa: ARG002 — лог запросов здесь только мешает
        pass


class ThreadingWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
    """Стенд, обслуживающий запросы параллельно.

    `wsgiref.simple_server` однопоточен: один запрос в единицу времени на сайт.
    Браузер держит keep-alive соединение и параллельно тянет подресурсы, поэтому
    занятое соединение блокировало весь сайт — приёмка падала по таймауту
    `page.goto`, каждый раз на новом тесте. Отказ плавал по набору и выглядел
    как дефект страницы, хотя дефект был в стенде.

    Потоки демонические: стенд останавливают снаружи, дожидаться незакрытых
    соединений на выходе не нужно.
    """

    daemon_threads = True


def main() -> int:
    servers = []
    for site_id, port in PORTS.items():
        app = preview_mod.application(site_id)
        server = make_server(
            HOST, port, app, server_class=ThreadingWSGIServer, handler_class=QuietHandler
        )
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(json.dumps({
            "site_id": site_id,
            "profile": app.site.profile,
            "url": f"http://{HOST}:{port}/",
            "pages": len(app.site.html_paths()),
        }, ensure_ascii=False), flush=True)
    print(f"стенд Lords поднят: {len(servers)} сайта(ов)", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        for server in servers:
            server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
