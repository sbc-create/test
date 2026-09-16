#!/usr/bin/env python3
"""Стенд theme pack `basis-video`: собранный пилот на петлевом интерфейсе.

Отдельный стенд, а не расширение стенда направления: там профили Lords
рендерятся из манифестов на лету, здесь отдаётся готовая сборка пакета. Общий
стенд пришлось бы учить двум несовместимым способам получения страниц, и он
перестал бы отвечать за что-то одно.

Каталог сборки выбирается по времени изменения — самая свежая сборка пилота.
Придумывать идентификатор нельзя: он меняется с каждым прогоном, а
зафиксированный в коде указывал бы на сборку, которой уже нет.

Порт 8821: стенд направления занимает 8811 и далее, и пересечение диапазонов
означало бы, что один прогон молча проверяет чужие страницы.
"""
from __future__ import annotations

import http.server
import json
import socketserver
import sys
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORT = 8821
SITE = "pilot-local"


def latest_build() -> Path:
    base = ROOT / "var" / "build" / SITE
    builds = [d for d in base.iterdir() if (d / "public").is_dir()] if base.is_dir() else []
    if not builds:
        raise SystemExit(
            f"сборки {SITE} нет: сначала python3 -m factory build --site {SITE}")
    return max(builds, key=lambda d: d.stat().st_mtime) / "public"


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: ARG002 — стенд не ведёт журнал
        pass

    def do_GET(self):  # noqa: N802
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return
        super().do_GET()


def main() -> int:
    public = latest_build()
    plan = {
        "site": SITE,
        "build": public.parent.name,
        "base": f"http://127.0.0.1:{PORT}",
        # Страницы берутся из карты маршрутов сборки, а не перечисляются здесь:
        # список в коде разошёлся бы со сборкой при первом же изменении пакета.
        "pages": [],
    }
    routes = public.parent / "routes.json"
    if routes.is_file():
        data = json.loads(routes.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("routes", [])
        seen: dict[str, str] = {}
        for row in rows:
            seen.setdefault(row["page_type"], row["path"])
        plan["pages"] = [{"page_type": k, "url": f"http://127.0.0.1:{PORT}{v}"}
                         for k, v in sorted(seen.items())]
    out = ROOT / "var" / "artifacts" / "basis-stand.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"стенд basis-video: {public} → {plan['base']}, страниц {len(plan['pages'])}")

    socketserver.TCPServer.allow_reuse_address = True
    handler = partial(Handler, directory=str(public))
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
