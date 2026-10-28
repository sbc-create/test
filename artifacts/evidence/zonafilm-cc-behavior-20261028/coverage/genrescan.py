"""Каждый пункт жанрового фильтра /movies/ и /series/: код ответа и число карточек. По одному запросу."""
import html, json, re, sys, time, urllib.error, urllib.request
UA = "Mozilla/5.0 factory-seo-acceptance"
def get(p):
    try:
        r = urllib.request.urlopen(urllib.request.Request("https://zonafilm.cc" + p, headers={"User-Agent": UA}), timeout=60); return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, ""
OUT = {}
for sec in ("/movies/", "/series/"):
    st, h = get(sec)
    m = re.search(r'<select[^>]*aria-label="Фильтр по жанру"[^>]*>(.*?)</select>', h, re.S)
    opts = [(html.unescape(v), re.sub(r"\s+", " ", html.unescape(t)).strip()) for v, t in re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)', m.group(1))]
    bad = []
    for v, t in opts[1:]:
        st, b = get(v.replace(" ", "%20")); main = b[b.find("<main"):b.find("</main>")]
        n = len(set(re.findall(r'href="/title/([^/"]+)/"', main)))
        if st != 200 or n == 0: bad.append((t, v, st, n))
        time.sleep(0.3)
    OUT[sec] = {"options": len(opts) - 1, "bad": bad}
    print(sec, "пунктов", len(opts) - 1, "плохих", len(bad)); [print("   ", b) for b in bad]
json.dump(OUT, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
