"""Статический линт сборки: проверяет артефакты до подъёма сервера.

Проверяет то, что можно доказать по файлам: canonical, robots, дубли title/H1/
description, соответствие матрице, состав sitemap, разметку JSON-LD, пагинацию,
отсутствие staging/test-URL в production-артефактах.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

from factory.seo import matrix as matrix_mod
from factory.seo.model import Finding, Report

TAG_RE = {
    "title": re.compile(r"<title>(.*?)</title>", re.S | re.I),
    "canonical": re.compile(r'<link rel="canonical" href="([^"]+)"', re.I),
    "robots": re.compile(r'<meta name="robots" content="([^"]+)"', re.I),
    "description": re.compile(r'<meta name="description" content="([^"]*)"', re.I),
    "h1": re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I),
}
JSONLD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
HREFLANG_RE = re.compile(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', re.I)
OG_URL_RE = re.compile(r'<meta property="og:url" content="([^"]+)"', re.I)

#: Поля VideoObject, допустимые без отдельного подтверждения contract.
JSONLD_VIDEO_ALLOWED = {"@context", "@type", "name", "description", "url"}
LINK_RE = re.compile(r'<a\s[^>]*href="([^"]+)"', re.I)
STAGING_HINT_RE = re.compile(r"(localhost|127\.0\.0\.1|staging|\.test\b|demo|lorem ipsum)", re.I)


def _text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value)).strip()


def lint(build_dir: Path, *, environment: str = "staging") -> Report:
    report = Report("seo-lint")
    routes_file = build_dir / "routes.json"
    if not routes_file.exists():
        report.add(Finding("build", "critical", "-", "routes.json отсутствует: сборка неполна."))
        return report
    config = json.loads(routes_file.read_text(encoding="utf-8"))
    routes = config["routes"]
    base_url = str(config.get("base_url", "")).rstrip("/")
    site_host = urllib.parse.urlparse(base_url).netloc.lower()
    public = build_dir / "public"
    matrix_types = {p["id"]: p for p in matrix_mod.load().get("page_types", [])}
    url_policy = matrix_mod.url_policy()
    forbidden_params = set(url_policy.get("forbidden_in_url") or [])
    redirect_sources = {r["source"]: r.get("target", "") for r in config.get("redirects", [])}
    today = time.strftime("%Y-%m-%d", time.gmtime())
    allowed_video_fields = set(config.get("allowed_video_fields") or [])

    titles: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, list[str]] = defaultdict(list)
    by_path = {r["path"]: r for r in routes}
    incoming: Counter[str] = Counter()

    for route in routes:
        url, page_type = route["path"], route["page_type"]
        policy = matrix_types.get(page_type)
        if policy is None:
            report.add(Finding("matrix", "critical", url, f"Тип страницы «{page_type}» отсутствует в матрице.", "HR-*"))
            continue
        if route["status"] not in (policy.get("http_status") or [200]):
            report.add(Finding("status", "critical", url, f"Статус {route['status']} не разрешён матрицей для типа «{page_type}» ({policy.get('http_status')}).", "HR-4"))
        # Формат адреса объявлен матрицей (`case`, `word_separator`) и до сих пор
        # не проверялся ничем: сборки ему соответствовали, потому что так устроен
        # генератор, а не потому, что кто-то следил. Заглавная буква или
        # подчёркивание рождают вторую версию той же страницы — ровно то, от чего
        # рядом защищают `trailing_slash` и `page_one_url`.
        if url_policy.get("case") == "lower" and url != url.lower():
            report.add(Finding("url-policy", "critical", url,
                               f"Адрес содержит заглавные буквы, политика матрицы — «{url_policy['case']}»."))
        separator = url_policy.get("word_separator")
        if separator == "-" and "_" in url:
            report.add(Finding("url-policy", "critical", url,
                               "Адрес содержит «_», политика матрицы — разделитель «-»."))
        if not route.get("file"):
            continue
        html = (public / route["file"]).read_text(encoding="utf-8")

        title = _text((TAG_RE["title"].search(html) or [None, ""])[1] if TAG_RE["title"].search(html) else "")
        h1_matches = TAG_RE["h1"].findall(html)
        canonical = (TAG_RE["canonical"].search(html) or [None, None])[1] if TAG_RE["canonical"].search(html) else None
        robots = (TAG_RE["robots"].search(html) or [None, ""])[1] if TAG_RE["robots"].search(html) else ""
        description = (TAG_RE["description"].search(html) or [None, ""])[1] if TAG_RE["description"].search(html) else ""

        # H1
        if len(h1_matches) != 1:
            report.add(Finding("h1", "critical", url, f"Ожидается ровно один H1, найдено {len(h1_matches)}."))
        # canonical
        indexable = route["indexable"] and route["status"] == 200
        if indexable:
            if not canonical:
                report.add(Finding("canonical", "critical", url, "Индексируемая страница без self-canonical.", "HR-1"))
            elif not canonical.startswith("https://"):
                report.add(Finding("canonical", "critical", url, f"Canonical не абсолютный: {canonical}", "HR-1"))
            else:
                canonical_host = urllib.parse.urlparse(canonical).netloc.lower()
                if site_host and canonical_host != site_host:
                    # Раньше сравнивался только хвост URL, поэтому canonical на чужой
                    # домен проходил проверку целиком.
                    report.add(Finding("canonical", "critical", url,
                                       f"Canonical указывает на чужой домен «{canonical_host}» вместо «{site_host}».", "HR-2"))
                # Сравнивается путь целиком, а не хвост: «/arhiv/lekcii/material-01/»
                # заканчивается на «/lekcii/material-01/», и проверка по суффиксу
                # принимала canonical на другую страницу того же сайта.
                elif (urllib.parse.urlparse(canonical).path or "/") != url:
                    report.add(Finding("canonical", "critical", url, f"Canonical «{canonical}» не совпадает с собственным URL.", "HR-1"))
            # F-4.2: отсутствие description у индексируемой страницы раньше не замечалось
            if not description.strip():
                report.add(Finding("description", "critical", url, "Индексируемая страница без meta description."))
            # F-4.3: OG-URL обязан совпадать с каноническим
            og_url_match = OG_URL_RE.search(html)
            if og_url_match and canonical and og_url_match.group(1) != canonical:
                report.add(Finding("og", "critical", url,
                                   f"og:url «{og_url_match.group(1)}» расходится с canonical «{canonical}»."))
            if not title:
                report.add(Finding("title", "critical", url, "Пустой title у индексируемой страницы."))
            titles[title].append(url)
            if description:
                descriptions[description].append(url)
            if "noindex" in robots:
                report.add(Finding("robots", "critical", url, "Страница помечена indexable, но содержит noindex."))
        else:
            if "noindex" not in robots and route["status"] == 200 and page_type not in ("service",):
                report.add(Finding("robots", "critical", url, f"Неиндексируемая страница без noindex (robots=«{robots}»)."))
            if canonical and page_type in ("search", "filter_non_indexable"):
                report.add(Finding("canonical", "major", url, "У noindex-страницы задан self-canonical — сигналы противоречивы."))
        # sitemap
        if route["in_sitemap"] and not indexable:
            report.add(Finding("sitemap", "critical", url, "URL включён в sitemap, но не является indexable 200.", "HR-3"))
        # soft 404
        if route["status"] == 200 and indexable:
            body = re.search(r"<main[^>]*>(.*?)</main>", html, re.S)
            if body and len(_text(body.group(1))) < 40:
                report.add(Finding("soft404", "critical", url, "Индексируемая страница практически без содержимого (soft 404).", "HR-4"))
        # JSON-LD
        for block in JSONLD_RE.findall(html):
            try:
                data = json.loads(block)
            except json.JSONDecodeError as exc:
                report.add(Finding("jsonld", "critical", url, f"JSON-LD не парсится: {exc}"))
                continue
            if data.get("@type") == "VideoObject":
                # Матч по префиксу: рендер добавляет к классу модификатор соотношения
                # сторон, и точное сравнение никогда не срабатывало.
                if 'class="player-frame' not in html:
                    report.add(Finding("jsonld", "critical", url, "VideoObject размечен на странице без видимого плеера.", "HR-6"))
                unexpected = set(data) - JSONLD_VIDEO_ALLOWED - allowed_video_fields
                if unexpected:
                    report.add(Finding("jsonld", "critical", url,
                                       f"В VideoObject поля вне разрешённых contract: {', '.join(sorted(unexpected))}.", "HR-6"))
            # Пустой список типов в матрице означает «никакой разметки», а не «любая».
            declared_types = set((matrix_types.get(page_type) or {}).get("structured_data") or [])
            emitted = data.get("@type")
            if emitted:
                simple = {t.split("_")[0] for t in declared_types}
                allowed_here = emitted in simple or any(emitted in t for t in declared_types)
                if not allowed_here:
                    report.add(Finding("jsonld", "critical", url,
                                       f"Тип {emitted} не разрешён матрицей для «{page_type}» "
                                       f"(разрешено: {', '.join(sorted(declared_types)) or 'ничего'}).", "HR-6"))
        # содержимое staging в production
        if environment == "production" and STAGING_HINT_RE.search(html):
            report.add(Finding("production-purity", "critical", url, "В production-сборке найден staging/demo/placeholder-маркер.", "HR-8"))
        # внутренние ссылки: считаем входящие и проверяем каноничность формы
        for href in LINK_RE.findall(html):
            if not href.startswith("/"):
                continue
            # для связности считаем чистый путь, а параметры и якорь проверяем отдельно
            incoming[href.split("#")[0].split("?")[0]] += 1
            if href != href.lower():
                report.add(Finding("link-canonicality", "critical", url,
                                   f"Внутренняя ссылка не в каноничном регистре: {href}"))
            path_only = href.split("#")[0].split("?")[0]
            # Ссылка на источник редиректа — лишний хоп на каждом клике к
            # странице, конечный адрес которой известен заранее. Проверки формы
            # ссылки рядом закрывают тот же класс: ссылка обязана вести туда,
            # куда в итоге придёт запрос.
            if path_only in redirect_sources:
                report.add(Finding("link-canonicality", "critical", url,
                                   f"Внутренняя ссылка ведёт на редирект: {href} → "
                                   f"{redirect_sources[path_only]}"))
            if url_policy.get("trailing_slash") and not path_only.endswith("/") and "." not in path_only.rsplit("/", 1)[-1]:
                report.add(Finding("link-canonicality", "critical", url,
                                   f"Внутренняя ссылка без завершающего слэша: {href} — это лишний 301"))
            for param in forbidden_params:
                if f"{param}=" in href:
                    report.add(Finding("link-canonicality", "critical", url,
                                       f"Внутренняя ссылка содержит запрещённый параметр {param}: {href}"))

        # hreflang: ссылка обязана быть взаимной и включать саму себя
        hreflangs = HREFLANG_RE.findall(html)
        if hreflangs:
            hrefs = {href for _, href in hreflangs}
            if canonical and canonical not in hrefs:
                report.add(Finding("hreflang", "critical", url,
                                   "В наборе hreflang нет ссылки на саму страницу (self-reference)."))
            langs = [lang for lang, _ in hreflangs]
            if len(set(langs)) != len(langs):
                report.add(Finding("hreflang", "critical", url, "Дублирующиеся значения hreflang."))

        # lastmod: дата из будущего означает, что она проставляется деплоем, а не контентом
        if route.get("lastmod") and str(route["lastmod"])[:10] > today:
            report.add(Finding("lastmod", "major", url,
                               f"lastmod в будущем ({route['lastmod']}): дата обязана отражать изменение контента"))

    # дубли
    for _title, urls in titles.items():
        if len(urls) > 1:
            report.add(Finding("duplicate-title", "critical", urls[0], f"Дублирующийся title на {len(urls)} страницах: {', '.join(urls[:4])}"))
    for description, urls in descriptions.items():
        if len(urls) > 1 and description:
            report.add(Finding("duplicate-description", "major", urls[0], f"Дублирующаяся description на {len(urls)} страницах: {', '.join(urls[:4])}"))

    # orphan pages
    for route in routes:
        if route["indexable"] and route["status"] == 200 and route["path"] != "/" and incoming[route["path"]] == 0:
            report.add(Finding("orphan", "critical", route["path"], "Индексируемая страница без входящих внутренних ссылок.", "HR-7"))

    # пагинация
    paginated = [r for r in routes if r["page_type"] == "paginated_page"]
    for route in paginated:
        parent = route.get("parent")
        if parent and parent not in by_path:
            report.add(Finding("pagination", "critical", route["path"], f"Родительская страница {parent} отсутствует."))
        html = (public / route["file"]).read_text(encoding="utf-8")
        if 'class="pagination"' not in html:
            report.add(Finding("pagination", "critical", route["path"], "На странице пагинации нет блока навигации по страницам.", "HR-5"))
        if not re.search(r'<a[^>]+href="[^"]*page/\d+/"', html) and not re.search(r'<a[^>]+class="page-prev"', html):
            report.add(Finding("pagination", "critical", route["path"], "Пагинация не связана обычными <a href> ссылками.", "HR-5"))
    for redirect in config.get("redirects", []):
        if redirect["source"].endswith("page/1/") and redirect["status"] != 301:
            report.add(Finding("pagination", "critical", redirect["source"], "page/1/ обязан отдавать 301 на базовый URL."))

    # Содержимое собранного sitemap проверяется независимо от окружения:
    # раньше он на staging не собирался, и правило HR-3 не проверялось ни разу.
    sitemap_dir = next((d for d in (public, build_dir / "sitemap-preview") if (d / "sitemap.xml").exists()), None)
    sitemap_urls: list[str] = []
    if sitemap_dir:
        for sitemap_file in sorted(sitemap_dir.glob("sitemap*.xml")):
            text = sitemap_file.read_text(encoding="utf-8")
            for loc in re.findall(r"<loc>([^<]+)</loc>", text):
                if loc.endswith(".xml"):
                    continue
                sitemap_urls.append(loc)
                path = urllib.parse.urlparse(loc).path
                route = by_path.get(path)
                if route is None:
                    report.add(Finding("sitemap", "critical", loc, "URL из sitemap отсутствует среди маршрутов сборки.", "HR-3"))
                elif not route["indexable"] or route["status"] != 200:
                    report.add(Finding("sitemap", "critical", loc,
                                       f"В sitemap попал URL со статусом {route['status']} / indexable={route['indexable']}.", "HR-3"))
                elif route.get("canonical") and route["canonical"] != loc:
                    report.add(Finding("sitemap", "critical", loc, "URL в sitemap не совпадает с каноническим.", "HR-3"))
        expected = {r["canonical"] for r in routes if r["in_sitemap"] and r["indexable"] and r["status"] == 200 and r.get("canonical")}
        missing = expected - set(sitemap_urls)
        if missing:
            report.add(Finding("sitemap", "critical", sorted(missing)[0],
                               f"В sitemap не попали {len(missing)} индексируемых URL.", "HR-3"))
    elif any(r["in_sitemap"] for r in routes):
        report.add(Finding("sitemap", "critical", "sitemap.xml", "Sitemap не собран, хотя маршруты помечены для включения.", "HR-3"))

    report.counts = {
        "sitemap_urls": len(sitemap_urls),
        "routes": len(routes),
        "indexable": sum(1 for r in routes if r["indexable"] and r["status"] == 200),
        "in_sitemap": sum(1 for r in routes if r["in_sitemap"]),
        "paginated": len(paginated),
        "redirects": len(config.get("redirects", [])),
    }
    return report
