"""Стенд: рендер только тех страниц, что есть в очереди SEO."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, "/home/claude/wt-core-identity-22")
import yaml
from factory.lords import live_catalog, render as render_mod
from factory.paths import PATHS

site_id, out = sys.argv[1], Path(sys.argv[2])
queue = json.load(open(sys.argv[3], encoding="utf-8"))
lords = {"lordfilm47.space", "lordserial33.biz", "1lordserials1.online"}
from urllib.parse import urlparse
слаги = set()
for r in queue:
    if r.get("domain") not in lords:
        continue
    cid = str(r.get("content_id") or "")
    if not cid.startswith("http"):
        continue
    части = [c for c in urlparse(cid).path.split("/") if c]
    if len(части) == 2 and части[0] == "title":
        слаги.add(части[1])
print("страниц к отрисовке:", len(слаги))

package = yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))
кэш = json.load(open("/srv/site-factory/repo/var/lords/lords/catalog-cache/%s.json" % site_id, encoding="utf-8"))
t = time.time()
catalog = live_catalog.catalog_from_live(кэш["items"])
print("каталог собран за", round(time.time()-t,1), "с; тайтлов", len(catalog.titles))
t = time.time()
site = render_mod.render_site(package, catalog=catalog, environ={},
                              only_title_slugs=frozenset(слаги))
print("отрисовано за", round(time.time()-t,1), "с; страниц", len(site.pages))
out.mkdir(parents=True, exist_ok=True)
страницы = site.pages
пары = (страницы.items() if isinstance(страницы, dict)
        else [(getattr(p, "path", ""), p) for p in страницы])
n = 0
for адрес, тело in пары:
    ключ = str(адрес).strip("/")
    if not ключ or "/title/" not in "/" + ключ:
        continue
    путь = out / ключ
    if not путь.suffix:
        путь = путь / "index.html"
    путь.parent.mkdir(parents=True, exist_ok=True)
    текст = тело if isinstance(тело, str) else getattr(тело, "body", str(тело))
    путь.write_text(текст if isinstance(текст, str) else str(текст), encoding="utf-8")
    n += 1
print("записано страниц произведений:", n)
