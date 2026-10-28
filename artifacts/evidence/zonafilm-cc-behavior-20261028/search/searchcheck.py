"""Проверка запросов внутреннего поиска zonafilm.cc по смыслу запроса.

Вход: JSON {запрос: визиты}. Для каждого: класс запроса, нужные произведения в каталоге (zona-02), выдача
/search/ (порядок, «Совпадений»), место нужного, карточка (статус, плеер; у сериала — ссылки на серии).
Исход: ok | нет в каталоге | ошибка поиска | ранжирование | неисправна карточка | жанр/год (по смыслу) | неясно.
Запросы к сайту по одному, метка factory-seo-acceptance.
"""
import difflib, json, re, sys, time, urllib.error, urllib.parse, urllib.request
S, INP, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
UA = "Mozilla/5.0 factory-seo-acceptance"
queries = json.load(open(INP))
cat = json.load(open("/srv/zonafilm-cc/data/zona-02-catalog.json"))["items"]
facets = json.load(open(S + "/zcc/facets.json"))
def norm(s):
    s = s.lower().replace("ё", "е"); s = re.sub(r"\(\d{4}\)?|\(\d{4}$", " ", s)
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()
by = {}
for i in cat: by.setdefault(norm(i["title"]), []).append(i)
titles = list(by)
GENRES = {norm(t): v for v, t in facets.get("Фильтр по жанру", []) if t != "Все жанры"}
PLURAL = {"ужасы": "ужасы", "комедии": "комедия", "боевики": "боевик", "мелодрамы": "мелодрама", "триллеры": "триллер", "драмы": "драма",
          "мультфильмы": "мультфильм", "мультики": "мультфильм", "детективы": "детектив", "сериалы": None, "фильмы": None, "аниме": "аниме", "дорамы": "дорама", "фантастика": "фантастика"}
def get(path):
    try:
        r = urllib.request.urlopen(urllib.request.Request("https://zonafilm.cc" + path, headers={"User-Agent": UA}), timeout=40); return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e: return e.code, ""
def card(slug):
    st, h = get(f"/title/{slug}/")
    vp = re.search(r'<video-player[^>]*data-title-id="([^"]+)"', h)
    return {"status": st, "player": bool(vp), "episodes": len(set(re.findall(r'/title/' + re.escape(slug) + r'/season-\d+/episode-\d+/', h)))}
R = []
for q, visits in sorted(queries.items(), key=lambda x: -x[1]):
    n = norm(q); base = re.sub(r"\b\d+\s*(сезон|серия|серии|сезона)\b|\b(сезон|серия)\s*\d+\b", " ", n).strip(); base = re.sub(r"\s+", " ", base)
    kind = "сезон/серия" if base != n else None
    yr = re.fullmatch(r"(фильмы|сериалы|мультфильмы)?\s*(19|20)\d\d( года)?", base)
    words = base.split()
    gen = GENRES.get(base) or (PLURAL.get(base) if base in PLURAL else None)
    exact = by.get(base, [])
    franch = [i for t in titles if t.startswith(base + " ") for i in by[t]] if len(base) >= 3 else []
    if yr: kind = "год"
    elif gen or base in PLURAL: kind = "жанр"
    elif exact and len({(i["year"], i["kind"]) for i in exact}) > 1: kind = kind or "неоднозначное название"
    elif exact and franch: kind = kind or "франшиза"
    elif exact: kind = kind or "точное название"
    elif franch: kind = kind or "франшиза/начало названия"
    targets = exact or franch
    near = [] if targets or kind in ("жанр", "год") else difflib.get_close_matches(base, titles, n=3, cutoff=0.8)
    if near and not targets: kind = "опечатка"; targets = [i for t in near[:1] for i in by[t]]
    st, h = get("/search/?q=" + urllib.parse.quote(q))
    main = h[h.find("<main"):h.find("</main>")]
    res = list(dict.fromkeys(re.findall(r'href="(?:https://zonafilm\.cc)?/title/([^/"]+)/"', main)))
    m = re.search(r"Совпадений:\s*(\d+)", main); total = int(m.group(1)) if m else 0
    tslugs = [i["slug"] for i in targets]
    pos = next((k + 1 for k, s in enumerate(res) if s in tslugs), None)
    c = card(tslugs[0] if pos is None and tslugs else res[pos - 1]) if (tslugs) else None
    if kind in ("жанр", "год"): verdict = "жанр/год: поиск по названию, нужен раздел"
    elif not targets: verdict = "нет в каталоге"
    elif pos is None: verdict = "ошибка поиска" if total < 28 else "ранжирование (нет на 1-й странице)"
    elif c and (c["status"] != 200 or not c["player"]): verdict = "неисправна карточка"
    elif pos > 3: verdict = "ранжирование"
    else: verdict = "ok"
    row = {"q": q, "visits": visits, "class": kind or "неясно", "targets": [(i["title"], i["year"], i["kind"], i["slug"]) for i in targets[:4]], "n_targets": len(targets),
           "near": near, "results_total": total, "first_results": res[:5], "pos": pos, "card": c, "verdict": verdict}
    R.append(row); print(json.dumps({k: row[k] for k in ("q", "visits", "class", "n_targets", "results_total", "pos", "verdict")}, ensure_ascii=False), flush=True)
    time.sleep(0.4)
json.dump(R, open(OUT, "w"), ensure_ascii=False, indent=1)
