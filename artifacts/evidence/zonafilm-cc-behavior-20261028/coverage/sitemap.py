"""Публичная карта сайта zonafilm.cc → список URL и шаблоны. Запросы по одному, метка factory-seo-acceptance."""
import collections, json, re, sys, time, urllib.request
UA = "Mozilla/5.0 factory-seo-acceptance"
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=60).read().decode()
idx = get("https://zonafilm.cc/sitemap.xml"); locs = re.findall(r"<loc>([^<]+)</loc>", idx)
urls = []
for l in locs:
    if l.endswith(".xml"):
        time.sleep(1); urls += re.findall(r"<loc>([^<]+)</loc>", get(l))
    else: urls.append(l)
def tpl(p):
    k = re.sub(r"/title/[^/]+/", "/title/X/", p); k = re.sub(r"season-\d+", "season-N", k); k = re.sub(r"episode-\d+", "episode-M", k)
    k = re.sub(r"/collection/[^/]+/", "/collection/X/", k); return re.sub(r"=[^&]+", "=V", k)
c = collections.Counter(); ex = {}
for u in urls:
    p = u.replace("https://zonafilm.cc", ""); k = tpl(p); c[k] += 1; ex.setdefault(k, p)
json.dump({"index": locs, "urls": urls}, open(sys.argv[1], "w"))
print(len(urls)); [print(v, k, ex[k]) for k, v in c.most_common(40)]
