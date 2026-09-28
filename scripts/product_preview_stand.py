#!/usr/bin/env python3
"""Стенд предпросмотра продуктов: витрина на порт, один туннель на все.

Каждой витрине — свой порт, и это не прихоть. Страницы ссылаются на
`/assets/site.css` и `/assets/app.js` от корня, потому что витрина живёт в
корне своего домена. Первая редакция стенда отдавала их под префиксом
`/<продукт>/`, и абсолютные ссылки уходили в никуда: страницы приходили без
единого стиля, а проверка честно сообщала о горизонтальной прокрутке в 408
пикселей при ширине 390 — прокрутка была настоящей, но принадлежала
неоформленной странице, а не витрине.

Стенд слушает только петлевой интерфейс: наружу он не смотрит и смотреть не
должен.

Индексация закрыта заголовком на каждом ответе. Предпросмотр — не production и
не приёмка: у витрин нет ни домена, ни окружения, ни разрешения владельца.

Запуск:
    .venv/bin/python scripts/product_preview_stand.py [--port 8902]
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import signal
import socketserver
import sys
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

ROOT = Path(__file__).resolve().parents[1]
PREVIEW_ROOT = ROOT / "var" / "product-preview"

#: Где стенд хранит свой идентификатор процесса. В `var/`, а не в `/tmp`:
#: файл принадлежит рабочей копии и переживает уборку временного каталога.
PIDFILE = ROOT / "var" / "product-preview-stand.pid"

#: Постоянные порты витрин. Меняются только вместе с адресом, отданным
#: владельцу, — то есть осознанно.
PORTS = {
    "zona-cinema": 8903,
    "animedia-portal": 8904,
    "basis-video": 8905,
    "yummy": 8906,
}

#: Заголовки, одинаковые для всякого ответа. Индексация закрыта: предпросмотр
#: не должен попасть в поиск ни при каких обстоятельствах.
COMMON_HEADERS = (
    ("X-Robots-Tag", "noindex, nofollow"),
    ("Cache-Control", "no-store"),
    ("Referrer-Policy", "no-referrer"),
)


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):  # noqa: ARG002 — лог запросов здесь только мешает
        pass


class ThreadingWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
    """Стенд обслуживает запросы параллельно.

    Однопоточный сервер обслуживает один запрос за раз, а браузер держит
    соединение и параллельно тянет подресурсы — занятое соединение блокировало
    бы страницу целиком. Эта ошибка на фикстурном стенде уже случалась и
    выглядела как плавающий отказ страницы, а не как свойство сервера.
    """

    daemon_threads = True


def _products() -> list[str]:
    if not PREVIEW_ROOT.is_dir():
        return []
    return sorted(p.name for p in PREVIEW_ROOT.iterdir()
                  if p.is_dir() and (p / "index.html").is_file())


def _index_page(plan: dict) -> bytes:
    rows = "".join(
        f'<li><a href="{url}">{name}</a></li>' for name, url in plan["products"].items()
    ) or "<li>предпросмотры не собраны</li>"
    return (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Предпросмотр витрин</title>"
        "<style>body{font:16px/1.6 system-ui,sans-serif;margin:2rem auto;max-width:44rem;"
        "padding:0 1rem}a{color:#1a5fb4}li{margin:.4rem 0}</style></head><body>"
        "<h1>Предпросмотр витрин</h1>"
        "<p>Собранные пакеты на настоящих данных каталога. Это <strong>не "
        "production</strong> и не приёмка витрины: домена, окружения и "
        "разрешения владельца у этих витрин нет.</p>"
        "<p>У каждой витрины свой порт: страницы ссылаются на стили и скрипты "
        "от корня, и под общим префиксом они не находились бы.</p>"
        f"<ul>{rows}</ul></body></html>"
    ).encode("utf-8")


def _index_app(plan: dict):
    def application(environ, start_response):
        body = _index_page(plan)
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"),
                                  ("Content-Length", str(len(body))), *COMMON_HEADERS])
        return [body]
    return application


def _site_app(product: str):
    """Одна витрина в корне своего порта."""
    base = PREVIEW_ROOT / product

    def application(environ, start_response):
        rest = environ.get("PATH_INFO", "/").lstrip("/")
        target = base / rest if rest else base
        if target.is_dir() or rest.endswith("/") or not rest:
            target = target / "index.html"

        # Выход за пределы каталога предпросмотра запрещён: путь из запроса
        # нельзя принимать на веру.
        try:
            resolved = target.resolve()
            resolved.relative_to(base.resolve())
        except (ValueError, OSError):
            body = b"forbidden"
            start_response("403 Forbidden",
                           [("Content-Type", "text/plain; charset=utf-8"),
                            ("Content-Length", str(len(body))), *COMMON_HEADERS])
            return [body]

        if not resolved.is_file():
            fallback = base / "404.html"
            body = fallback.read_bytes() if fallback.is_file() else b"not found"
            start_response("404 Not Found",
                           [("Content-Type", "text/html; charset=utf-8"),
                            ("Content-Length", str(len(body))), *COMMON_HEADERS])
            return [body]

        body = resolved.read_bytes()
        kind = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        if kind.startswith("text/") or kind.endswith(("json", "javascript", "xml")):
            kind += "; charset=utf-8"
        start_response("200 OK", [("Content-Type", kind),
                                  ("Content-Length", str(len(body))), *COMMON_HEADERS])
        return [body]
    return application


def _probe(url: str) -> tuple[int | None, str]:
    """Отвечает ли адрес. Используется и состоянием, и самопроверкой."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, ""
    except urllib.error.HTTPError as error:
        return error.code, ""
    except Exception as error:  # noqa: BLE001 — недоступность тоже ответ
        return None, str(error)[:80]


def show_status(host: str, ports: dict) -> int:
    """Состояние стенда: процесс и ответы витрин.

    Проверяется не только корень: витрина, отдающая главную и молчащая на
    вложенном маршруте, выглядит работающей ровно до первого перехода.
    """
    pid = None
    if PIDFILE.is_file():
        try:
            pid = int(PIDFILE.read_text(encoding="utf-8").strip())
        except ValueError:
            pid = None
    alive = False
    if pid:
        try:
            os.kill(pid, 0)
            alive = True
        except OSError:
            alive = False
    print(f"процесс: {'работает' if alive else 'не найден'}"
          + (f", pid {pid}" if pid else ""))

    #: Вложенные маршруты у каждой витрины свои: у basis-video нет каталога.
    deep = {
        "zona-cinema": ["/", "/catalog/", "/genres/", "/search/"],
        "animedia-portal": ["/", "/catalog/", "/anime/", "/search/"],
        "basis-video": ["/", "/lekcii/", "/news/", "/search/"],
    }
    bad = 0
    for name, port in ports.items():
        for route in deep.get(name, ["/"]):
            url = f"http://{host}:{port}{route}"
            code, error = _probe(url)
            ok = code == 200
            bad += 0 if ok else 1
            print(f"  {'OK ' if ok else 'НЕТ'} {code or '—':>4}  {url}"
                  + (f"  {error}" if error else ""))
    return 0 if not bad else 1


def stop_stand() -> int:
    if not PIDFILE.is_file():
        print("стенд не запущен: файла с идентификатором процесса нет")
        return 0
    try:
        pid = int(PIDFILE.read_text(encoding="utf-8").strip())
    except ValueError:
        PIDFILE.unlink(missing_ok=True)
        print("файл с идентификатором повреждён — снят")
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"стенд остановлен, pid {pid}")
    except ProcessLookupError:
        print(f"процесса {pid} нет — файл снят")
    PIDFILE.unlink(missing_ok=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8902,
                        help="базовый порт; каждой витрине достаётся следующий")
    parser.add_argument("--plan", action="store_true", help="напечатать план и выйти")
    parser.add_argument("--status", action="store_true",
                        help="проверить, отвечают ли витрины, и выйти")
    parser.add_argument("--stop", action="store_true", help="остановить стенд и выйти")
    args = parser.parse_args()

    products = _products()
    #: Порт закреплён за именем продукта, а не за порядком в каталоге.
    #: Нумерация по порядку сдвигала бы адреса при появлении новой витрины, и
    #: ссылка, отданная владельцу вчера, сегодня открывала бы чужую витрину.
    ports = {name: PORTS.get(name, args.port + 90 + index)
             for index, name in enumerate(products)}
    plan = {
        "base": f"http://{args.host}:{args.port}",
        "tunnel": (f"ssh -N " + " ".join(
            f"-L {port}:127.0.0.1:{port}" for port in [args.port, *ports.values()])
            + " claude@<хост>"),
        "indexing": "закрыта заголовком X-Robots-Tag на каждом ответе",
        "acceptance": ("предпросмотр, не production: домена, окружения и разрешения "
                       "владельца у этих витрин нет"),
        "products": {name: f"http://{args.host}:{port}/" for name, port in ports.items()},
    }
    out = ROOT / "artifacts" / "evidence" / "products" / "preview-plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.status:
        return show_status(args.host, ports)
    if args.stop:
        return stop_stand()

    if args.plan:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    if not products:
        print("предпросмотры не собраны: сначала scripts/build_product_preview.py",
              file=sys.stderr)
        return 1

    import threading

    servers = []
    for name, port in ports.items():
        server = make_server(args.host, port, _site_app(name),
                             server_class=ThreadingWSGIServer, handler_class=QuietHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        print(f"  {name:18} http://{args.host}:{port}/")

    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(str(os.getpid()), encoding="utf-8")

    index = make_server(args.host, args.port, _index_app(plan),
                        server_class=ThreadingWSGIServer, handler_class=QuietHandler)
    print(f"опись: {plan['base']}")
    index.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
