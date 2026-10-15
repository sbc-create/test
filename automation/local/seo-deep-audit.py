"""Глубокий аудит витрин (только чтение): перелинковка, кликабельность жанров/тегов,
метаданные, canonical, пагинация, битые переходы, мобильные страницы.

python3 automation/local/seo-deep-audit.py var/seo-audit/deep-<дата>.json [домен ...]
"""
import concurrent.futures as cf
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from seo_operator import tech_backlog  # noqa: E402

DESK = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36 seo-audit"
MOB = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Mobile Safari/537.36 seo-audit"
LINKS_PER_SITE = 150


class _Без(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OP = urllib.request.build_opener(_Без)


def get(url, ua=DESK):
    t = time.time()
    try:
        with OP.open(urllib.request.Request(url, headers={"User-Agent": ua}), timeout=40) as о:
            return о.status, о.headers.get("Location") or "", о.read(1_500_000).decode("utf-8", "replace"), dict(о.headers), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location") or "", "", dict(e.headers or {}), time.time() - t
    except Exception as e:  # noqa: BLE001
        return -1, str(e)[:80], "", {}, time.time() - t


def meta(тело, hdr):
    def m(rx):
        x = re.search(rx, тело, re.S | re.I)
        return html.unescape(x.group(1)).strip() if x else None
    return {
        "title": m(r"<title[^>]*>(.*?)</title>"),
        "desc": m(r'<meta name="description" content="([^"]*)"'),
        "canonical": m(r'<link rel="canonical" href="([^"]*)"'),
        "robots": m(r'<meta name="robots" content="([^"]*)"'),
        "xrobots": hdr.get("X-Robots-Tag") or hdr.get("x-robots-tag"),
        "h1": len(re.findall(r"<h1[\s>]", тело)),
        "viewport": m(r'<meta name="viewport" content="([^"]*)"'),
        "next": m(r'<link rel="next" href="([^"]*)"'),
        "prev": m(r'<link rel="prev" href="([^"]*)"'),
    }


def ссылки(домен, тело):
    итог = []
    for h in re.findall(r'<a\b[^>]*\bhref="([^"#]+)"', тело):
        h = html.unescape(h)
        if h.startswith(f"https://{домен}"):
            h = h[len(f"https://{домен}"):] or "/"
        if h.startswith("/") and not h.startswith("//"):
            итог.append(h)
    return итог


def жанры_ld(тело):
    out = []
    for блок in re.findall(r'<script type="application/ld\+json">(.*?)</script>', тело, re.S):
        try:
            d = json.loads(блок)
        except ValueError:
            continue
        for x in (d if isinstance(d, list) else [d]):
            if isinstance(x, dict):
                g = x.get("genre")
                if isinstance(g, str):
                    out.append(g)
                elif isinstance(g, list):
                    out += [s for s in g if isinstance(s, str)]
                kw = x.get("keywords")
                if isinstance(kw, str) and kw:
                    out += [("tag", s.strip()) for s in kw.split(",") if s.strip()]
    return out


def тексты_ссылок(тело):
    return {re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", t))).strip().lower()
            for t in re.findall(r"<a\b[^>]*>(.*?)</a>", тело, re.S)}


def аудит(домен):
    r = {"domain": домен, "pages": {}, "findings": []}
    F = lambda kind, url, detail: r["findings"].append({"kind": kind, "url": url, "detail": detail})
    база = f"https://{домен}"
    тела = {}

    def страница(путь, ярлык):
        код, куда, тело, hdr, dt = get(база + путь)
        м = meta(тело, hdr) if код == 200 else {}
        r["pages"][ярлык] = {"path": путь, "code": код, "location": куда, "t": round(dt, 2), **м}
        if код == 200:
            тела[путь] = тело
        return код, тело, м

    # 1. Опорные страницы
    _, главная, _ = страница("/", "home")
    _, каталог, мк = страница("/catalog/", "catalog")
    # пагинация каталога
    страницы = [int(x) for x in re.findall(r'href="/catalog/\?page=(\d+)"', каталог)]
    последняя = max(страницы) if страницы else None
    r["pages"]["catalog"]["pages_linked"] = sorted(set(страницы))[:10] + (["…", последняя] if страницы and len(set(страницы)) > 10 else [])
    if страницы:
        к2, т2, м2 = страница("/catalog/?page=2", "catalog_p2")
        if к2 == 200:
            if м2.get("canonical") and "page=2" not in м2["canonical"]:
                F("pagination_canonical", база + "/catalog/?page=2", f"canonical {м2['canonical']}")
            if м2.get("robots") and "noindex" in м2["robots"]:
                F("pagination_noindex", база + "/catalog/?page=2", м2["robots"])
            if м2.get("title") and м2["title"] == мк.get("title"):
                F("pagination_dup_title", база + "/catalog/?page=2", м2["title"][:100])
            if м2.get("desc") and м2["desc"] == мк.get("desc"):
                F("pagination_dup_desc", база + "/catalog/?page=2", (м2["desc"] or "")[:100])
        else:
            F("pagination_code", база + "/catalog/?page=2", f"код {к2}")
        кл, тл, мл = страница(f"/catalog/?page={последняя}", "catalog_last")
        if кл != 200:
            F("pagination_last", база + f"/catalog/?page={последняя}", f"код {кл}")
        elif 'href="/catalog/?page=' + str(последняя + 1) + '"' in тл:
            F("pagination_beyond_link", база + f"/catalog/?page={последняя}", f"ссылка на page={последняя + 1}")
        кз, _, мз = страница(f"/catalog/?page={(последняя or 1) + 500}", "catalog_beyond")
        if кз == 200 and not (мз.get("robots") and "noindex" in мз["robots"]):
            F("pagination_beyond_200_index", база + f"/catalog/?page={(последняя or 1) + 500}", "за последней страницей 200 и index")
        к1, куда1, _, _, _ = get(база + "/catalog/?page=1")
        r["pages"]["catalog_p1"] = {"code": к1, "location": куда1}
        if к1 == 200:
            _, _, т1, h1, _ = get(база + "/catalog/?page=1")
            м1 = meta(т1, h1)
            if not (м1.get("canonical") or "").rstrip("/").endswith("/catalog"):
                F("pagination_page1", база + "/catalog/?page=1", f"200, canonical {м1.get('canonical')}")
    # 2. Жанры: хаб и страница жанра
    жанровые = [h for h in ссылки(домен, главная + каталог) if re.search(r"/genres?/[^/?]+|[?&]genre=", h)]
    if жанровые:
        g = жанровые[0]
        кг, тг, мг = страница(g, "genre")
        if кг == 200:
            стр_г = [int(x) for x in re.findall(r'[?&](?:amp;)?page=(\d+)"', тг)]
            if стр_г:
                разд = "&" if "?" in g else "?"
                кг2, тг2, мг2 = страница(f"{g}{разд}page=2", "genre_p2")
                if кг2 == 200 and мг2.get("title") == мг.get("title"):
                    F("pagination_dup_title", база + f"{g}{разд}page=2", (мг2.get("title") or "")[:100])
                if кг2 == 200 and мг2.get("canonical") and "page=2" not in мг2["canonical"]:
                    F("pagination_canonical", база + f"{g}{разд}page=2", f"canonical {мг2['canonical']}")
    # 3. Тайтлы из карты: жанры/теги кликабельны
    код, _, индекс, _, _ = get(база + "/sitemap.xml")
    тайтлы = []
    if код == 200:
        for часть in re.findall(r"<loc>([^<]+)</loc>", индекс)[:3]:
            _, _, т, _, _ = get(html.unescape(часть))
            тайтлы += [u for u in (html.unescape(x) for x in re.findall(r"<loc>([^<]+)</loc>", т)) if "/title/" in u]
            if len(тайтлы) > 200:
                break
    выбор = тайтлы[:: max(1, len(тайтлы) // 4)][:4]
    for i, u in enumerate(выбор):
        путь = u[len(база):] if u.startswith(база) else u
        кт, тт, мт = страница(путь, f"title{i}")
        if кт != 200:
            continue
        тексты = тексты_ссылок(тт)
        for g in жанры_ld(тт):
            if isinstance(g, tuple):
                if g[1].lower() not in тексты:
                    F("tag_not_link", u, g[1])
            elif g.lower() not in тексты:
                F("genre_not_link", u, g)
    # 4. Мобильные: те же статус, canonical, title, robots; viewport
    for ярлык, p in list(r["pages"].items()):
        if p.get("code") != 200 or "path" not in p:
            continue
        км, _, тм, hм, _ = get(база + p["path"], MOB)
        мм = meta(тм, hм) if км == 200 else {}
        p["mobile"] = {"code": км, "canonical": мм.get("canonical"), "viewport": мм.get("viewport")}
        if км != 200:
            F("mobile_code", база + p["path"], f"моб {км}, десктоп 200")
            continue
        for поле in ("canonical", "title", "robots", "desc"):
            if (мм.get(поле) or "") != (p.get(поле) or ""):
                F(f"mobile_diff_{поле}", база + p["path"], f"моб «{(мм.get(поле) or '')[:70]}» ≠ «{(p.get(поле) or '')[:70]}»")
        if not мм.get("viewport") or "width=device-width" not in мм["viewport"]:
            F("mobile_viewport", база + p["path"], мм.get("viewport") or "нет")
    # 5. Метаданные опорных страниц
    for ярлык, p in r["pages"].items():
        if p.get("code") != 200 or "path" not in p:
            continue
        u = база + p["path"]
        if not p.get("title"):
            F("no_title", u, "")
        if not p.get("desc") or len(p["desc"]) < 50:
            F("short_desc", u, p.get("desc") or "нет")
        if p.get("h1") != 1:
            F("h1_count", u, str(p.get("h1")))
        if not p.get("canonical"):
            F("no_canonical", u, "")
        elif not p["canonical"].startswith(база):
            F("canonical_foreign", u, p["canonical"])
        elif "?" not in p["path"] and p["canonical"].rstrip("/") != u.rstrip("/"):
            F("canonical_other", u, p["canonical"])
    заголовки = {}
    for ярлык, p in r["pages"].items():
        if p.get("title"):
            заголовки.setdefault(p["title"], []).append(p["path"])
    for t, ps in заголовки.items():
        if len(set(ps)) > 1 and not all("page=" in x for x in ps):
            F("dup_title", база + ps[0], f"{t[:80]} — {sorted(set(ps))}")
    # 6. Битые переходы: все внутренние ссылки всех взятых страниц
    все = {}
    for путь, тело in тела.items():
        for h in ссылки(домен, тело):
            if not any(п.search(h) for п in tech_backlog.НАМЕРЕННЫЕ):
                все.setdefault(h, путь)
    r["links_total"] = len(все)
    проверено = 0
    for h, откуда in list(все.items())[:LINKS_PER_SITE]:
        к, куда, т, hdr, _ = get(база + h)
        проверено += 1
        if к >= 300 or к < 0:
            F("link_bad", база + h, f"{к} {куда} (с {откуда})")
        elif "?" not in h and tech_backlog._noindex(т):
            F("link_noindex", база + h, f"(с {откуда})")
    r["links_checked"] = проверено
    return r


def main():
    out = sys.argv[1]
    домены = sys.argv[2:] or sorted(tech_backlog.promoted_cells())
    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(аудит, домены))
    json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sites": res}, open(out, "w"), ensure_ascii=False, indent=1)
    for r in res:
        kinds = {}
        for f in r["findings"]:
            kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
        print(r["domain"], "ссылок", r.get("links_checked"), "/", r.get("links_total"), kinds, flush=True)


if __name__ == "__main__":
    main()
