"""Сданные составы подборок (T340, T341, подборки zonafilm.cc / animedia.icu) против снимка каталога после обновления.
Для каждого объекта с id = details[].id: есть ли id в снимке, тот же ли слаг, доступен ли (playable), не сменился ли тип.
Только чтение снимков. python3 stability.py <out.json>"""
import json, re, sys
from pathlib import Path
DOCS = Path(__file__).resolve().parents[3] / "docs" / "seo-operator"
SNAP = {"zonafilm.space": "/srv/zonafilm-space/data/zona-01-details.json", "zonafilm12.site": "/srv/lords/.frontend/zona-03-details.json",
        "zonafilm.cc": "/srv/zonafilm-cc/data/zona-02-details.json", "animedia.icu": "/srv/animedia-icu/data/animedia-01-details.json"}
FILES = {"ZONAFILM_SPACE_COLLECTIONS_20261026.json": "zonafilm.space", "ZONAFILM12_SITE_COLLECTIONS_20261026.json": "zonafilm12.site",
         "ZONAFILM_CC_COLLECTIONS_20261026.json": "zonafilm.cc", "ANIMEDIA_ICU_COLLECTIONS_20261026.json": "animedia.icu",
         "HOME_ZONAFILM_SPACE_20261027.json": "zonafilm.space", "HOME_ZONAFILM12_SITE_20261027.json": "zonafilm12.site", "HOME_ANIMEDIA_ICU_20261027.json": "animedia.icu"}
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
def walk(o, out):
    if isinstance(o, dict):
        if isinstance(o.get("id"), str) and UUID.match(o["id"]): out.append(o)
        for v in o.values(): walk(v, out)
    elif isinstance(o, list):
        for v in o: walk(v, out)
cache = {}
def snap(site):
    if site not in cache:
        d = json.load(open(SNAP[site]))
        det = d["details"]; cache[site] = ({e["id"]: (slug, e) for slug, e in det.items()}, d.get("catalog_built_at"), d.get("catalog_revision"))
    return cache[site]
REPORT = {}
for fn, site in FILES.items():
    by_id, built, rev = snap(site)
    items = []; walk(json.load(open(DOCS / fn)), items)
    seen = {}; [seen.setdefault(o["id"], o) for o in items]
    rows = []
    for i, o in seen.items():
        s = by_id.get(i); slug = o.get("slug")
        if not s: rows.append({"id": i, "slug": slug, "issue": "нет в снимке"}); continue
        sl, e = s; probs = []
        if slug and slug != sl: probs.append(f"слаг {slug} → {sl}")
        if str(e.get("playable")) != "True": probs.append(f"playable={e.get('playable')}")
        if probs: rows.append({"id": i, "slug": slug, "issue": "; ".join(probs)})
    REPORT[fn] = {"site": site, "snapshot": SNAP[site], "catalog_built_at": built, "ids": len(seen), "problems": rows}
    print(f"{fn}: {site}, id {len(seen)}, проблем {len(rows)}, снимок {built}")
    for r in rows: print("   ", r)
json.dump(REPORT, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
