"""Приёмка опубликованных текстов карточек списка владельца: журнал публикаций + живая страница.

python3 accept_published.py <out.json> <домен>/<slug> [...]
Для каждого: запись publish в history.jsonl, тело в published.json, на живой странице — 200, canonical на себя,
robots, фрагмент текста виден; плюс год/название записи каталога в тексте — грубая сверка идентичности.
"""
import html
import json
import re
import sys
import time
import urllib.request

UA = "Mozilla/5.0 (factory-seo-acceptance; popular-titles-20261028)"
ROOT = {"zonafilm.space": "lords", "zonafilm12.site": "lords", "animedia.icu": "animedia"}
SNAP = {"zonafilm.space": "/srv/zonafilm-space/data/zona-01-details.json",
        "zonafilm12.site": "/srv/zonafilm12-site/data/zona-03-details.json",
        "animedia.icu": "/srv/animedia-icu/data/animedia-01-details.json"}
out, rows, det = sys.argv[1], [], {}
for arg in sys.argv[2:]:
    d, s = arg.split("/", 1)
    base = f"/srv/sites/{ROOT[d]}/runtime/overlays/{d}"
    pubs = [json.loads(l) for l in open(f"{base}/history.jsonl", encoding="utf-8") if l.strip()]
    pub = [r for r in pubs if r.get("op") == "publish" and r.get("slug") == s]
    items = json.load(open(f"{base}/published.json", encoding="utf-8")).get("items") or []
    body = next((x.get("body") for x in reversed(items) if x.get("slug") == s), "") or ""
    if d not in det:
        det[d] = json.load(open(SNAP[d], encoding="utf-8"))["details"]
    v = det[d].get(s) or {}
    url = f"https://{d}/title/{s}/"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
        st, h = r.status, r.read().decode("utf-8", "replace")
    page = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h)))
    frag = re.sub(r"\s+", " ", body)[:60]
    rob = re.search(r'name="robots" content="([^"]+)"', h)
    rows.append({
        "url": url, "published_at": pub[-1]["at"] if pub else None, "author": pub[-1].get("author") if pub else None,
        "body_chars": len(body), "status": st, "canonical_self": f'href="{url}"' in h,
        "robots": rob.group(1) if rob else None, "text_on_page": bool(frag) and frag in page,
        "catalog": {"name": v.get("name"), "year": v.get("year"), "original_name": v.get("original_name")},
        "year_in_text": str(v.get("year")) in body if v.get("year") else None,
        "body_head": body[:300],
    })
    x = rows[-1]
    print(x["published_at"], st, x["canonical_self"], x["robots"], "текст на странице:", x["text_on_page"],
          "год в тексте:", x["year_in_text"], url)
json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rows": rows},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
