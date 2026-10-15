#!/usr/bin/env python3
"""Редакционный аудит публичных текстов сети (только чтение): технические пояснения на страницах.

    python3 automation/local/editorial-audit.py var/seo-audit/editorial-<дата>.json [домен ...]

На каждом домене берутся типы страниц: главная, каталог, жанр, подборки, год, тайтл, сезон,
серия, поиск без результатов, 404. Из каждой — видимый текст (шапка и подвал включительно),
<title>, meta description, og:description/twitter:description и текстовые поля JSON-LD.
Предложения с маркерами внутренней реализации выписываются с типом страницы и полем.
Маркеры — ориентиры поиска, а не правило замены: решение — по каждому месту.
"""
from __future__ import annotations

import concurrent.futures as cf
import html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MARKERS = [
    r"источник\w*", r"поставщик\w*", r"переданн\w+ данн\w+", r"выдуманн\w+", r"не угадыва\w+|не угадать|не угадан\w*",
    r"подтвержд[её]нн\w+ пол\w+", r"профил\w+ витрин\w*", r"снимк\w+ каталог\w*|снимок каталог\w*", r"сетк\w+ постер\w*",
    r"витрин\w+", r"реестр\w*", r"метк\w+ поставщик\w*|служебн\w+ метк\w+", r"по данным (?:источника|поставщика|каталога)",
    r"данн\w+ (?:поставщика|источника)", r"\bAPI\b", r"рантайм\w*", r"шаблон\w*", r"генерир\w+|сгенерир\w+",
    r"опираются на", r"не придумыва\w+|не выдумыва\w+", r"без выдумок", r"фабрик\w+", r"слаг\w*", r"идентификатор\w*",
]
RX = re.compile(r"(?i)(" + "|".join(MARKERS) + r")")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) editorial-audit"}


def get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
            return r.status, r.read(2_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(2_000_000).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return e.code, ""
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def visible(body: str) -> str:
    body = re.sub(r"(?is)<(script|style|noscript|template)\b.*?</\1>", " ", body)
    body = re.sub(r"(?s)<!--.*?-->", " ", body)
    body = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|section|header|footer|nav|dd|dt|td|th)>", "\n", body)
    return html.unescape(re.sub(r"<[^>]+>", " ", body))


def sentences(text: str) -> list[str]:
    out = []
    for block in re.split(r"\n+", text):
        block = re.sub(r"\s+", " ", block).strip()
        if not block:
            continue
        out += [s.strip() for s in re.split(r"(?<=[.!?…])\s+(?=[А-ЯA-Z«])", block) if s.strip()]
    return out


def fields(body: str) -> dict[str, list[str]]:
    f: dict[str, list[str]] = {}
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
    f["title"] = [html.unescape(re.sub(r"\s+", " ", m.group(1))).strip()] if m else []
    f["meta_description"] = [html.unescape(x) for x in re.findall(r'<meta name="description" content="([^"]*)"', body)]
    f["social"] = [html.unescape(x) for x in re.findall(r'<meta (?:property|name)="(?:og|twitter):(?:description|title)" content="([^"]*)"', body)]
    ld = []
    for blk in re.findall(r'(?is)<script type="application/ld\+json">(.*?)</script>', body):
        try:
            data = json.loads(blk)
        except ValueError:
            continue
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("description", "name", "headline", "alternativeHeadline", "abstract", "text") and isinstance(v, str):
                        ld.append(v)
                    else:
                        walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(data)
    f["jsonld"] = ld
    return f


def links(domain: str, body: str) -> list[str]:
    out = []
    for h in re.findall(r'href="([^"#]+)"', body):
        h = html.unescape(h)
        if h.startswith(f"https://{domain}"):
            h = h[len(f"https://{domain}"):] or "/"
        if h.startswith("/") and not h.startswith("//"):
            out.append(h)
    return out


def pick(ls: list[str], rx: str) -> str | None:
    return next((h for h in ls if re.search(rx, h)), None)


def audit(domain: str) -> dict:
    res = {"domain": domain, "pages": {}, "hits": []}
    code, home = get(f"https://{domain}/")
    res["reachable"] = code
    if code != 200:
        return res
    hl = links(domain, home)
    _, cat = get(f"https://{domain}/catalog/")
    cl = links(domain, cat) + hl
    pages = {"home": "/", "catalog": "/catalog/"}
    for k, rx in (("genre", r"(/genres?/[^/?]+/?$|[?&]genre=)"), ("collections", r"^/collections/?$"), ("collection", r"^/collections/[^/]+"),
                  ("year", r"(/year/\d{4}|[?&]year=\d{4})"), ("genres_hub", r"^/genres/?$"), ("schedule", r"^/schedule/?$"),
                  ("movies", r"^/(movies|films?)/?$"), ("series", r"^/series/?$"), ("new", r"^/new/?$"), ("top", r"^/top/?$")):
        p = pick(cl, rx)
        if p:
            pages[k] = p
    t = pick(cl, r"^/(title|anime)/[^/]+/?$")
    if t:
        pages["title"] = t
        _, tb = get(f"https://{domain}{t}")
        tl = links(domain, tb)
        s = pick(tl, r"/season[-/]\d+/?$")
        e = pick(tl, r"/(episode[-/]\d+|seriya)")
        if s:
            pages["season"] = s
        if e:
            pages["episode"] = e
    pages["search_empty"] = "/search/?q=%D1%8A%D1%8A%D1%8A%D1%8Bzz"
    pages["not_found"] = "/no-such-page-editorial-audit/"
    for kind, path in pages.items():
        code, body = get(f"https://{domain}{path}")
        res["pages"][kind] = {"path": path, "code": code}
        if not body or code < 0:
            continue
        seen = set()
        for field, vals in [("visible", sentences(visible(body)))] + list(fields(body).items()):
            for v in vals:
                for s in (sentences(v) if field != "visible" else [v]):
                    if RX.search(s) and (field, s) not in seen:
                        seen.add((field, s))
                        res["hits"].append({"page": kind, "path": path, "field": field, "text": s[:400],
                                            "markers": sorted({m.group(0).lower() for m in RX.finditer(s)})})
    return res


def main() -> int:
    out = sys.argv[1]
    if len(sys.argv) > 2:
        domains = sys.argv[2:]
    else:
        reg = json.load(open(ROOT / "config/analytics.json", encoding="utf-8"))["properties"]
        from seo_operator.tech_run import ВНЕ_ПРОДВИЖЕНИЯ
        domains = [p["domain"] for p in reg] + sorted(ВНЕ_ПРОДВИЖЕНИЯ)
    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(audit, domains))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in res:
        print(f"{r['domain']:24} код {r.get('reachable')} | страниц {len(r['pages'])} | находок {len(r['hits'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
