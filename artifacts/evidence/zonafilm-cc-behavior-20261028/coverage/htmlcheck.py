"""Счётчик в HTML по набору URL: статус, ID, число init, tag.js, чужие счётчики, robots, canonical. По одному запросу."""
import collections, json, re, sys, time, urllib.error, urllib.parse, urllib.request
S = sys.argv[1]; UA = "Mozilla/5.0 factory-seo-acceptance"; ID = "113110481"
urls = json.load(open(S + "/zcc/urlset.json"))["urls"]
PREV = {r["p"]: r for r in json.load(open(S + "/zcc/htmlcheck.json"))} if len(sys.argv) > 2 else {}
if PREV: urls = [u for u in urls if "err" in PREV.get(u, {"err": 1})]
def tpl(p):
    if p == "/": return "главная"
    if p.startswith("/search/"): return "поиск" + (" с запросом" if "q=" in p else "")
    if p.startswith("/collections/"): return "список подборок"
    if p.startswith("/collection/"): return "подборка"
    if p.startswith("/title/"):
        if "/episode-" in p: return "серия"
        if "/season-" in p: return "сезон"
        return "карточка"
    base = p.split("?")[0]
    if "?" in p: return f"раздел {base} с параметрами" + (" (пагинация)" if "page=" in p else "")
    return f"раздел {base}"
R = []
for p in urls:
    t0 = time.time()
    try:
        r = urllib.request.urlopen(urllib.request.Request("https://zonafilm.cc" + urllib.parse.quote(p, safe="/?&=%:+"), headers={"User-Agent": UA}), timeout=40); st = r.status; h = r.read().decode("utf-8", "replace"); final = r.geturl()
    except urllib.error.HTTPError as e:
        st = e.code; h = e.read().decode("utf-8", "replace"); final = None
    except Exception as e:
        R.append({"p": p, "t": tpl(p), "err": type(e).__name__}); continue
    ids = re.findall(r'ym\(\s*(\d+)\s*,\s*["\']init', h)
    rob = re.search(r'name="robots" content="([^"]+)"', h)
    R.append({"p": p, "t": tpl(p), "status": st, "final": final and final.replace("https://zonafilm.cc", ""), "inits": ids, "tagjs": h.count("mc.yandex.ru/metrika/tag.js"),
              "noscript_pixel": h.count(f"mc.yandex.ru/watch/{ID}"), "other_ids": sorted(set(re.findall(r"mc\.yandex\.ru/watch/(\d+)", h)) - {ID}),
              "robots": rob and rob.group(1), "ms": round((time.time() - t0) * 1000)})
    time.sleep(0.15)
R = list({**PREV, **{r["p"]: r for r in R}}.values()) if PREV else R
json.dump(R, open(S + "/zcc/htmlcheck.json", "w"), ensure_ascii=False)
agg = collections.defaultdict(collections.Counter)
for r in R:
    ok = r.get("inits") == [ID] and r.get("tagjs") == 1 and not r.get("other_ids")
    agg[r["t"]]["всего"] += 1; agg[r["t"]]["счётчик верен" if ok else "ДЕФЕКТ"] += 1; agg[r["t"]][f"статус {r.get('status', r.get('err'))}"] += 1
for t, c in sorted(agg.items()): print(t, dict(c))
bad = [r for r in R if not (r.get("inits") == [ID] and r.get("tagjs") == 1 and not r.get("other_ids"))]
print("дефекты:", len(bad)); [print(" ", b) for b in bad[:15]]
