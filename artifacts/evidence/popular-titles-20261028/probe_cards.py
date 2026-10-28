"""Живая проверка карточек: статус, canonical, robots, плеер/постер, присутствие в поиске сайта.

python3 probe_cards.py <host> <out.json> <slug> [<slug> ...]
Пробы по одной, с меткой User-Agent factory-seo-acceptance; только GET.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (factory-seo-acceptance; popular-titles-20261028)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def card(host, slug):
    url = f"https://{host}/title/{slug}/"
    st, html = get(url)
    canon = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', html)
    robots = re.search(r'<meta[^>]+name="robots"[^>]+content="([^"]+)"', html)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    desc = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html)
    name = re.sub(r"<[^>]+>", "", h1.group(1)).strip() if h1 else None
    # Поиск сайта по точному названию: карточка среди совпадений (до «Возможно, вы искали» не считаем).
    q = name or slug
    sst, shtml = get(f"https://{host}/search/?q={urllib.parse.quote(q)}")
    res = shtml.split("Совпадений:", 1)[1] if "Совпадений:" in shtml else ""
    links = re.findall(r'href="/title/([^/"]+)/"', res)
    order = list(dict.fromkeys(links))
    return {
        "url": url, "status": st,
        "canonical": canon.group(1) if canon else None,
        "canonical_self": bool(canon and canon.group(1) == url),
        "robots": robots.group(1) if robots else None,
        "title": title.group(1).strip() if title else None,
        "h1": name, "description": desc.group(1) if desc else None,
        "player": bool(re.search(r"player|плеер|iframe", html, re.I)),
        "search": {"query": q, "status": sst, "position": order.index(slug) + 1 if slug in order else None,
                   "results_seen": len(order)},
    }


def main():
    host, out, slugs = sys.argv[1], sys.argv[2], sys.argv[3:]
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows = []
    for s in slugs:
        rows.append(card(host, s))
    json.dump({"host": host, "started": stamp, "finished": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "user_agent": UA, "cards": rows}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in rows:
        print(r["status"], r["canonical_self"], r["robots"], r["search"]["position"], r["url"], "|", r["h1"])


main()
