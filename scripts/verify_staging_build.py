#!/usr/bin/env python3
"""Проверка собранной витрины ДО переключения — на петле, без прав.

Смысл в том, чтобы найти неисправную сборку раньше, чем она станет боевой.
Витрина поднимается из каталога сборки на отдельном порту и отвечает на те же
запросы, что и боевая. Всё, что здесь провалится, провалилось бы и после
подмены ссылки — но уже на глазах у зрителя.

Ограничение названо прямо: сравнение с предыдущим релизом без прав root
невозможно — каталог `/srv/lords/<site>/current/site` принадлежит `lords` с
правами `drwx------`, и учётная запись сборки его не читает (проверено
фактической попыткой). Эту часть ворот выполняет фаза switch, идущая от root.

Запуск:
    .venv/bin/python scripts/verify_staging_build.py --site lords-02
"""
from __future__ import annotations

import argparse
import http.server
import json
import re
import socketserver
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "evidence" / "release"
PORT = 8931
SNAPSHOT_DIR = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache")

ROUTES = ["/", "/catalog/", "/catalog/page/2/", "/genres/", "/years/",
          "/countries/", "/new/", "/search/"]


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: ARG002
        pass


def serve(directory: Path):
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT),
                                   partial(Quiet, directory=str(directory)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def fetch(path: str) -> tuple[int | None, str]:
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}" + urllib.parse.quote(path), timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError) as e:
        return None, str(e)[:120]


def pinned_digest() -> str | None:
    text = (ROOT / "automation" / "host" / "lords-canary-apply.sh").read_text(encoding="utf-8")
    m = re.search(r'readonly EXPECT_DIGEST="([0-9a-f]{64})"', text)
    return m.group(1) if m else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default="lords-02")
    args = parser.parse_args()

    staging_root = ROOT / "var" / "canary-staging"
    staging = staging_root / args.site
    receipt_path = staging_root / f"{args.site}.render.json"

    findings: list[dict] = []
    if not receipt_path.is_file():
        print(f"расписки о сборке нет: {receipt_path}")
        return 2
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    pinned = pinned_digest()
    if receipt.get("template_digest") != pinned:
        findings.append({"severity": "fail", "what": "расписка собрана на другом отпечатке",
                         "receipt": receipt.get("template_digest"), "pinned": pinned})
    if not receipt.get("pages"):
        findings.append({"severity": "fail", "what": "в расписке ноль страниц"})
    if receipt.get("rendered_by_uid") == 0:
        findings.append({"severity": "fail", "what": "сборка шла от root"})

    snapshot = SNAPSHOT_DIR / f"{args.site}.json"
    raw = json.loads(snapshot.read_text(encoding="utf-8"))
    items = raw.get("items") if isinstance(raw, dict) else raw
    expected = len(items or [])

    gates = subprocess.run(
        [sys.executable, str(ROOT / "automation" / "host" / "lords-canary-gates.py"),
         str(staging), str(snapshot), ""],
        capture_output=True, text=True)
    gate_report: dict = {}
    if gates.stdout.strip():
        try:
            gate_report = json.loads(gates.stdout)
        except ValueError:
            gate_report = {"raw": gates.stdout[:400]}
    if gates.returncode != 0:
        findings.append({"severity": "fail", "what": "ворота содержимого не сошлись",
                         "stderr": gates.stderr.strip()[:400]})

    httpd = serve(staging)
    routes: dict = {}
    duration: dict = {}
    try:
        for path in ROUTES:
            status, body = fetch(path)
            routes[path] = {"status": status, "bytes": len(body),
                            "cards": body.count('class="card') if body else 0}
            if status != 200:
                findings.append({"severity": "fail", "what": f"{path} ответил {status}"})
        # Дефект, ради которого собиралась версия 3: ложный ноль у серий.
        _, catalog = fetch("/catalog/")
        titles = re.findall(r'href="(/title/[^"]+)"', catalog)[:20]
        zero_pages, checked, values = 0, 0, set()
        for title in titles:
            status, html = fetch(title)
            if status != 200:
                continue
            checked += 1
            found = re.findall(r"<span>(\d+)\s*мин</span>", html)
            values.update(found)
            if any(v == "0" for v in found):
                zero_pages += 1
        duration = {"pages_checked": checked, "pages_with_zero": zero_pages,
                    "distinct_values": sorted(values)}
        if zero_pages:
            findings.append({"severity": "fail",
                             "what": f"«0 мин» осталось на {zero_pages} страницах "
                                     "из осмотренных — версия 3 не помогла"})
    finally:
        httpd.shutdown()

    payload = {
        "artifact": "STAGING_BUILD_VERIFICATION",
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "site_id": args.site,
        "receipt": receipt,
        "snapshot_items_now": expected,
        "gates_without_previous_release": gate_report,
        "gates_limitation": (
            "сравнение с предыдущим релизом невозможно без прав root: каталог "
            "/srv/lords/<site>/current/site принадлежит lords с правами "
            "drwx------. Эту часть выполняет фаза switch"),
        "routes": routes,
        "episode_duration": duration,
        "findings": findings,
        "verdict": "FAIL" if any(f["severity"] == "fail" for f in findings) else "PASS",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"staging-verification.{args.site}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"расписка: страниц {receipt.get('pages')}, отпечаток "
          f"{(receipt.get('template_digest') or '')[:16]}, записей "
          f"{receipt.get('content_snapshot_items')}")
    print(f"снимок сейчас: {expected} записей")
    for path, row in routes.items():
        print(f"  {path:20} {row['status']}  карточек {row['cards']}")
    print(f"  длительность серий: осмотрено {duration.get('pages_checked')}, "
          f"страниц с нулём {duration.get('pages_with_zero')}, "
          f"значения {duration.get('distinct_values', [])[:6]}")
    for f in findings:
        print(f"  [{f['severity']}] {f['what']}")
    print(f"\n  вердикт: {payload['verdict']}")
    return 0 if payload["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
