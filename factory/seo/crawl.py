"""Обход реального HTTP: проверяет то, что нельзя доказать по файлам.

Статусы, цепочки редиректов, canonical, robots/noindex, битые внутренние ссылки,
orphan-страницы, глубину, прямое открытие страницы N и согласованность sitemap.
"""
from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from factory.seo.model import Finding, Report

LINK_RE = re.compile(r'<a\s[^>]*href="([^"]+)"', re.I)
CANONICAL_RE = re.compile(r'<link rel="canonical" href="([^"]+)"', re.I)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
ROBOTS_RE = re.compile(r'<meta name="robots" content="([^"]+)"', re.I)
BREADCRUMB_RE = re.compile(r'class="breadcrumbs"', re.I)
CARD_LINK_RE = re.compile(r'<li class="card">\s*<a class="card-link" href="([^"]+)"', re.I)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


@dataclass
class Response:
    status: int
    headers: dict
    body: str
    location: str | None = None


class Crawler:
    def __init__(self, base_url: str, *, auth: str = "", max_pages: int = 500, timeout: int = 10) -> None:
        self.base = base_url.rstrip("/")
        self.auth = auth
        self.max_pages = max_pages
        self.timeout = timeout
        self.opener = urllib.request.build_opener(_NoRedirect)

    def fetch(self, path: str) -> Response:
        url = path if path.startswith("http") else self.base + path
        request = urllib.request.Request(url, headers={"User-Agent": "factory-seo-crawler/1.0"})
        if self.auth:
            request.add_header("Authorization", "Basic " + base64.b64encode(self.auth.encode()).decode())
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                body = response.read()
                return Response(response.status, dict(response.headers), body.decode("utf-8", "replace"),
                                response.headers.get("Location"))
        except urllib.error.HTTPError as exc:
            body = exc.read()
            return Response(exc.code, dict(exc.headers), body.decode("utf-8", "replace"), exc.headers.get("Location"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return Response(0, {}, f"transport error: {exc}")


def _text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value)).strip()


def crawl(base_url: str, build_dir: Path, *, auth: str = "", environment: str = "staging") -> Report:
    report = Report("seo-crawl")
    config = json.loads((build_dir / "routes.json").read_text(encoding="utf-8"))
    expected = {r["path"]: r for r in config["routes"]}
    max_depth = int(config.get("max_depth") or 4)
    redirects = {r["source"]: r for r in config.get("redirects", [])}
    crawler = Crawler(base_url, auth=auth)

    seen: dict[str, int] = {}
    titles: dict[str, list[str]] = {}
    h1s: dict[str, list[str]] = {}
    queue: deque[tuple[str, int]] = deque([("/", 0)])
    visited_links: set[str] = set()
    fetched = 0

    while queue and fetched < crawler.max_pages:
        path, depth = queue.popleft()
        if path in seen:
            continue
        seen[path] = depth
        response = crawler.fetch(path)
        fetched += 1

        if response.status == 0:
            report.add(Finding("transport", "critical", path, response.body))
            continue

        route = expected.get(path)
        if route is None:
            if path in redirects:
                if response.status != redirects[path]["status"]:
                    report.add(Finding("redirect", "critical", path, f"Ожидался {redirects[path]['status']}, получен {response.status}."))
                continue
            if response.status != 404:
                report.add(Finding("unknown-url", "major", path, f"URL не описан в сборке, но отвечает {response.status}."))
            continue

        if response.status != route["status"]:
            report.add(Finding("status", "critical", path, f"Ожидался {route['status']}, получен {response.status}."))
            continue

        indexable = route["indexable"] and route["status"] == 200
        header_robots = response.headers.get("X-Robots-Tag", "")
        meta_robots = (ROBOTS_RE.search(response.body) or [None, ""])[1] if ROBOTS_RE.search(response.body) else ""
        canonical = (CANONICAL_RE.search(response.body) or [None, None])[1] if CANONICAL_RE.search(response.body) else None

        if indexable:
            if not canonical:
                report.add(Finding("canonical", "critical", path, "Нет self-canonical на живой indexable-странице.", "HR-1"))
            elif not canonical.endswith(path):
                report.add(Finding("canonical", "critical", path, f"Canonical «{canonical}» не соответствует URL.", "HR-1"))
            if environment == "production" and "noindex" in (header_robots + meta_robots):
                report.add(Finding("robots", "critical", path, "Индексируемая страница отдаёт noindex."))
            title = _text((TITLE_RE.search(response.body) or [None, ""])[1] if TITLE_RE.search(response.body) else "")
            titles.setdefault(title, []).append(path)
            h1_all = H1_RE.findall(response.body)
            if len(h1_all) != 1:
                report.add(Finding("h1", "critical", path, f"H1 на странице: {len(h1_all)} (нужен ровно один)."))
            else:
                h1s.setdefault(_text(h1_all[0]), []).append(path)
            if route["page_type"] not in ("home",) and not BREADCRUMB_RE.search(response.body):
                report.add(Finding("breadcrumbs", "major", path, "Нет видимых хлебных крошек."))
        else:
            if response.status == 200 and "noindex" not in (header_robots + meta_robots):
                report.add(Finding("robots", "critical", path, "Неиндексируемая страница не отдаёт noindex."))

        if depth > max_depth and indexable:
            report.add(Finding("depth", "major", path, f"Глубина {depth} превышает бюджет пакета ({max_depth})."))

        for href in LINK_RE.findall(response.body):
            if href.startswith(("http://", "https://", "mailto:", "tel:", "#", "javascript:")):
                continue
            target = urllib.parse.urljoin(path, href).split("#")[0]
            visited_links.add(target)
            if target not in seen:
                queue.append((target, depth + 1))

    # битые ссылки
    for link in sorted(visited_links):
        clean = link.split("?")[0]
        if clean in expected or clean in redirects:
            continue
        response = crawler.fetch(link)
        if response.status >= 400:
            report.add(Finding("broken-link", "critical", link, f"Внутренняя ссылка отвечает {response.status}."))

    # цепочки редиректов: раньше метрика redirect_chains считалась, но ничего не измеряла
    for redirect in config.get("redirects", []):
        hops, location, status = 0, redirect["source"], None
        while hops < 5:
            response = crawler.fetch(location)
            status = response.status
            if status not in (301, 302, 307, 308):
                break
            hops += 1
            location = response.location or ""
            if not location:
                report.add(Finding("redirect", "critical", redirect["source"], f"Редирект {status} без заголовка Location."))
                break
        if hops > 1:
            report.add(Finding("redirect", "critical", redirect["source"],
                               f"Цепочка из {hops} редиректов до {location} — допускается ровно один переход."))
        elif status is not None and status >= 400:
            report.add(Finding("redirect", "critical", redirect["source"], f"Редирект ведёт на {status}."))

    # out-of-range пагинация проверяется воротами, а не только роутером стенда
    parents = {r.get("parent") for r in config["routes"] if r["page_type"] == "paginated_page" and r.get("parent")}
    for parent in sorted(p for p in parents if p):
        total = 1 + sum(1 for r in config["routes"] if r.get("parent") == parent)
        for suffix, label in ((f"page/{total + 5}/", "вне диапазона"), ("page/abc/", "нечисловая"),
                              ("page/0/", "нулевая")):
            response = crawler.fetch(parent + suffix)
            if response.status != 404:
                report.add(Finding("pagination", "critical", parent + suffix,
                                   f"{label} страница пагинации отвечает {response.status} вместо 404.", "HR-5"))

    # прямое открытие страницы N без прохода по ссылкам
    for route in config["routes"]:
        if route["page_type"] == "paginated_page":
            direct = Crawler(base_url, auth=auth).fetch(route["path"])
            if direct.status != 200:
                report.add(Finding("pagination", "critical", route["path"], f"Прямое открытие страницы пагинации даёт {direct.status}.", "HR-5"))

    # дубли по живым страницам
    for _title, paths in titles.items():
        if len(paths) > 1:
            report.add(Finding("duplicate-title", "critical", paths[0], f"Одинаковый title на {len(paths)} живых страницах."))
    for _h1, paths in h1s.items():
        if len(paths) > 2:
            report.add(Finding("duplicate-h1", "minor", paths[0], f"Одинаковый H1 на {len(paths)} страницах."))

    # orphan: indexable-страницы, до которых обход не дошёл
    for route in config["routes"]:
        if route["indexable"] and route["status"] == 200 and route["path"] not in seen:
            report.add(Finding("orphan", "critical", route["path"], "Страница недостижима обходом обычных ссылок.", "HR-7"))

    # sitemap
    sitemap = crawler.fetch("/sitemap.xml")
    if environment == "production":
        if sitemap.status != 200:
            report.add(Finding("sitemap", "critical", "/sitemap.xml", f"Sitemap недоступен: {sitemap.status}.", "HR-3"))
        else:
            locs = re.findall(r"<loc>([^<]+)</loc>", sitemap.body)
            for loc in locs:
                if loc.endswith(".xml"):
                    child = crawler.fetch(urllib.parse.urlparse(loc).path)
                    locs.extend(re.findall(r"<loc>([^<]+)</loc>", child.body))
            for loc in locs:
                if loc.endswith(".xml"):
                    continue
                path = urllib.parse.urlparse(loc).path
                route = expected.get(path)
                if route is None or not route["indexable"] or route["status"] != 200:
                    report.add(Finding("sitemap", "critical", loc, "В sitemap попал неиндексируемый URL или URL со статусом ≠200.", "HR-3"))
    else:
        if sitemap.status == 200:
            report.add(Finding("sitemap", "critical", "/sitemap.xml", "Staging публикует sitemap — staging-URL не должны попадать в индекс.", "HR-8"))

    robots = crawler.fetch("/robots.txt")
    if environment != "production" and "Disallow: /" not in robots.body:
        report.add(Finding("robots", "critical", "/robots.txt", "Staging robots.txt не запрещает обход."))
    if environment == "production" and "Sitemap:" not in robots.body:
        report.add(Finding("robots", "critical", "/robots.txt", "В production robots.txt нет ссылки на канонический sitemap."))

    report.counts = {
        "fetched": fetched,
        "unique_urls": len(seen),
        "max_depth": max(seen.values()) if seen else 0,
        "titles": len(titles),
        "internal_links": len(visited_links),
    }
    return report
