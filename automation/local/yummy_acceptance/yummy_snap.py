"""Снимок индекса и всех частей карты домена: python3 yummy_snap.py <домен> <каталог>"""
import sys, os, re, urllib.request, json, hashlib, datetime
D, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "sf-seo-audit/1.0"}
g = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read()
idx = g(f"https://{D}/sitemap.xml"); open(f"{OUT}/{D}__index.xml", "wb").write(idx)
meta = {"at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "parts": {}}
for loc, lm in re.findall(r"<loc>([^<]+)</loc>(?:\s*<lastmod>([^<]+)</lastmod>)?", idx.decode()):
    name = loc.rsplit("/", 1)[1].replace("sitemap-", "").replace("sitemaps/", "")
    b = g(loc); open(f"{OUT}/{D}__{name}", "wb").write(b)
    meta["parts"][name] = {"loc": loc, "lastmod": lm, "sha12": hashlib.sha256(b).hexdigest()[:12], "bytes": len(b)}
json.dump(meta, open(f"{OUT}/{D}__meta.json", "w"), indent=1); print(D, json.dumps(meta, ensure_ascii=False))
