"""Каждый пункт фильтров жанра на разделах хоста: код, число карточек, robots. По одному запросу, метка factory-seo-acceptance.
python3 genrescan_host.py <host> <out.json> <раздел>..."""
import html, json, re, sys, time, urllib.error, urllib.parse, urllib.request
UA = "Mozilla/5.0 factory-seo-acceptance"
HOST, OUTP, SECS = sys.argv[1], sys.argv[2], sys.argv[3:]
def get(p):
    try:
        r = urllib.request.urlopen(urllib.request.Request("https://" + HOST + urllib.parse.quote(p, safe="/?&=%:+"), headers={"User-Agent": UA}), timeout=60); return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, ""
OUT = {"host": HOST, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sections": {}}
for sec in SECS:
    st, h = get(sec)
    sels = re.findall(r'<select([^>]*)>(.*?)</select>', h, re.S)
    sel = [b for a, b in sels if "жанр" in a.lower() or 'name="genre"' in a]
    if st != 200 or not sel:
        OUT["sections"][sec] = {"status": st, "genre_select": False, "selects": [a.strip()[:120] for a, b in sels]}; print(sec, st, "нет фильтра жанра", [a.strip()[:80] for a, b in sels]); continue
    opts = [(html.unescape(v), re.sub(r"\s+", " ", html.unescape(t)).strip()) for v, t in re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)', sel[0])]
    opts = [o for o in opts if o[0] and "genre" in o[0]]
    rows = []
    for v, t in opts:
        url = v if v.startswith("/") else sec + v
        st2, b = get(url); main = b[b.find("<main"):b.find("</main>")] if "<main" in b else b
        rows.append({"label": t, "url": url, "status": st2, "cards": len(set(re.findall(r'href="/title/([^/"]+)/"', main))),
                     "robots": (re.findall(r'<meta name="robots" content="([^"]+)"', b) or [None])[0]})
        time.sleep(0.3)
    bad = [r for r in rows if r["status"] != 200 or r["cards"] == 0]
    OUT["sections"][sec] = {"status": st, "options": len(rows), "dead": len(bad), "rows": rows}
    print(sec, "пунктов", len(rows), "тупиков", len(bad), "noindex", sum(1 for r in rows if r["robots"] and "noindex" in r["robots"]))
OUT["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(OUT, open(OUTP, "w"), ensure_ascii=False, indent=1)
