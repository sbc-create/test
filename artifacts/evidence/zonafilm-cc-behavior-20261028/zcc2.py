import json, collections
cat = {i["slug"]: i for i in json.load(open("/srv/zonafilm-cc/data/zona-02-catalog.json"))["items"]}
print("kinds", collections.Counter(i["kind"] for i in cat.values()))
def M(f):
    d = json.load(open(f)); x = [x for x in d["domains"] if x["domain"] == "zonafilm.cc"][0]
    return {m["key"]: m for m in x["measurements"]}
def ptype(p):
    if p == "/": return "главная"
    if p in ("/movies/", "/series/", "/animation/", "/doramas/", "/new/", "/catalog/"): return "разделы " + p
    if p.startswith("/search"): return "поиск"
    if p.startswith("/collection"): return "подборки"
    if p.startswith("/title/"):
        s = p.split("/")[2]; k = cat.get(s, {}).get("kind", "нет в каталоге")
        return ("серия " if "/episode-" in p or "/season-" in p else "карточка ") + k
    return "прочее"
for f, lab in (("artifacts/analytics/analytics-2026-10-27.json", "20–26.10"), ("artifacts/analytics/analytics-2026-10-28.json", "21–27.10")):
    m = M(f)
    print("==", lab, "visits", m["visits"]["value"], "depth", m["page_depth"]["value"], "pv~", round(m["visits"]["value"] * m["page_depth"]["value"]))
    tot = 0
    if not m["popular_pages"]["measured"]: print("  popular_pages:", m["popular_pages"]["reason"]); continue
    for r in m["popular_pages"]["value"]:
        p = r["dimensions"][0]["name"]; v = r["metrics"][0]; tot += v
        print(f"  {int(v):6d} {p:55s} {ptype(p)}")
    print("  top20 sum", int(tot))
    print(" landing:")
    for r in m["landing_pages"]["value"]:
        p = r["dimensions"][0]["name"]; print(f"  {r['metrics']} {p} {ptype(p)}")
    print(" popular_pages meta", {k: v for k, v in m["popular_pages"].items() if k != "value"})
