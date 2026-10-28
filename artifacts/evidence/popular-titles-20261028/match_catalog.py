"""Первичное сопоставление 392 строк владельца с каталогами активных сайтов (28.10).

Только точное совпадение нормализованного названия (name / original_name) — кандидат, не решение:
идентичность, сезон и направление подтверждаются отдельно (match-decisions). Снимки только читаются.

python3 match_catalog.py → match-candidates-20261028.json рядом.
"""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
ROWS = json.loads((HERE / "source-owner-20261028.json").read_text(encoding="utf-8"))["rows"]
# Активные сайты (исключённые домены и K2 без каталога сюда не входят); снимки — data/ витрины.
SITES = {
    "zonafilm.cc": "/srv/zonafilm-cc/data/zona-02-details.json",
    "zonafilm.space": "/srv/zonafilm-space/data/zona-01-details.json",
    "zonafilm12.site": "/srv/zonafilm12-site/data/zona-03-details.json",
    "lordserial33.biz": "/srv/lordserial33-biz/data/lords-02-details.json",
    "1lordserials1.online": "/srv/site-1lordserials1-online/data/lords-03-details.json",
    "lordserials22.info": "/srv/lordserials22-info/data/lords-05-details.json",
    "animedia.icu": "/srv/animedia-icu/data/animedia-01-details.json",
    "animeg0.site": "/srv/animeg0-site/data/animego-03-details.json",
    "an1meg0.site": "/srv/an1meg0-site/data/animego-04-details.json",
    "an1mego.site": "/srv/an1mego-site/data/animego-02-details.json",
}


def norm(s):
    s = (s or "").lower().replace("ё", "е")
    s = re.sub(r"[«»\"'’“”.,:;!?()\-–—/]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


out = {r["n"]: {**r, "candidates": []} for r in ROWS}
built = {}
want = {norm(r["title"]): r["n"] for r in ROWS}
for site, path in SITES.items():
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    built[site] = {"catalog_built_at": data.get("catalog_built_at"), "titles": len(data["details"])}
    for slug, v in data["details"].items():
        for field in ("name", "original_name"):
            n = want.get(norm(v.get(field)))
            if n is not None:
                out[n]["candidates"].append({
                    "site": site, "slug": slug, "id": v.get("id"), "name": v.get("name"),
                    "original_name": v.get("original_name"), "year": v.get("year"), "type": v.get("type"),
                    "genres": v.get("genres"), "countries": v.get("countries"),
                    "seasons": len(v.get("seasons") or []), "playable": v.get("playable"),
                    "ext": {k: v.get("external_ids", {}).get(k) for k in ("imdb", "kp", "mal", "mdl") if (v.get("external_ids") or {}).get(k)},
                    "matched_on": field,
                })
                break

rows = list(out.values())
(HERE / "match-candidates-20261028.json").write_text(json.dumps(
    {"snapshots": built, "rows": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
hit = sum(1 for r in rows if r["candidates"])
print(f"строк с кандидатом хотя бы на одном сайте: {hit} из {len(rows)}")
for s in SITES:
    print(s, built[s], sum(1 for r in rows if any(c["site"] == s for c in r["candidates"])))
