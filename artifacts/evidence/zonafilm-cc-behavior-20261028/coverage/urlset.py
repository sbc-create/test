"""Набор URL для проверки счётчика: все не-карточки карты сайта, все адреса из выгрузок Метрики (посещённые),
случайная выборка карточек (seed 20261028), подборки со страницы /collections/, сезоны/серии/пагинация/фильтры."""
import json, random, re, sys, urllib.parse, urllib.request
S = sys.argv[1]
UA = "Mozilla/5.0 factory-seo-acceptance"
sm = json.load(open(S + "/zcc/sitemap.json"))["urls"]
paths = {u.replace("https://zonafilm.cc", "") for u in sm}
cards = sorted(p for p in paths if p.startswith("/title/"))
rnd = random.Random(20261028)
pick = set(p for p in paths if not p.startswith("/title/")) | set(rnd.sample(cards, 600))
visited = set()
for f in ("artifacts/analytics/analytics-2026-10-27.json", "artifacts/analytics/analytics-2026-10-28.json"):
    d = json.load(open(f)); x = [x for x in d["domains"] if x["domain"] == "zonafilm.cc"][0]
    for m in x["measurements"]:
        if m.get("measured") and isinstance(m.get("value"), list):
            for r in m["value"]:
                for dim in r.get("dimensions", []):
                    n = dim.get("name") or ""
                    if n.startswith("https://zonafilm.cc"): n = n[len("https://zonafilm.cc"):]
                    if n.startswith("/"): visited.add(n)
h = urllib.request.urlopen(urllib.request.Request("https://zonafilm.cc/collections/", headers={"User-Agent": UA}), timeout=60).read().decode()
cols = set(re.findall(r'href="(/collection/[^"/]+/)"', h))
extra = {"/movies/?page=2", "/movies/?page=50", "/series/?page=2", "/movies/?genre=action", "/movies/?year=2025&genre=uzhasy&sort=rating",
         "/catalog/?country=ssha", "/search/?q=%D0%BE%D0%B4%D0%B8%D1%81%D1%81%D0%B5%D1%8F", "/search/?q=zzzqqq", "/search/",
         "/title/tyurma-chernyy-ostrov/season-1/", "/title/tyurma-chernyy-ostrov/season-1/episode-9/", "/title/moya-lyubov-chernoe-more/season-1/episode-2/",
         "/no-such-page-factory-check/"}
allp = sorted(pick | visited | cols | extra)
json.dump({"visited": sorted(visited), "collections": sorted(cols), "sample_cards": 600, "cards_in_sitemap": len(cards), "urls": allp}, open(S + "/zcc/urlset.json", "w"), ensure_ascii=False)
print("visited", len(visited), "collections", len(cols), "total", len(allp))
