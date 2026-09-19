"""Zona Pass6 Block 04: title detail — no right rail, facts-only metadata, one description."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

ИСХОДНИК = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"


def _каталог():
    items = [
        {"slug": "full-meta", "title": "Full Meta Film", "kind": "Фильм", "year": 2024,
         "poster": "https://poster.example/full.webp", "url": "/title/full-meta/",
         "published_at": "2026-09-01T00:00:00Z"},
        {"slug": "no-desc", "title": "No Description", "kind": "Фильм", "year": 2020,
         "poster": "", "url": "/title/no-desc/",
         "published_at": "2026-09-02T00:00:00Z"},
        {"slug": "long-series", "title": "Very Long Series Title That Wraps Nicely Across Lines",
         "kind": "Сериал", "year": 2026,
         "poster": "https://poster.example/series.webp", "url": "/title/long-series/",
         "published_at": "2026-09-03T00:00:00Z"},
        {"slug": "no-rating", "title": "Unrated Title", "kind": "Фильм", "year": 2019,
         "poster": "https://poster.example/nr.webp", "url": "/title/no-rating/",
         "published_at": "2026-09-04T00:00:00Z"},
    ]
    return {"version": 2, "count": len(items), "items": items, "site": "zona-01",
            "schema": "nova-catalog/2.0.0", "revision": "pass6-b04",
            "builtAt": "2026-09-19T00:00:00Z"}


def _подробности(catalog):
    details = {
        "full-meta": {
            "id": "id-full", "description": "A" * 400,
            "short_description": "Short plot.",
            "original_name": "Full Meta Original",
            "genres": ["драма", "триллер"], "genre_codes": ["drama", "triller"],
            "countries": ["США"], "duration": 120, "status": "завершён",
            "age_rating": "16+",
            "sources": [{"provider": "kp", "source_id": "1",
                         "availability_status": "available"}],
            "playable": True, "imdb_rating": 7.8, "kinopoisk_rating": 7.5,
            "ratings_by_source": {
                "imdb": {"value": 7.8, "votes": 6, "source": "imdb"},
                "kp": {"value": 7.5, "votes": 10, "source": "kp"},
            },
        },
        "no-desc": {
            "id": "id-nodesc", "genres": ["комедия"], "genre_codes": ["comedy"],
            "countries": ["Россия"],
            "sources": [{"provider": "kp", "source_id": "2",
                         "availability_status": "available"}],
            "playable": True, "imdb_rating": 6.0,
            "ratings_by_source": {"imdb": {"value": 6.0, "votes": 2, "source": "imdb"}},
        },
        "long-series": {
            "id": "id-series",
            "description": "Series plot " + ("word " * 80),
            "original_name": "长标题",
            "genres": ["дорама"], "genre_codes": ["dorama"],
            "countries": ["Китай"],
            "seasons": [{"n": 1, "eps": 30, "avail": 6}],
            "sources": [{"provider": "kp", "source_id": "3",
                         "availability_status": "available"}],
            "playable": True, "imdb_rating": 7.8,
            "ratings_by_source": {"imdb": {"value": 7.8, "votes": 6, "source": "imdb"}},
        },
        "no-rating": {
            "id": "id-nr", "description": "Has plot but no scores.",
            "genres": ["боевик"], "genre_codes": ["action"],
            "countries": ["США"],
            "sources": [{"provider": "kp", "source_id": "4",
                         "availability_status": "available"}],
            "playable": True,
        },
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
        "build_id": "PASS6B04", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-19T00:00:00Z",
    }), encoding="utf-8")
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona Pass6 B04"
    os.environ["LORDS_CLOCK_ISO"] = "2026-09-19T12:00:00Z"
    try:
        имя = "nova_zona_pass6_b04_v2"
        sys.modules.pop(имя, None)
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
    return _поднять(tmp_path_factory.mktemp("zona-pass6-b04"))


def test_title_has_no_right_rail(зона):
    о = запросить(зона, "/title/long-series/")
    assert о.статус == 200
    assert 'class="ztitle__rail"' not in о.тело
    assert 'class="ztitle__dl"' not in о.тело
    assert 'data-testid="title-facts"' in о.тело
    assert "Серии" in о.тело  # merged into facts
    assert о.тело.count('id="synopsis"') <= 1
    assert 'href="#watch"' in о.тело
    assert 'data-player' in о.тело


def test_title_facts_only_real_values(зона):
    о = запросить(зона, "/title/full-meta/")
    assert "Продолжительность" in о.тело or "Время" in о.тело
    assert "Статус" in о.тело
    assert "Возраст" in о.тело
    assert "Short plot." in о.тело
    # Genre chips present; not duplicated as a Жанры fact row.
    assert о.тело.count("<dt>Жанры</dt>") == 0


def test_title_without_description_has_no_empty_plot_block(зона):
    о = запросить(зона, "/title/no-desc/")
    assert 'id="synopsis"' not in о.тело
    assert 'class="ztitle__desc' not in о.тело
    assert "data-expand-plot" not in о.тело


def test_title_without_rating_single_none_message(зона):
    о = запросить(зона, "/title/no-rating/")
    assert о.тело.count("Оценок пока нет") <= 1


def test_title_css_is_two_column_not_three(зона):
    css = зона.ЗОНА_СТИЛЬ
    assert "260px minmax(0,1fr) 280px" not in css
    assert "max-height:500px" not in css
    assert ".ztitle__rail{display:none}" in css
