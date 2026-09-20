"""Zona Pass6 Block 02: shell / header / nav — no empty strip, 44px targets."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

ИСХОДНИК = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"


def _каталог(n=40):
    items = []
    for i in range(n):
        kind = "Фильм" if i % 3 == 0 else ("Сериал" if i % 3 == 1 else "Мультфильм")
        items.append({
            "slug": f"t-{i:04d}", "title": f"Title {i:04d}", "kind": kind,
            "year": 2020 + (i % 6), "poster": f"https://poster.example/{i}.webp",
            "url": f"/title/t-{i:04d}/",
            "published_at": f"2026-09-{(i % 28) + 1:02d}T00:00:00Z",
        })
    return {"version": 2, "count": len(items), "items": items, "site": "zona-01",
            "schema": "nova-catalog/2.0.0", "revision": "pass6-b02",
            "builtAt": "2026-09-19T00:00:00Z"}


def _подробности(catalog):
    details = {}
    for it in catalog["items"]:
        details[it["slug"]] = {
            "id": f"id-{it['slug']}",
            "description": f"Desc {it['slug']}",
            "genres": ["драма"], "genre_codes": ["drama"],
            "countries": ["США"],
            "sources": [{"provider": "kp", "source_id": "1",
                         "availability_status": "available"}],
            "external_ids": {"kp": "1"}, "playable": True,
            "imdb_rating": 7.0,
            "ratings_by_source": {"imdb": {"value": 7.0, "votes": 3, "source": "imdb"}},
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
        "build_id": "PASS6B02", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-19T00:00:00Z",
    }), encoding="utf-8")
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona Pass6 B02"
    os.environ["LORDS_CLOCK_ISO"] = "2026-09-19T12:00:00Z"
    try:
        имя = "nova_zona_pass6_b02"
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


@pytest.fixture(scope="module")
def зона(tmp_path_factory):
    return _поднять(tmp_path_factory.mktemp("zona-pass6-b02"))


def test_shell_css_mobile_padding_matches_single_row_header(зона):
    css = зона.ЗОНА_СТИЛЬ
    assert "padding-top:117px" not in css
    # B01: 56 / 62 / 70 body offset for 390 / tablet / desktop header heights.
    assert re.search(r"body\{[^}]*padding-top:56px", css, re.S)
    assert "padding-top:62px" in css
    assert "padding-top:70px" in css
    assert "min-height:44px" in css
    assert re.search(r"\.zhd__menu\{[^}]*width:44px", css, re.S)
    assert "outline:2px solid" in css
    assert "height:56px" in css and "height:70px" in css


def test_home_renders_header_nav_search_no_side_rail(зона):
    о = запросить(зона, "/")
    assert о.статус == 200
    assert 'class="zhd"' in о.тело
    assert "zhd__menu" in о.тело
    assert 'action="/search/"' in о.тело
    # B01 contract labels (not abstract «Обзор»).
    assert "Главная" in о.тело
    assert "Новинки" in о.тело
    assert "Фильмы" in о.тело
    assert "Каталог" in о.тело
    assert "Обзор" not in о.тело
    assert "СКРИПТ_ЗОНА_ШАПКА" not in о.тело  # source name never leaks
    assert "zhd-nav" in о.тело
    assert 'data-empty-submit="forbid"' in о.тело
    assert "noindex" in о.тело
    # Side genre rail must stay suppressed in CSS, not stuck to the page.
    assert "zrail" in зона.ЗОНА_СТИЛЬ
    assert re.search(r"\.zrail[^\{]*\{display:none\}", зона.ЗОНА_СТИЛЬ) or \
           ".zrail,.zrail__logo" in зона.ЗОНА_СТИЛЬ


def test_locked_card_grid_untouched(зона):
    assert "repeat(7," in зона.ЗОНА_СТИЛЬ
    assert "repeat(8," in зона.ЗОНА_СТИЛЬ
    assert "--z-card-max:180px" in зона.ЗОНА_СТИЛЬ
