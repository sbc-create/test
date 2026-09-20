"""P0-05 filter state preservation + country route aliases."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"
sys.path.insert(0, str(КОРЕНЬ / "automation" / "host"))


def _поднять(tmp_path):
    items = [
        {"slug": "uk-film", "title": "UK Film", "kind": "Фильм",
         "year": 2020, "poster": "https://p/a.webp", "url": "/title/uk-film/",
         "published_at": "2026-09-01T00:00:00Z"},
        {"slug": "us-comedy", "title": "US Comedy", "kind": "Фильм",
         "year": 2021, "poster": "https://p/b.webp", "url": "/title/us-comedy/",
         "published_at": "2026-09-02T00:00:00Z"},
        {"slug": "old-drama", "title": "Old Drama", "kind": "Сериал",
         "year": 1902, "poster": "https://p/c.webp", "url": "/title/old-drama/",
         "published_at": "2026-08-01T00:00:00Z"},
    ]
    cat = {"version": 2, "count": len(items), "items": items, "site": "zona-01",
           "schema": "nova-catalog/2.0.0", "revision": "p0-b04",
           "builtAt": "2026-09-20T00:00:00Z"}
    details = {
        "schema": "nova-details/1.0.0", "site": "zona-01",
        "details_total": 3, "source": "test", "items_total": 3,
        "details": {
            "uk-film": {
                "id": "1", "description": "d", "genres": ["драма"],
                "genre_codes": ["drama"], "countries": ["Великобритания"],
                "sources": [], "external_ids": {}, "playable": True,
            },
            "us-comedy": {
                "id": "2", "description": "d", "genres": ["комедия"],
                "genre_codes": ["comedy"], "countries": ["США"],
                "sources": [], "external_ids": {}, "playable": True,
            },
            "old-drama": {
                "id": "3", "description": "d", "genres": ["драма"],
                "genre_codes": ["drama"], "countries": ["Франция"],
                "sources": [], "external_ids": {}, "playable": True,
            },
        },
    }
    root = tmp_path / "zona-01"
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
        "build_id": "P0-B04", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    env = dict(os.environ)
    os.environ.update({
        "LORDS_TEMPLATE_MANIFEST": str(man),
        "LORDS_CATALOG": str(root / "zona-01-catalog.json"),
        "LORDS_DETAILS": str(root / "zona-01-details.json"),
        "LORDS_PLAYER_CONFIG": str(root / "player-zona-01.json"),
        "LORDS_SITE_NAME": "Zona P0 B04",
        "LORDS_CLOCK_ISO": "2026-09-20T12:00:00Z",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    name = f"nova_zona_p0_b04_{tmp_path.name}"
    spec = importlib.util.spec_from_file_location(name, ИСХОДНИК)
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


def запросить(модуль, путь: str):
    from tests.lords.test_nova_frontend_families import запросить as _з
    return _з(модуль, путь)


@pytest.fixture
def зона(tmp_path):
    return _поднять(tmp_path)


def _option_hrefs(html: str, select_id: str) -> list[str]:
    import html as _html
    m = re.search(
        rf'<select[^>]*id="{re.escape(select_id)}"[^>]*>(.*?)</select>',
        html, re.S)
    assert m, f"select #{select_id} missing"
    return [_html.unescape(h) for h in re.findall(r'<option value="([^"]*)"', m.group(1))]


def test_genre_change_preserves_year_kind_sort(зона):
    о = запросить(
        зона, "/catalog/?year=2021&kind=%D0%A4%D0%B8%D0%BB%D1%8C%D0%BC&sort=rating")
    assert о.статус == 200
    hrefs = _option_hrefs(о.тело, "zona-genre-facet")
    comedy = [h for h in hrefs if "genre=comedy" in h or "genre=комедия" in h]
    assert comedy, hrefs
    raw = comedy[0].replace("&amp;", "&")
    qs = parse_qs(urlparse(raw).query)
    assert qs.get("year") == ["2021"], raw
    assert qs.get("sort") == ["rating"], raw
    assert qs.get("kind") == ["Фильм"], raw


def test_active_zero_result_year_stays_selected(зона):
    # year=1902 + genre=comedy → empty, but 1902 must remain selected/removable
    о = запросить(зона, "/catalog/?year=1902&genre=comedy")
    assert о.статус == 200
    assert 'id="zona-year-facet"' in о.тело
    assert re.search(
        r'<option value="[^"]*"[^>]*selected[^>]*>1902', о.тело) or re.search(
        r'<option value="[^"]*" selected>1902', о.тело)
    assert "1902" in о.тело


def test_country_route_velikobritaniya(зона):
    о = запросить(зона, "/country/velikobritaniya/")
    if о.статус in (301, 302, 308):
        loc = о.заголовки.get("Location") or о.заголовки.get("location") or ""
        assert "country=" in loc
        assert "velikobritaniya" in loc or "uk" in loc
    else:
        assert о.статус == 200
        assert "uk-film" in о.тело or "UK Film" in о.тело
        assert 'id="zona-country-facet"' in о.тело


def test_country_alias_uk_resolves(зона):
    о = запросить(зона, "/country/uk/")
    if о.статус in (301, 302, 308):
        loc = о.заголовки.get("Location") or о.заголовки.get("location") or ""
        assert "country=" in loc
        from urllib.parse import urlparse as _u
        p = _u(loc)
        path = p.path + (("?" + p.query) if p.query else "")
        о2 = запросить(зона, path)
        assert о2.статус == 200
        assert "UK Film" in о2.тело or "uk-film" in о2.тело
    else:
        assert о.статус == 200
        assert "UK Film" in о.тело or "uk-film" in о.тело


def test_country_control_present_when_data_exists(зона):
    о = запросить(зона, "/catalog/")
    assert о.статус == 200
    assert 'id="zona-country-facet"' in о.тело
    assert "Великобритания" in о.тело or "velikobritaniya" in о.тело


def test_reset_clears_filters(зона):
    о = запросить(зона, "/catalog/?year=2021&genre=comedy&sort=rating")
    assert о.статус == 200
    assert re.search(r'href="/catalog/"[^>]*>Сбросить', о.тело) or \
        'href="/catalog/"' in о.тело
