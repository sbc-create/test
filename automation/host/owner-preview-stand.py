#!/usr/bin/env python3
"""Предпросмотр новых семейств для владельца — только на петле, только NOINDEX.

## Почему отдельный сервер, а не «открыть порт»

Инцидент 001: два сервера предпросмотра слушали `*:3111` и `*:3210`, то есть
все интерфейсы, и отвечали HTTP 200 на публичный адрес хоста. Незавершённая
работа была открыта интернету, а страницы могли попасть в индекс дубликатами
боевых. Причина была не в злом умысле, а в умолчании. Поэтому адрес
`127.0.0.1` задан здесь явно и не может быть пропущен по невнимательности.

Доступ владельцу — туннелем, а не открытым портом:

    ssh -N -L 8901:127.0.0.1:8901 claude@<хост>

## Почему заголовок, а не правка robots в шаблоне

Витрины zona-cinema и animedia-portal собраны без домена и уже отдают
`noindex, nofollow`. Пилот basis-video отдаёт `index,follow` — так решено его
матрицей страниц. Индексируемость принадлежит полосе SEO, и менять её в
артефакте ради предпросмотра значило бы принять чужое решение молча.

Поэтому запрет ставится там, где он принадлежит предпросмотру: заголовком
`X-Robots-Tag` на каждом ответе. Артефакты остаются нетронутыми, а
индексация закрыта независимо от того, что написано в разметке.

## Что здесь НЕ происходит

Ни один из трёх шаблонов не выкладывается в production: у них нет ни siteId в
реестре Control API, ни домена, ни живого источника контента. Это предпросмотр
собранных артефактов, и он назван предпросмотром.
"""
from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import sys
from functools import partial
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_PORT = 8901

FAMILIES_ROOT = Path("/home/claude/work-templates/families")


def sources() -> dict[str, Path]:
    """Каталоги собранных витрин. Отсутствующий каталог не подменяется."""
    found: dict[str, Path] = {}
    preview = FAMILIES_ROOT / "artifacts" / "lords" / "preview"
    for name, sub in (("zona-cinema", "zona-cinema-preview"),
                      ("animedia-portal", "animedia-preview")):
        path = preview / sub
        if (path / "index.html").is_file():
            found[name] = path
    builds = FAMILIES_ROOT / "var" / "build" / "pilot-local"
    if builds.is_dir():
        ready = [d for d in builds.iterdir() if (d / "public" / "index.html").is_file()]
        if ready:
            found["basis-video"] = max(ready, key=lambda d: d.stat().st_mtime) / "public"
    return found


class Handler(http.server.SimpleHTTPRequestHandler):
    families: dict[str, Path] = {}

    def log_message(self, *args):  # noqa: ARG002 — стенд не ведёт журнал обращений
        pass

    def end_headers(self):
        # Запрет индексации ставится на КАЖДЫЙ ответ, включая 404 и статику:
        # заголовок, поставленный только на успешные страницы, оставил бы
        # открытыми ровно те адреса, которых нет в разметке.
        self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._index()
            return
        parts = self.path.lstrip("/").split("/", 1)
        family = parts[0]
        if family not in self.families:
            # Ответ собирается вручную: `send_error` кладёт пояснение в строку
            # состояния HTTP, а она обязана быть latin-1. Кириллица там роняла
            # обработчик, и запрос несуществующего адреса обрывал соединение
            # вместо честного 404.
            self._plain(404, f"Семейство «{family}» не публикуется этим стендом.")
            return
        self.directory = str(self.families[family])
        self.path = "/" + (parts[1] if len(parts) > 1 else "")
        super().do_GET()

    def _plain(self, code: int, text: str):
        body = (f'<!doctype html><html lang="ru"><head><meta charset="utf-8">'
                f'<meta name="robots" content="noindex, nofollow">'
                f"<title>{code}</title></head><body><h1>{code}</h1>"
                f"<p>{text}</p></body></html>").encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _index(self):
        rows = "".join(
            f'<li><a href="/{name}/">{name}</a> — {path}</li>'
            for name, path in sorted(self.families.items()))
        body = (
            '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            '<meta name="robots" content="noindex, nofollow">'
            "<title>Предпросмотр семейств</title></head><body>"
            "<h1>Предпросмотр собранных семейств</h1>"
            "<p>Только петлевой интерфейс. Индексация закрыта заголовком "
            "<code>X-Robots-Tag</code> на каждом ответе. Ни одна из витрин "
            "не выложена в production: у них нет ни siteId в реестре, ни "
            "домена, ни живого источника контента.</p>"
            f"<ul>{rows}</ul></body></html>").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--plan", help="куда записать карту предпросмотра")
    args = parser.parse_args()

    families = sources()
    if not families:
        print("нечего показывать: собранных витрин не найдено", file=sys.stderr)
        return 2
    Handler.families = families

    plan = {
        "base": f"http://{HOST}:{args.port}",
        "tunnel": f"ssh -N -L {args.port}:{HOST}:{args.port} claude@<хост>",
        "indexing": "закрыта заголовком X-Robots-Tag на каждом ответе",
        "production": "ни одна витрина не выложена: нет siteId, домена и живого источника",
        "families": {name: {"url": f"http://{HOST}:{args.port}/{name}/", "root": str(path)}
                     for name, path in sorted(families.items())},
    }
    if args.plan:
        Path(args.plan).parent.mkdir(parents=True, exist_ok=True)
        Path(args.plan).write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
    for name, row in plan["families"].items():
        print(f"  {name:18} {row['url']}")
    print(f"туннель: {plan['tunnel']}")

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((HOST, args.port), partial(Handler)) as httpd:
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
