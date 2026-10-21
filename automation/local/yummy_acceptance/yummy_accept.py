"""Приёмка выпуска Yummy против исходного набора одного домена.

python3 yummy_accept.py <домен> <старый baseline.json> <новый baseline.json> [выборка]
Новый baseline строится yummy_baseline.py по свежему обходу каталога и свежему снимку карты.
Проверки: появились / остались отсутствующими; прежние адреса карты сохранены;
дубли и чужие/недопустимые адреса; выборка появившихся страниц (200, index, canonical на себя,
h1 и номер серии в странице); последние страницы каталога.
"""
import json, re, sys, random, urllib.request, urllib.error

D, OLD, NEW = sys.argv[1:4]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 30
UA = {"User-Agent": "sf-seo-audit/1.0"}
o, n = json.load(open(OLD)), json.load(open(NEW))

def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60)
        return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return str(e)[:80], ""

def page(u):
    st, h = get(u)
    can = (re.findall(r'<link rel="canonical" href="([^"]+)"', h) or [None])[0]
    rb = (re.findall(r'<meta name="robots" content="([^"]+)"', h) or [""])[0]
    h1 = re.sub(r"<[^>]+>", "", (re.findall(r"<h1[^>]*>(.*?)</h1>", h, re.S) or [""])[0]).strip()
    return {"url": u, "status": st, "canonical_self": (can or "").rstrip("/") == u.rstrip("/"),
            "robots": rb, "h1": h1[:120], "html": h}

res = {"domain": D, "old": OLD, "new": NEW}
for k in ("seasons", "episodes"):
    om, nm = set(o["missing"][k]), set(n["missing"][k])
    appeared = sorted(om - nm)
    res[k] = {"baseline_missing": len(om), "appeared": len(appeared), "still_missing": len(om & nm),
              "newly_missing": sorted(nm - om)[:200], "newly_missing_count": len(nm - om),
              "still_missing_list": sorted(om & nm)[:300]}
    res[k + "_appeared_list"] = appeared
# новые поступления: адреса эталона, которых в старом эталоне не было
for k in ("titles", "seasons", "episodes"):
    res.setdefault("new_arrivals", {})[k] = {"own_old": o["own"][k], "own_new": n["own"][k]}
old_urls, new_urls = set(o["sitemap_urls"]), set(n["sitemap_urls"])
lost = sorted(old_urls - new_urls)
res["preservation"] = {"old_urls": len(old_urls), "new_urls": len(new_urls), "lost_count": len(lost), "lost": lost[:300]}
# потерянные адреса — живы ли они (потеря с причиной = 404/noindex)
random.seed(20261022)
res["preservation"]["lost_sample"] = [{k: v for k, v in page(u).items() if k != "html"} for u in random.sample(lost, min(20, len(lost)))]
res["hygiene"] = {"duplicates": len(n["duplicates"]), "foreign_host": len(n["foreign_host"]),
                  "extra_not_in_own_catalog": {k: len(n["extra"][k]) for k in ("titles", "seasons", "episodes")},
                  "extra_sample": n["extra"]["episodes"][:20] + n["extra"]["seasons"][:20]}
smp = []
for key in random.sample(res["episodes_appeared_list"], min(N, len(res["episodes_appeared_list"]))):
    sl, s, e = key.split("/")
    p = page(f"https://{D}/anime/{sl}/season/{s}/episode/{e}")
    p["episode_in_page"] = bool(re.search(rf"\b{e}\b\s*(?:серия|эпизод)|(?:серия|эпизод)\s*{e}\b", p.pop("html"), re.I))
    smp.append(p)
for key in random.sample(res["seasons_appeared_list"], min(10, len(res["seasons_appeared_list"]))):
    sl, s = key.split("/")
    p = page(f"https://{D}/anime/{sl}/season/{s}"); p.pop("html"); smp.append(p)
res["appeared_sample"] = {"n": len(smp), "ok": sum(1 for x in smp if x["status"] == 200 and x["canonical_self"]
                                                 and "noindex" not in x["robots"] and x["h1"]), "rows": smp}
# последние страницы каталога
cat = []
for pn in list(range(330, 352)):
    st, h = get(f"https://{D}/catalog?page={pn}")
    cards = len(set(re.findall(r'href="/anime/([^/"?#]+)"', h)))
    rb = (re.findall(r'<meta name="robots" content="([^"]+)"', h) or [""])[0]
    cat.append({"page": pn, "status": st, "cards": cards, "robots": rb})
res["catalog_tail"] = cat
res["catalog_tail_summary"] = {"last_page_with_cards": max([c["page"] for c in cat if c["cards"]] or [None]),
                               "empty_indexable": [c["page"] for c in cat if c["status"] == 200 and not c["cards"] and "noindex" not in c["robots"]]}
for k in ("seasons_appeared_list", "episodes_appeared_list"):
    res[k] = res[k][:500]
json.dump(res, open(f"{NEW.rsplit('/', 1)[0]}/{D}-accept.json", "w"), ensure_ascii=False, indent=1)
print(D, "seasons", {k: v for k, v in res["seasons"].items() if not isinstance(v, list)},
      "episodes", {k: v for k, v in res["episodes"].items() if not isinstance(v, list)},
      "lost", res["preservation"]["lost_count"], "hygiene", res["hygiene"]["duplicates"], res["hygiene"]["foreign_host"],
      res["hygiene"]["extra_not_in_own_catalog"], "sample ok", res["appeared_sample"]["ok"], "/", res["appeared_sample"]["n"],
      "catalog", res["catalog_tail_summary"])
