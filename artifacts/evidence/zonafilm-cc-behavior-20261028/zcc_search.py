"""Внутренний поиск zonafilm.cc: есть ли результаты по запросам о названиях из каталога. Пробы по одной."""
import html, json, re, sys, time, urllib.parse, urllib.request
UA = "Mozilla/5.0 factory-seo-acceptance"
QS = ["одиссея", "ярость на пределе", "человек паук", "призрак гилмор хаус", "тюрьма черный остров", "тюрьма чёрный остров", "веном", "мстители", "гарри поттер", "ведьмак", "игра в кальмара", "уэнсдей", "трансформеры", "шрек", "фильмы 2025", "ужасы", "комедия"]
R = []
for q in QS:
    u = "https://zonafilm.cc/search/?q=" + urllib.parse.quote(q)
    h = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=60).read().decode("utf-8", "replace")
    main = h[h.find("<main"):h.find("</main>")]
    slugs = list(dict.fromkeys(re.findall(r'href="(?:https://zonafilm\.cc)?/title/([^/"]+)/"', main)))
    txt = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", main)))[:300]
    rob = re.search(r'name="robots" content="([^"]+)"', h)
    R.append({"q": q, "results": len(slugs), "first": slugs[:3], "robots": rob and rob.group(1), "text": txt[:160]})
    print(R[-1], flush=True); time.sleep(1)
json.dump(R, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
