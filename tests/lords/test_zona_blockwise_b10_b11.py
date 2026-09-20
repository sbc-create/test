"""Zona blockwise B10 compact filters + B11 pagination oracle."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

ИСХОДНИК = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"


def _каталог(n=120):
    items = []
    for i in range(n):
        kind = "Фильм" if i % 3 == 0 else ("Сериал" if i % 3 == 1 else "Мультфильм")
        items.append({
            "slug": f"t-{i:04d}", "title": f"Title {i:04d}", "kind": kind,
            "year": 2000 + (i % 20), "poster": f"https://poster.example/{i}.webp",
            "url": f"/title/t-{i:04d}/",
            "published_at": f"2026-08-{(i % 28) + 1:02d}T00:00:00Z",
        })
    return {"version": 2, "count": len(items), "items": items, "site": "zona-01",
            "schema": "nova-catalog/2.0.0", "revision": "b10b11",
            "builtAt": "2026-09-20T00:00:00Z"}


def _подробности(catalog):
    details = {}
    countries = ["США", "Великобритания", "Франция", "Германия"]
    genres = [("drama", "драма"), ("komediya", "комедия"), ("action", "боевик")]
    for i, it in enumerate(catalog["items"]):
        g = genres[i % len(genres)]
        details[it["slug"]] = {
            "id": f"id-{it['slug']}",
            "description": f"Desc {it['slug']}",
            "genres": [g[1]], "genre_codes": [g[0]],
            "countries": [countries[i % len(countries)]],
            "sources": [{"provider": "kp", "source_id": "1",
                         "availability_status": "available"}],
            "external_ids": {"kp": "1"}, "playable": True,
            "imdb_rating": 6.0 + (i % 30) / 10.0,
            "ratings_by_source": {
                "imdb": {"value": 6.0 + (i % 30) / 10.0, "votes": 10, "source": "imdb"}},
        }
    return {
        "schema": "nova-details/1.0.0", "site": "zona-01",
        "details_total": len(details), "source": "test",
        "items_total": len(details), "details": details,
    }


def _поднять(tmp_path):
    корень = tmp_path / "zona-01"
    корень.mkdir(parents=True, exist_ok=True)
    cat = _каталог()
    (корень / "zona-01-catalog.json").write_text(
        json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    (корень / "zona-01-details.json").write_text(
        json.dumps(_подробности(cat), ensure_ascii=False), encoding="utf-8")
    (корень / "player-zona-01.json").write_text(
        json.dumps({"publisher_id": "10238", "source_mode": "provider-id"}),
        encoding="utf-8")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "zona",
        "design_version": "1.2.0", "source_commit": "0" * 40,
        "build_id": "B10B11", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona B10"
    os.environ["LORDS_CLOCK_ISO"] = "2026-09-20T12:00:00Z"
    try:
        имя = f"nova_zona_b10_{tmp_path.name}"
        спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
        модуль = importlib.util.module_from_spec(спец)
        sys.modules[имя] = модуль
        спец.loader.exec_module(модуль)
    finally:
        os.environ.clear()
        os.environ.update(старое)
    модуль.Обработчик.данные = модуль.Данные(str(корень / "zona-01-catalog.json"))
    модуль.Обработчик.подробности = модуль.Подробности(str(корень / "zona-01-details.json"))
    модуль.Обработчик.индекс = модуль.построить_индекс(
        модуль.Обработчик.данные, модуль.Обработчик.подробности)
    return модуль


def запросить(модуль, путь: str):
    from tests.lords.test_nova_frontend_families import запросить as _з
    return _з(модуль, путь)


@pytest.fixture
def зона(tmp_path):
    return _поднять(tmp_path)


def test_b10_compact_filters_have_selects_not_year_chip_wall(зона):
    о = запросить(зона, "/catalog/")
    assert о.статус == 200
    assert 'data-testid="catalog-filters"' in о.тело
    assert 'id="zona-year-facet"' in о.тело
    assert 'id="zona-genre-facet"' in о.тело
    assert 'id="zona-country-facet"' in о.тело
    assert 'id="zona-sort-facet"' in о.тело
    assert "zfilt-toggle" in о.тело
    # No massive year chip wall (select is primary).
    assert 'class="zfilt__y"' not in о.тело
    assert "Фильмы" in о.тело
    assert "Весь каталог" not in о.тело or "Каталог" in о.тело


def test_b10_filter_preserves_other_params(зона):
    о = запросить(зона, "/catalog/?genre=drama&year=2010")
    assert о.статус == 200
    # Year select options keep genre
    assert "genre=drama" in о.тело
    assert "year=2010" in о.тело or ">2010" in о.тело
    assert "Активные фильтры" in о.тело or "zfilt-chips" in о.тело


def test_b10_country_velikobritaniya_in_index(зона):
    idx = зона.Обработчик.индекс
    assert "velikobritaniya" in (idx.get("country") or {})
    о = запросить(зона, "/country/velikobritaniya/")
    assert о.статус == 200
    assert "Великобритания" in о.тело or "результатов" in о.тело.lower() or "Результаты" in о.тело


def test_b11_page_size_28_and_no_cross_page_duplicates(зона):
    page_size = зона.НА_СТРАНИЦЕ_1_1
    assert page_size == 28
    seen = []
    for page in (1, 2, 3):
        path = "/catalog/" if page == 1 else f"/catalog/?page={page}"
        о = запросить(зона, path)
        assert о.статус == 200
        ids = re.findall(r'href="(/title/t-\d{4}/)"', о.тело)
        # grid section only — take unique preserving order
        grid = о.тело.split('data-testid="catalog-grid"', 1)[1].split("zpg", 1)[0]
        ids = re.findall(r'href="(/title/t-\d{4}/)"', grid)
        assert 1 <= len(ids) <= page_size
        assert len(ids) == len(set(ids)), "duplicate ids within page"
        seen.extend(ids)
    assert len(seen) == len(set(seen)), "duplicate ids across pages"


def test_b11_invalid_page_is_404(зона):
    о = запросить(зона, "/catalog/?page=99999")
    assert о.статус == 404


def test_b11_page1_has_no_page_query_in_canonical(зона):
    о = запросить(зона, "/catalog/")
    # canonical should not include page=1
    m = re.search(r'rel="canonical" href="([^"]+)"', о.тело)
    assert m
    assert "page=1" not in m.group(1)
