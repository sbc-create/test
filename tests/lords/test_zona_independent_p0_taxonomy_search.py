"""P0 taxonomy + original-title search gates for independent repair."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"
sys.path.insert(0, str(КОРЕНЬ / "automation" / "host"))
import genre_aliases  # noqa: E402
import collection_contract as cc  # noqa: E402


def test_genre_aliases_unify_comedy_keys():
    assert genre_aliases.канон_жанра("comedy") == "comedy"
    assert genre_aliases.канон_жанра("komediya") == "comedy"
    assert genre_aliases.канон_жанра("комедия") == "comedy"
    assert genre_aliases.жанр_совпадает(
        "comedy", ["komediya"], ["комедия"])
    assert genre_aliases.жанр_совпадает(
        "комедия", ["comedy"], [])
    # Exact token — not bare substring of unrelated compound without alias hit
    assert genre_aliases.жанр_совпадает(
        "comedy", [], ["романтическая комедия"])


def _поднять(tmp_path):
    items = [
        {"slug": "only-code-comedy", "title": "Code Comedy", "kind": "Фильм",
         "year": 2020, "poster": "https://p/a.webp", "url": "/title/only-code-comedy/",
         "published_at": "2026-09-01T00:00:00Z"},
        {"slug": "only-ru-label", "title": "RU Comedy", "kind": "Фильм",
         "year": 2021, "poster": "https://p/b.webp", "url": "/title/only-ru-label/",
         "published_at": "2026-09-02T00:00:00Z"},
        {"slug": "dusty", "title": "Пыльные утёсы", "kind": "Фильм",
         "year": 2022, "poster": "https://p/c.webp", "url": "/title/dusty/",
         "published_at": "2026-09-10T00:00:00Z"},
        {"slug": "old-added", "title": "Old Added", "kind": "Фильм",
         "year": 1990, "poster": "https://p/d.webp", "url": "/title/old-added/",
         "published_at": "2025-01-01T00:00:00Z"},
    ]
    cat = {"version": 2, "count": len(items), "items": items, "site": "zona-01",
           "schema": "nova-catalog/2.0.0", "revision": "p0",
           "builtAt": "2026-09-20T00:00:00Z"}
    details = {
        "schema": "nova-details/1.0.0", "site": "zona-01",
        "details_total": 4, "source": "test", "items_total": 4,
        "details": {
            "only-code-comedy": {
                "id": "1", "description": "d", "genres": ["комедия"],
                "genre_codes": ["comedy"], "countries": ["США"],
                "sources": [], "external_ids": {}, "playable": True,
            },
            "only-ru-label": {
                "id": "2", "description": "d", "genres": ["комедия"],
                # no genre_codes → translit komediya historically
                "genre_codes": [], "countries": ["США"],
                "sources": [], "external_ids": {}, "playable": True,
            },
            "dusty": {
                "id": "3", "description": "d", "genres": ["драма"],
                "genre_codes": ["drama"], "countries": ["США"],
                "original_name": "Dusty Bluffs",
                "sources": [], "external_ids": {}, "playable": True,
            },
            "old-added": {
                "id": "4", "description": "d", "genres": ["боевик"],
                "genre_codes": ["action"], "countries": ["США"],
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
        "build_id": "P0", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    env = dict(os.environ)
    os.environ.update({
        "LORDS_TEMPLATE_MANIFEST": str(man),
        "LORDS_CATALOG": str(root / "zona-01-catalog.json"),
        "LORDS_DETAILS": str(root / "zona-01-details.json"),
        "LORDS_PLAYER_CONFIG": str(root / "player-zona-01.json"),
        "LORDS_SITE_NAME": "Zona P0",
        "LORDS_CLOCK_ISO": "2026-09-20T12:00:00Z",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    name = f"nova_zona_p0_{tmp_path.name}"
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


def test_p0_comedy_catalog_equals_collection(зона):
    # Catalog facet
    набор_c, _ = зона.отбор(
        зона.Обработчик.данные, зона.Обработчик.индекс,
        {"genre": ["comedy"]}, "/catalog")
    набор_k, _ = зона.отбор(
        зона.Обработчик.данные, зона.Обработчик.индекс,
        {"genre": ["komediya"]}, "/catalog")
    набор_ru, _ = зона.отбор(
        зона.Обработчик.данные, зона.Обработчик.индекс,
        {"genre": ["комедия"]}, "/catalog")
    slugs_c = {з["slug"] for з in набор_c}
    assert slugs_c == {з["slug"] for з in набор_k} == {з["slug"] for з in набор_ru}
    assert "only-code-comedy" in slugs_c
    assert "only-ru-label" in slugs_c

    снимок = зона.Снимок.получить(зона.Обработчик.данные, зона.Обработчик.подробности)
    кол = cc.разрешить("genre_comedy", снимок, "zona", предел=100)
    assert кол is not None
    coll_slugs = {к.raw["slug"] for к in кол.items}
    assert coll_slugs == slugs_c
    assert кол.total == len(slugs_c)


def test_p0_original_title_search(зона):
    hits = зона.Обработчик.данные.искать("Dusty Bluffs")
    assert hits and hits[0]["slug"] == "dusty"
    hits_ru = зона.Обработчик.данные.искать("Пыльные утёсы")
    assert hits_ru and hits_ru[0]["slug"] == "dusty"


def test_p0_recently_added_bounded(зона):
    снимок = зона.Снимок.получить(зона.Обработчик.данные, зона.Обработчик.подробности)
    кол = cc.разрешить("recently_added", снимок, "zona", предел=100)
    assert кол is not None
    slugs = {к.raw["slug"] for к in кол.items}
    assert "dusty" in slugs
    assert "old-added" not in slugs
    assert кол.total < len(зона.Обработчик.данные.items)
