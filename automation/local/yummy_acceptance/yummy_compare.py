"""Сверка собственного опубликованного каталога домена Yummy со всеми частями его карты.

Вход: <d>-catalog.json (+ <d>-extra.json), снимок частей <d>__*.xml.
Выход: <d>-compare.json и строка итога. Чужие домены эталоном не служат.
"""
import json, re, sys, glob, os, random, urllib.request

D = sys.argv[1]
SAMPLE = int(sys.argv[2]) if len(sys.argv) > 2 else 30
UA = {"User-Agent": "sf-seo-audit/1.0"}

cat = json.load(open(f"{D}-catalog.json"))
T = dict(cat["titles"]); S = dict(cat["seasons"])
if os.path.exists(f"{D}-extra.json"):
    ex = json.load(open(f"{D}-extra.json"))
    T.update(ex["titles"]); S.update(ex["seasons"])

def self_ok(r, path):
    return (r.get("status") == 200 and (r.get("canonical") or "").rstrip("/") == f"https://{D}{path}".rstrip("/")
            and "noindex" not in (r.get("robots") or ""))

own_t, bad_t = set(), {}
for sl, r in T.items():
    if self_ok(r, f"/anime/{sl}"): own_t.add(sl)
    else: bad_t[sl] = {k: r.get(k) for k in ("status", "canonical", "robots")}
own_s, own_e, bad_s = set(), set(), {}
for k, r in S.items():
    sl, n = k.rsplit("/", 1)
    if sl not in own_t: continue
    if r.get("status") not in (200, "from_title_page") or (r.get("status") == 200 and not self_ok(r, f"/anime/{sl}/season/{n}")):
        bad_s[k] = {x: r.get(x) for x in ("status", "canonical", "robots")}; continue
    own_s.add((sl, n))
    for e in r["episodes"]:
        own_e.add((sl, n, str(e)))

sm_t, sm_s, sm_e = set(), set(), set()
for f in glob.glob(f"{D}__*.xml"):
    part = f.split("__")[1]
    if part in ("index.xml", "images.xml", "static.xml"): continue
    for u in re.findall(r"<loc>([^<]+)</loc>", open(f).read()):
        m = re.match(rf"https://{re.escape(D)}/anime/([^/]+)(?:/season/(\d+)(?:/episode/(\d+))?)?$", u)
        if not m: continue
        a, b, c = m.groups()
        if c: sm_e.add((a, b, c))
        elif b: sm_s.add((a, b))
        else: sm_t.add(a)

res = {
    "domain": D, "crawl_started": cat.get("started"), "crawl_finished": cat.get("finished"),
    "own": {"titles": len(own_t), "seasons": len(own_s), "episodes": len(own_e)},
    "sitemap": {"titles": len(sm_t), "seasons": len(sm_s), "episodes": len(sm_e)},
    "titles_not_indexable": len(bad_t), "seasons_not_indexable": len(bad_s),
    "missing": {"titles": sorted(own_t - sm_t), "seasons": sorted("/".join(x) for x in own_s - sm_s),
                "episodes_count": len(own_e - sm_e)},
    "extra_in_sitemap": {"titles": sorted(sm_t - own_t), "seasons": sorted("/".join(x) for x in sm_s - own_s),
                         "episodes": sorted("/".join(x) for x in sm_e - own_e)[:500],
                         "episodes_count": len(sm_e - own_e)},
}
miss_e = sorted(own_e - sm_e)
by_t = {}
for a, b, c in miss_e: by_t[a] = by_t.get(a, 0) + 1
res["missing"]["episodes_by_title_top"] = sorted(by_t.items(), key=lambda x: -x[1])[:30]
res["missing"]["titles_with_missing_episodes"] = len(by_t)
res["extra_in_sitemap"]["titles_reason"] = {sl: bad_t.get(sl, "нет в каталоге") for sl in res["extra_in_sitemap"]["titles"][:200]}

# Выборка пропущенных серий на сайте: допустимы ли (200, index, canonical на себя).
random.seed(20261021)
smp = random.sample(miss_e, min(SAMPLE, len(miss_e)))
chk = []
for a, b, c in smp:
    u = f"https://{D}/anime/{a}/season/{b}/episode/{c}"
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60)
        h = r.read().decode("utf-8", "replace"); st = r.status
    except urllib.error.HTTPError as e:
        h, st = "", e.code
    can = (re.findall(r'<link rel="canonical" href="([^"]+)"', h) or [None])[0]
    rb = (re.findall(r'<meta name="robots" content="([^"]+)"', h) or [None])[0]
    chk.append({"url": u, "status": st, "canonical_self": (can or "").rstrip("/") == u.rstrip("/"), "robots": rb,
                "h1": bool(re.search(r"<h1", h)), "player": ("iframe" in h or "player" in h.lower())})
res["missing_episode_sample"] = {"seed": 20261021, "n": len(chk),
                                 "allowed": sum(1 for x in chk if x["status"] == 200 and x["canonical_self"] and "noindex" not in (x["robots"] or "")),
                                 "rows": chk}
json.dump(res, open(f"{D}-compare.json", "w"), ensure_ascii=False, indent=1)
print(D, "own", res["own"], "sitemap", res["sitemap"], "missing t/s/e", len(res["missing"]["titles"]),
      len(res["missing"]["seasons"]), res["missing"]["episodes_count"], "extra t/s/e", len(res["extra_in_sitemap"]["titles"]),
      len(res["extra_in_sitemap"]["seasons"]), res["extra_in_sitemap"]["episodes_count"],
      "sample allowed", res["missing_episode_sample"]["allowed"], "/", len(chk))
