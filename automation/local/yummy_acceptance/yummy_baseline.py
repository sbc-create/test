"""Исходные наборы пропусков Yummy: собственный каталог домена против всех частей его карты.

Запуск из каталога var/seo-audit/yummy-sitemap-20261021:  python3 yummy_baseline.py <домен> <каталог_снимка>
Пишет baseline/<домен>.json: полные списки отсутствующих сезонов и серий, все адреса карты, дубли и недопустимые адреса.
Эталон — только каталог этого же домена.
"""
import json, re, sys, glob, os, collections

D, SNAP = sys.argv[1], sys.argv[2]
OUT = sys.argv[3] if len(sys.argv) > 3 else "baseline"
cat = json.load(open(f"{D}-catalog.json"))
T = dict(cat["titles"]); S = dict(cat["seasons"])
if os.path.exists(f"{D}-extra.json"):
    ex = json.load(open(f"{D}-extra.json")); T.update(ex["titles"]); S.update(ex["seasons"])

def self_ok(r, path):
    return (r.get("status") == 200 and (r.get("canonical") or "").rstrip("/") == f"https://{D}{path}".rstrip("/")
            and "noindex" not in (r.get("robots") or ""))

own_t = {sl for sl, r in T.items() if self_ok(r, f"/anime/{sl}")}
own_s, own_e = set(), set()
for k, r in S.items():
    sl, n = k.rsplit("/", 1)
    if sl not in own_t: continue
    if r.get("status") not in (200, "from_title_page") or (r.get("status") == 200 and not self_ok(r, f"/anime/{sl}/season/{n}")):
        continue
    own_s.add(f"{sl}/{n}")
    for e in r["episodes"]: own_e.add(f"{sl}/{n}/{e}")

locs, parts = [], {}
for f in sorted(glob.glob(f"{SNAP}/{D}__*.xml")):
    part = f.split("__")[1]
    if part == "index.xml": continue
    u = re.findall(r"<loc>([^<]+)</loc>", open(f).read())
    if part == "images.xml":  # в images loc — страницы с картинками; учитываем отдельно
        continue
    parts[part] = len(u); locs += u
cnt = collections.Counter(locs)
dups = sorted(u for u, c in cnt.items() if c > 1)
sm_t, sm_s, sm_e, other, foreign = set(), set(), set(), [], []
for u in cnt:
    if not u.startswith(f"https://{D}/"): foreign.append(u); continue
    m = re.match(rf"https://{re.escape(D)}/anime/([^/?#]+)(?:/season/(\d+)(?:/episode/(\d+))?)?$", u)
    if not m: other.append(u); continue
    a, b, c = m.groups()
    if c: sm_e.add(f"{a}/{b}/{c}")
    elif b: sm_s.add(f"{a}/{b}")
    else: sm_t.add(a)

res = {"domain": D, "snapshot": SNAP, "catalog_crawl": [cat.get("started"), cat.get("finished")], "parts": parts,
       "own": {"titles": len(own_t), "seasons": len(own_s), "episodes": len(own_e)},
       "sitemap": {"titles": len(sm_t), "seasons": len(sm_s), "episodes": len(sm_e), "other": len(other), "total_locs": len(locs)},
       "duplicates": dups, "foreign_host": foreign, "non_title_urls": sorted(other),
       "missing": {"titles": sorted(own_t - sm_t), "seasons": sorted(own_s - sm_s), "episodes": sorted(own_e - sm_e)},
       "extra": {"titles": sorted(sm_t - own_t), "seasons": sorted(sm_s - own_s), "episodes": sorted(sm_e - own_e)},
       "sitemap_urls": sorted(cnt)}
os.makedirs(OUT, exist_ok=True)
json.dump(res, open(f"{OUT}/{D}.json", "w"), ensure_ascii=False)
print(D, "own", res["own"], "sitemap", res["sitemap"], "dups", len(dups), "foreign", len(foreign),
      "missing t/s/e", *(len(res["missing"][k]) for k in ("titles", "seasons", "episodes")),
      "extra t/s/e", *(len(res["extra"][k]) for k in ("titles", "seasons", "episodes")))
