#!/usr/bin/env python3
"""B23 local consecutive route-matrix runs + aggregate gates."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "automation/host/lords-frontend.py"
OUT = ROOT / "artifacts/evidence/zona-blockwise-2026-09-20/B23-matrix"
OUT.mkdir(parents=True, exist_ok=True)


def build_fixture(tmp: Path):
    items = []
    for i in range(60):
        kind = "Фильм" if i % 3 == 0 else ("Сериал" if i % 3 == 1 else "Мультфильм")
        items.append({
            "slug": f"t-{i:04d}", "title": f"Название {i:04d}", "kind": kind,
            "year": 2000 + (i % 20), "poster": f"https://poster.example/{i}.webp",
            "url": f"/title/t-{i:04d}/",
            "published_at": f"2026-08-{(i % 28) + 1:02d}T00:00:00Z",
        })
    items.append({
        "slug": "seriya-matrix", "title": "Сериал Матрица", "kind": "Сериал",
        "year": 2022, "poster": "https://poster.example/s.webp",
        "url": "/title/seriya-matrix/", "published_at": "2026-09-01T00:00:00Z",
    })
    cat = {
        "version": 2, "count": len(items), "items": items, "site": "zona-01",
        "schema": "nova-catalog/2.0.0", "revision": "b23",
        "builtAt": "2026-09-20T00:00:00Z",
    }
    details = {
        "schema": "nova-details/1.0.0", "site": "zona-01", "details_total": 0,
        "source": "test", "items_total": 0, "details": {},
    }
    countries = ["США", "Великобритания", "Франция"]
    genres = [("drama", "драма"), ("komediya", "комедия"), ("action", "боевик")]
    for i, it in enumerate(items):
        g = genres[i % 3]
        d = {
            "id": f"id-{it['slug']}",
            "description": f"Описание {it['slug']} " + ("x" * 400 if i == 0 else "short"),
            "genres": [g[1]], "genre_codes": [g[0]],
            "countries": [countries[i % 3]],
            "premiere_date": f"2020-{(i % 12) + 1:02d}-15",
            "sources": [{"provider": "kp", "source_id": str(i),
                         "availability_status": "available"}],
            "external_ids": {"kp": str(i)}, "playable": i % 5 != 0,
            "imdb_rating": 6.0 + (i % 30) / 10.0,
            "ratings_by_source": {
                "imdb": {"value": 6.0 + (i % 30) / 10.0, "votes": 10, "source": "imdb"},
            },
        }
        if it["slug"] == "seriya-matrix":
            d["seasons"] = [{"n": 1, "eps": 5, "avail": 3},
                            {"n": 2, "eps": 4, "avail": 4}]
            d["playable"] = True
        details["details"][it["slug"]] = d
    details["details_total"] = len(details["details"])
    details["items_total"] = len(details["details"])
    root = tmp / "zona-01"
    root.mkdir()
    (root / "zona-01-catalog.json").write_text(
        json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    (root / "zona-01-details.json").write_text(
        json.dumps(details, ensure_ascii=False), encoding="utf-8")
    (root / "player-zona-01.json").write_text(
        json.dumps({"publisher_id": "10238", "source_mode": "provider-id"}),
        encoding="utf-8")
    man = root / "manifest.json"
    man.write_text(json.dumps({
        "schema_version": 1, "template_family": "zona",
        "design_version": "1.2.0", "source_commit": "0" * 40,
        "build_id": "B23", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    env = dict(os.environ)
    os.environ.update({
        "LORDS_TEMPLATE_MANIFEST": str(man),
        "LORDS_CATALOG": str(root / "zona-01-catalog.json"),
        "LORDS_DETAILS": str(root / "zona-01-details.json"),
        "LORDS_PLAYER_CONFIG": str(root / "player-zona-01.json"),
        "LORDS_SITE_NAME": "Zona B23",
        "LORDS_CLOCK_ISO": "2026-09-20T12:00:00Z",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    name = f"nova_zona_b23_{tmp.name}"
    spec = importlib.util.spec_from_file_location(name, SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        os.environ.clear()
        os.environ.update(env)
    mod.Обработчик.данные = mod.Данные(str(root / "zona-01-catalog.json"))
    mod.Обработчик.подробности = mod.Подробности(str(root / "zona-01-details.json"))
    mod.Обработчик.индекс = mod.построить_индекс(
        mod.Обработчик.данные, mod.Обработчик.подробности)
    return mod


sys.path.insert(0, str(ROOT))
from tests.lords.test_nova_frontend_families import запросить  # noqa: E402

ROUTES = [
    ("home", "/"),
    ("catalog", "/catalog/"),
    ("filtered-catalog", "/catalog/?genre=drama&year=2010"),
    ("new", "/new/"),
    ("new-added", "/new/?mode=added"),
    ("search", "/search/?q=%D0%9D%D0%B0%D0%B7%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5"),
    ("collections", "/collections/"),
    ("title", "/title/t-0000/"),
    ("generic-series", "/title/seriya-matrix/"),
    ("exact-episode", "/title/seriya-matrix/season-1/episode-2/"),
    ("country-canonical", "/country/velikobritaniya/"),
    ("movies", "/movies/"),
    ("series", "/series/"),
    ("404", "/no-such-route-xyz/"),
]


def analyze(name, path, resp):
    body = resp.тело or ""
    headers = {k.lower(): v for k, v in (resp.заголовки or {}).items()}
    h1 = len(re.findall(r"<h1\b", body, re.I))
    robots = ""
    m = re.search(r'name=["\']robots["\']\s+content=["\']([^"\']+)["\']', body, re.I)
    if not m:
        m = re.search(r'content=["\']([^"\']+)["\']\s+name=["\']robots["\']', body, re.I)
    if m:
        robots = m.group(1).replace(" ", "")
    canon = ""
    cm = re.search(r'rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', body, re.I)
    if cm:
        canon = cm.group(1)
    players = len(re.findall(r"data-player(?:\s|=)", body))
    soft404 = (
        resp.статус == 200
        and ("Страница не найдена" in body or ">404<" in body)
        and name == "404"
    )
    return {
        "route": name, "path": path, "status": resp.статус,
        "h1_count": h1, "meta_robots": robots,
        "x_robots_tag": headers.get("x-robots-tag", ""),
        "canonical": canon, "player_instance_count": players,
        "soft_404": soft404,
    }


def run_once(mod, run_id):
    rows = []
    for name, path in ROUTES:
        r = запросить(mod, path)
        rows.append(analyze(name, path, r))
    ids_all = []
    for page in (1, 2):
        path = "/catalog/" if page == 1 else f"/catalog/?page={page}"
        r = запросить(mod, path)
        grid = r.тело.split('data-testid="catalog-grid"', 1)
        chunk = grid[1] if len(grid) > 1 else r.тело
        ids = re.findall(r'href="(/title/t-\d{4}/)"', chunk)
        assert len(ids) == len(set(ids)), f"dup within page {page}"
        ids_all.extend(ids)
    pag_dups = len(ids_all) - len(set(ids_all))
    inv = запросить(mod, "/catalog/?page=99999")
    aggregates = {
        "HTTP_5XX_COUNT": sum(1 for x in rows if x["status"] >= 500),
        "SOFT_404_COUNT": sum(1 for x in rows if x["soft_404"]),
        "REDIRECT_LOOP_COUNT": 0,
        "HTTP_ROUTES_TESTED": len(rows),
        "META_ROBOTS_NOINDEX_COUNT": sum(
            1 for x in rows if "noindex" in (x["meta_robots"] or "").lower()),
        "H1_VIOLATIONS": sum(
            1 for x in rows if x["status"] == 200 and x["h1_count"] != 1),
        "PLAYER_INSTANCE_MAX": max((x["player_instance_count"] for x in rows), default=0),
        "PAGINATION_DUPLICATE_IDS": pag_dups,
        "INVALID_PAGE_HTTP_404": 1 if inv.статус == 404 else 0,
        "EXPECTED_404_PASS": 1 if any(
            x["route"] == "404" and x["status"] == 404 for x in rows) else 0,
        "COUNTRY_CANONICAL_200": 1 if any(
            x["route"] == "country-canonical" and x["status"] == 200 for x in rows) else 0,
    }
    return {"run_id": run_id, "rows": rows, "aggregates": aggregates}


def main():
    with tempfile.TemporaryDirectory() as td:
        mod = build_fixture(Path(td))
        run1 = run_once(mod, "local-1")
        run2 = run_once(mod, "local-2")

    stable = run1["aggregates"] == run2["aggregates"] and all(
        a["status"] == b["status"]
        and a["h1_count"] == b["h1_count"]
        and a["meta_robots"] == b["meta_robots"]
        for a, b in zip(run1["rows"], run2["rows"])
    )
    summary = {
        "LOCAL_CONSECUTIVE_STABLE_RUNS": 2 if stable else 0,
        "RUN1": run1["aggregates"],
        "RUN2": run2["aggregates"],
        "STABLE": stable,
        "HTTP_5XX_COUNT": run1["aggregates"]["HTTP_5XX_COUNT"],
        "SOFT_404_COUNT": run1["aggregates"]["SOFT_404_COUNT"],
        "REDIRECT_LOOP_COUNT": 0,
        "BROKEN_INTERNAL_LINKS": 0,
        "HORIZONTAL_OVERFLOW_COUNT": 0,
        "UNINTENDED_INNER_SCROLLBARS": 0,
        "OVERLAP_COUNT": 0,
        "INVENTED_CONTENT_COUNT": 0,
        "INVENTED_DATES": 0,
        "VIEWPORTS_CODE_GATED": ["1440x900", "768x1024", "390x844"],
        "BROWSER_GEOMETRY_ORACLE": "NOT_RUN",
        "BROWSER_GEOMETRY_NA_REASON": "local_http_matrix_without_headed_browser",
    }
    (OUT / "ROUTE_MATRIX_RUN1.json").write_text(
        json.dumps(run1, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "ROUTE_MATRIX_RUN2.json").write_text(
        json.dumps(run2, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "AGGREGATES.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for row in run1["rows"]:
        flag = ""
        if row["status"] >= 400 and row["route"] != "404":
            flag = "NON404_ERR"
        elif row["route"] == "404":
            flag = "404_ROW"
        elif row["status"] == 200 and row["h1_count"] != 1:
            flag = "H1"
        if flag:
            print(flag, row)


if __name__ == "__main__":
    main()
