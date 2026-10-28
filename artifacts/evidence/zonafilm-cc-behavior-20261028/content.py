"""Таблица использования произведений zonafilm.cc по доступным данным.

27.10: поисковые входы по странице (daily_search_landing_pages, по дням); 21–27.10: просмотры top-20.
Визиты с карточкой, намерения запуска и подтверждённые старты — не измерялись (нет отчёта/целей), пусто, а не 0.
"""
import collections, json, re, sys
S = sys.argv[1]
det = json.load(open("/srv/zonafilm-cc/data/zona-02-details.json"))
det = det.get("details", det)
ids = {s: (v.get("id"), v.get("type")) for s, v in (det.items() if isinstance(det, dict) else ((d["slug"], d) for d in det))}
cat = {i["slug"]: i for i in json.load(open("/srv/zonafilm-cc/data/zona-02-catalog.json"))["items"]}
d = json.load(open("artifacts/analytics/analytics-2026-10-28.json")); x = [x for x in d["domains"] if x["domain"] == "zonafilm.cc"][0]
M = {m["key"]: m for m in x["measurements"]}
land = collections.defaultdict(collections.Counter)
for r in M["daily_search_landing_pages"]["value"]:
    n = [z.get("name") for z in r["dimensions"]]; u = n[2].replace("https://zonafilm.cc", "")
    m = re.match(r"/title/([^/?]+)/(season-\d+/)?(episode-\d+/)?", u)
    if m: land[n[0]][(m.group(1), "серия" if m.group(3) else ("сезон" if m.group(2) else "карточка"))] += r["metrics"][0]
pv7 = {r["dimensions"][0]["name"].split("/")[2]: r["metrics"][0] for r in M["popular_pages"]["value"] if r["dimensions"][0]["name"].startswith("/title/")}
rows = []
agg = collections.Counter()
for (slug, lvl), v in land["2026-10-27"].items(): agg[slug] += v
for slug, v in agg.most_common():
    c = cat.get(slug, {}); i = ids.get(slug, (None, None))
    by = {lvl: land["2026-10-27"][(slug, lvl)] for lvl in ("карточка", "сезон", "серия") if land["2026-10-27"][(slug, lvl)]}
    rows.append({"slug": slug, "title": c.get("title"), "year": c.get("year"), "kind": c.get("kind") or "нет в каталоге", "id": i[0], "url": f"https://zonafilm.cc/title/{slug}/",
                 "search_entries_27": v, "entries_by_level": by, "pageviews_21_27_top20": pv7.get(slug), "visits_with_card": None, "play_intent": None, "confirmed_start": None})
json.dump(rows, open(S + "/zcc/content-27.json", "w"), ensure_ascii=False, indent=1)
print("произведений с поисковым входом 27.10:", len(rows), "входов:", sum(r["search_entries_27"] for r in rows))
print("по видам:", dict(collections.Counter(r["kind"] for r in rows)))
for r in rows[:15]: print(r["search_entries_27"], r["title"], r["year"], r["kind"], (r["id"] or "")[:13], r["entries_by_level"], r["pageviews_21_27_top20"])
