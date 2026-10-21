"""Собственный опубликованный каталог домена Yummy: тайтлы -> сезоны -> серии.

Только GET к своему домену, UA sf-seo-audit/1.0. Источник тайтлов — страницы
/catalog?page=N и /catalog/announcement?page=N; сезонов — ссылки season/N на странице
тайтла; серий — ссылки episode/N на странице сезона. На каждой странице пишем
статус, robots meta и canonical, чтобы отличать допустимые адреса от недопустимых.
"""
import json, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

D = sys.argv[1]
OUT = sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 3
UA = {"User-Agent": "sf-seo-audit/1.0"}


def get(path):
    u = f"https://{D}{path}"
    for a in range(4):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60)
            return r.status, r.geturl(), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and a < 3:
                time.sleep(2 + 3 * a); continue
            return e.code, u, ""
        except Exception as e:  # noqa: BLE001
            if a < 3:
                time.sleep(2 + 3 * a); continue
            return f"ERR {type(e).__name__}", u, ""


def meta(h):
    c = re.findall(r'<link rel="canonical" href="([^"]+)"', h)
    rb = re.findall(r'<meta name="robots" content="([^"]+)"', h)
    return (c[0] if c else None), (rb[0] if rb else None)


def listing(base):
    s, _, h = get(base)
    pages = [int(x) for x in re.findall(r"[?&]page=(\d+)", h)] or [1]
    n = max(pages)
    got = {}
    def one(p):
        return p, get(f"{base}?page={p}" if p > 1 else base)
    with ThreadPoolExecutor(1) as ex:
        for p, (s, _, h) in ex.map(one, range(1, n + 1)):
            got[p] = (s, sorted(set(re.findall(r'href="/anime/([^"/?#]+)"', h))))
    return n, got


t0 = time.time()
res = {"domain": D, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
titles = set(json.load(open(sys.argv[4])))
res["titles_source"] = "sitemap titles not reachable via /catalog (" + sys.argv[4] + ")"
T = {}
def title(slug):
    s, fin, h = get(f"/anime/{slug}")
    c, rb = meta(h)
    seasons = sorted({int(x) for x in re.findall(rf'href="/anime/{re.escape(slug)}/season/(\d+)"', h)}
                     | {int(x) for x in re.findall(rf'href="/anime/{re.escape(slug)}/season/(\d+)/episode/', h)})
    shown = {}
    for se, e in re.findall(rf'href="/anime/{re.escape(slug)}/season/(\d+)/episode/(\d+)"', h):
        shown.setdefault(int(se), set()).add(int(e))
    return slug, {"status": s, "final": fin, "canonical": c, "robots": rb, "seasons": seasons,
                  "shown_episodes": {str(k): sorted(v) for k, v in shown.items()}}
with ThreadPoolExecutor(W) as ex:
    for i, (slug, r) in enumerate(ex.map(title, sorted(titles))):
        T[slug] = r
        if i % 1000 == 0:
            print(D, "titles", i, round(time.time() - t0), flush=True)
res["titles"] = T

S = {}
# Страница сезона нужна только там, где страница тайтла не показала серии сезона.
pairs = [(sl, n) for sl, r in T.items() for n in r["seasons"] if str(n) not in r["shown_episodes"]]
for sl, r in T.items():
    for n, eps in r["shown_episodes"].items():
        S[f"{sl}/{n}"] = {"status": "from_title_page", "episodes": eps}
def season(p):
    sl, n = p
    s, fin, h = get(f"/anime/{sl}/season/{n}")
    c, rb = meta(h)
    eps = sorted({int(x) for x in re.findall(rf'href="/anime/{re.escape(sl)}/season/{n}/episode/(\d+)"', h)})
    return f"{sl}/{n}", {"status": s, "final": fin, "canonical": c, "robots": rb, "episodes": eps}
with ThreadPoolExecutor(W) as ex:
    for i, (k, r) in enumerate(ex.map(season, pairs)):
        S[k] = r
        if i % 1000 == 0:
            print(D, "seasons", i, "/", len(pairs), round(time.time() - t0), flush=True)
res["seasons"] = S
res["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(res, open(OUT, "w"), ensure_ascii=False)
print(D, "done", len(T), len(S), sum(len(r["episodes"]) for r in S.values()), round(time.time() - t0), flush=True)
