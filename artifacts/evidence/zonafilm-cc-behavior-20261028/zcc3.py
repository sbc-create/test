import json, collections
cat = {i["slug"]: i["kind"] for i in json.load(open("/srv/zonafilm-cc/data/zona-02-catalog.json"))["items"]}
d = json.load(open("artifacts/analytics/analytics-2026-10-28.json")); x = [x for x in d["domains"] if x["domain"] == "zonafilm.cc"][0]
M = {m["key"]: m for m in x["measurements"]}
m = M["daily_search_landing_pages"]; print({k: v for k, v in m.items() if k != "value"}, len(m["value"]))
print(json.dumps(m["value"][0], ensure_ascii=False)[:400])
def t(p):
    if p == "/": return "главная"
    if p in ("/movies/",): return "/movies/"
    if p in ("/series/", "/animation/", "/doramas/", "/new/", "/catalog/"): return "прочие разделы"
    if p.startswith("/search"): return "поиск"
    if p.startswith("/collection"): return "подборки"
    if p.startswith("/title/"):
        k = cat.get(p.split("/")[2], "нет в каталоге")
        return ("серии " if "/season-" in p else "карточки ") + k
    return "прочее"
agg = collections.defaultdict(lambda: collections.Counter()); Q = collections.defaultdict(collections.Counter)
for r in m["value"]:
    dims = r["dimensions"]; names = [x.get("name") for x in dims]
    date = next(n for n in names if n and n[:4] == "2026"); import urllib.parse as U; full = next(n for n in names if n and n.startswith("http")); path = U.urlparse(full).path; Q[t(path)][full.split("zonafilm.cc",1)[1][:60]] += r["metrics"][0] if date=="2026-10-27" else 0
    agg[date][t(path)] += r["metrics"][0]
for date in sorted(agg)[-3:]:
    print(date, sum(agg[date].values()), dict(agg[date].most_common()))

for k in ("/movies/","главная","поиск","карточки Фильм","карточки Сериал","серии Сериал"):
    print(k, Q[k].most_common(6))
