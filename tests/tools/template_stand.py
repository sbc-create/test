#!/usr/bin/env python3
"""Стенд шаблонов: каждый шаблон направления на своём порту, без пакета сайта.

Отличие от `tests/tools/lords_stand.py` — в том, что он поднимает. Тот стенд
поднимает четыре **сайта**: у каждого есть пакет в `sites/`, домен, счётчик и
решение об индексации. Этот поднимает **шаблоны**: манифест плюс синтетический
каталог, и больше ничего. Поэтому новый шаблон виден в браузере до того, как о
нём принято хоть одно решение владельца, и проверка состава главной не ждёт
появления сайта.

Порты 8811 и далее, по алфавиту манифестов, только петлевой интерфейс.
Раскладка портов и объявленный состав блоков пишутся в
`var/artifacts/template-stand.json`: браузерная проверка читает состав оттуда,
а не повторяет его у себя — иначе она проверяла бы собственную копию манифеста.
"""

from __future__ import annotations

import argparse
import json
import socketserver
import sys
import tempfile
import threading
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.lords import serve as serve_mod  # noqa: E402
from factory.templates import contract  # noqa: E402
from factory.templates import fixture as fixture_mod  # noqa: E402

HOST = "127.0.0.1"
FIRST_PORT = 8811


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):  # noqa: ARG002
        pass


class ThreadingWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
    """Тот же однопоточный дефект wsgiref, что и у стенда сайтов: браузер держит
    keep-alive и тянет подресурсы параллельно, а занятое соединение блокирует
    весь сайт целиком."""

    daemon_threads = True


def manifests(extra: list[str] | None = None) -> list[dict]:
    out = [contract.load_manifest(p) for p in contract.manifest_paths()]
    for path in extra or []:
        out.append(contract.load_manifest(Path(path)))
    return sorted(out, key=lambda m: str(m.get("profile") or ""))


def plan(extra: list[str] | None = None) -> dict:
    """Раскладка портов и объявленный состав блоков. Без сборки страниц.

    Нужна отдельно от `stand()` потому, что браузерная проверка читает состав
    блоков раньше, чем поднимается стенд: файлы тестов загружаются до старта
    webServer, и на первом прогоне читать было бы нечего.
    """
    entries = []
    for index, manifest in enumerate(manifests(extra)):
        layout = manifest.get("layout") or {}
        entries.append({
            "profile": str(manifest.get("profile") or ""),
            "port": FIRST_PORT + index,
            "url": f"http://{HOST}:{FIRST_PORT + index}/",
            "home_blocks": list(layout.get("home_blocks") or []),
            "columns": dict(layout.get("columns") or {}),
            "breakpoints": list(contract.BREAKPOINTS),
        })
    return {"host": HOST, "templates": entries}


def stand(extra: list[str] | None = None, *, workdir: Path) -> dict:
    """Собирает шаблоны и раскладывает их по портам. Ничего не слушает."""
    data = plan(extra)
    by_name = {str(m.get("profile") or ""): m for m in manifests(extra)}
    for entry in data["templates"]:
        manifest = by_name[entry["profile"]]
        base = workdir / entry["profile"]
        base.mkdir(parents=True, exist_ok=True)
        site = fixture_mod.render_fixture_site(manifest, base=base)
        entry["pages"] = len(site.html_paths())
        entry["app"] = serve_mod.Application(site)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="append", default=[],
                        help="дополнительный манифест, ещё не записанный в blueprints/")
    parser.add_argument("--out", default="var/artifacts/template-stand.json")
    parser.add_argument("--plan-only", action="store_true",
                        help="записать раскладку и выйти, ничего не собирая и не слушая")
    args = parser.parse_args()

    if args.plan_only:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan(args.manifest), ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"раскладка шаблонов записана: {out}")
        return 0

    workdir = Path(tempfile.mkdtemp(prefix="template-stand-"))
    data = stand(args.manifest, workdir=workdir)
    servers = []
    for entry in data["templates"]:
        server = make_server(HOST, entry["port"], entry.pop("app"),
                             server_class=ThreadingWSGIServer, handler_class=QuietHandler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for entry in data["templates"]:
        print(json.dumps(entry, ensure_ascii=False), flush=True)
    print(f"стенд шаблонов поднят: {len(servers)}", flush=True)
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
