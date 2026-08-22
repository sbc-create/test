#!/usr/bin/env python3
"""Прогон ворот cross_site_uniqueness по фактически отданным страницам трёх сайтов.

Сравниваются не замыслы, а то, что сервер реально отдал: заголовки, описания, H1,
текст внутри <main> и состав индексируемых адресов из sitemap каждого сайта.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.seo import uniqueness  # noqa: E402

APP = ROOT / "blueprints" / "payload-next-multisite" / "app"
ARTIFACT = ROOT / "var" / "artifacts" / "cross-site-uniqueness.json"

HOSTS = {
    "site-a.localhost": "a",
    "site-b.localhost": "b",
    "site-c.localhost": "c",
    "site-d.localhost": "d",
    "site-e.localhost": "e",
    "site-f.localhost": "f",
    "site-g.localhost": "g",
}

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
DESCRIPTION_RE = re.compile(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', re.I)
ROBOTS_RE = re.compile(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"', re.I)
CANONICAL_RE = re.compile(r'<link[^>]+rel="canonical"[^>]+href="([^"]*)"', re.I)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
MAIN_RE = re.compile(r"<main[^>]*>(.*?)</main>", re.S | re.I)
SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
LOC_RE = re.compile(r"<loc>([^<]+)</loc>")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def fetch(port: int, host: str, path: str) -> tuple[int, str]:
    quoted = urllib.parse.quote(path, safe="/?=&:")
    request = urllib.request.Request(f"http://127.0.0.1:{port}{quoted}", headers={"Host": host})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=180) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def page_type_of(path: str) -> str:
    """Тип страницы по форме адреса: он же задаёт требования к собственному тексту."""
    if path == "/":
        return "home"
    if path in ("/catalog/", "/news/", "/collections/", "/schedule/"):
        return "listing"
    if re.fullmatch(r"/catalog/[^/]+/season-\d+/episode-\d+/", path):
        return "episode"
    if re.fullmatch(r"/catalog/[^/]+/season-\d+/", path):
        return "season"
    if re.fullmatch(r"/catalog/[^/]+/", path):
        return "title"
    if re.fullmatch(r"/news/[^/]+/", path):
        return "article"
    if re.fullmatch(r"/collections/[^/]+/", path):
        return "collection"
    if re.fullmatch(r"/legal/[^/]+/", path):
        return "legal"
    if re.fullmatch(r"/[^/]+/page/\d+/", path):
        return "listing"
    return "page"


def strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", SCRIPT_RE.sub(" ", html))).strip()


BRAND_RE = re.compile(r'<a[^>]+class="site-header__brand"[^>]*>(.*?)</a>', re.S | re.I)


def observe(port: int, host: str, site_id: str, path: str) -> uniqueness.PageObservation | None:
    status, body = fetch(port, host, path)
    if status != 200:
        return None
    robots = ROBOTS_RE.search(body)
    main = MAIN_RE.search(body)
    h1 = H1_RE.search(body)
    return uniqueness.PageObservation(
        site_id=host,
        path=path,
        page_type=page_type_of(path),
        indexable=bool(robots) and robots.group(1).strip().startswith("index"),
        title=strip_tags(TITLE_RE.search(body).group(1)) if TITLE_RE.search(body) else "",
        description=DESCRIPTION_RE.search(body).group(1) if DESCRIPTION_RE.search(body) else "",
        h1=strip_tags(h1.group(1)) if h1 else "",
        own_text=strip_tags(main.group(1)) if main else "",
        canonical=CANONICAL_RE.search(body).group(1) if CANONICAL_RE.search(body) else "",
        site_name=strip_tags(BRAND_RE.search(body).group(1)) if BRAND_RE.search(body) else "",
    )


def main() -> int:
    port = free_port()
    env = dict(os.environ)
    env.update({
        "PLAYER_PUBLISHER_ID_A": "stand-publisher-a",
        "PLAYER_PUBLISHER_ID_B": "stand-publisher-b",
        "PLAYER_PUBLISHER_ID_C": "stand-publisher-c",
        "PLAYER_PUBLISHER_ID_D": "stand-publisher-d",
        "PLAYER_PUBLISHER_ID_E": "stand-publisher-e",
        "PLAYER_PUBLISHER_ID_F": "stand-publisher-f",
        "PLAYER_PUBLISHER_ID_G": "stand-publisher-g",
        "PLAYER_MODE": "mock",
        "FACTORY_ENVIRONMENT": "staging",
    })

    seeding = subprocess.run(
        [sys.executable, str(ROOT / "tests/tools/with_app_env.py"), "--scope", "anime", "--push", "--",
         str(APP / "node_modules/.bin/tsx"), str(APP / "tests" / "stand-seed.ts")],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=900, check=False,
    )
    if seeding.returncode != 0:
        print("FAIL: не удалось наполнить стенд")
        print(seeding.stdout[-2000:], seeding.stderr[-2000:])
        return 1

    server = subprocess.Popen(
        [sys.executable, str(ROOT / "tests/tools/with_app_env.py"), "--scope", "anime",
         "--cwd", str(APP), "--", str(APP / "node_modules/.bin/next"), "dev", "-p", str(port), "-H", "127.0.0.1"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    pages: list[uniqueness.PageObservation] = []
    try:
        deadline = time.time() + 180
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=2):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            print("FAIL: сервер не открыл порт")
            return 1

        for host, site_id in HOSTS.items():
            status, sitemap = fetch(port, host, "/sitemap.xml")
            if status != 200:
                print(f"FAIL: {host} не отдал sitemap ({status})")
                return 1
            # Проверяем ровно ту поверхность, которую сайт сам объявил индексируемой.
            paths = [urllib.parse.urlparse(loc).path for loc in LOC_RE.findall(sitemap)]
            for path in paths:
                observation = observe(port, host, site_id, path)
                if observation:
                    pages.append(observation)
    finally:
        server.terminate()
        try:
            server.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
            server.communicate()

    report = uniqueness.check(pages)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"страниц собрано: {len(pages)}; индексируемых: {report.counts.get('indexable_pages')}")
    for finding in report.findings:
        print(f"{finding.severity.upper():8} {finding.rule} {finding.url}\n         {finding.message}")
    print(f"\nворота cross_site_uniqueness: {'ПРОЙДЕНЫ' if report.passed else 'ЗАБЛОКИРОВАНЫ'}; "
          f"артефакт: {ARTIFACT.relative_to(ROOT)}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
