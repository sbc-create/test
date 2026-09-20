"""Zona blockwise B13 /new/ temporal modes."""
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
        {"slug": "prem-old", "title": "Old Premiere", "kind": "Фильм", "year": 2019,
         "poster": "https://poster.example/a.webp", "url": "/title/prem-old/",
         "published_at": "2026-01-01T00:00:00Z"},
        {"slug": "prem-future", "title": "Future Premiere", "kind": "Фильм", "year": 2027,
         "poster": "https://poster.example/b.webp", "url": "/title/prem-future/",
         "published_at": "2026-09-01T00:00:00Z"},
        {"slug": "added-only", "title": "Added Only", "kind": "Сериал", "year": 2020,
         "poster": "https://poster.example/c.webp", "url": "/title/added-only/",
         "published_at": "2026-09-18T00:00:00Z"},
        {"slug": "both", "title": "Both Dates", "kind": "Фильм", "year": 2024,
         "poster": "https://poster.example/d.webp", "url": "/title/both/",
         "published_at": "2026-09-19T12:00:00Z"},
    ]
    return {"version": 2, "count": len(items), "items": items, "site": "zona-01",
            "schema": "nova-catalog/2.0.0", "revision": "b13",
            "builtAt": "2026-09-20T00:00:00Z"}


def _подробности():
    return {
        "schema": "nova-details/1.0.0", "site": "zona-01",
        "details_total": 4, "source": "test", "items_total": 4,
        "details": {
            "prem-old": {
                "id": "1", "description": "d", "genres": ["драма"], "genre_codes": ["drama"],
                "countries": ["США"], "premiere_date": "2019-05-01",
                "sources": [{"provider": "kp", "source_id": "1", "availability_status": "available"}],
                "external_ids": {"kp": "1"}, "playable": True,
            },
            "prem-future": {
                "id": "2", "description": "d", "genres": ["драма"], "genre_codes": ["drama"],
                "countries": ["США"], "premiere_date": "2027-01-15",
                "sources": [{"provider": "kp", "source_id": "2", "availability_status": "available"}],
                "external_ids": {"kp": "2"}, "playable": True,
            },
            "added-only": {
                "id": "3", "description": "d", "genres": ["комедия"], "genre_codes": ["komediya"],
                "countries": ["США"],
                # no premiere_date — only catalog published_at
                "sources": [{"provider": "kp", "source_id": "3", "availability_status": "available"}],
                "external_ids": {"kp": "3"}, "playable": True,
            },
            "both": {
                "id": "4", "description": "d", "genres": ["боевик"], "genre_codes": ["action"],
                "countries": ["США"], "premiere_date": "2024-03-10",
                "sources": [{"provider": "kp", "source_id": "4", "availability_status": "available"}],
                "external_ids": {"kp": "4"}, "playable": True,
            },
        },
    }


def _поднять(tmp_path):
    корень = tmp_path / "zona-01"
    корень.mkdir(parents=True, exist_ok=True)
    (корень / "zona-01-catalog.json").write_text(
        json.dumps(_каталог(), ensure_ascii=False), encoding="utf-8")
    (корень / "zona-01-details.json").write_text(
        json.dumps(_подробности(), ensure_ascii=False), encoding="utf-8")
    (корень / "player-zona-01.json").write_text(
        json.dumps({"publisher_id": "10238", "source_mode": "provider-id"}),
        encoding="utf-8")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "zona",
        "design_version": "1.2.0", "source_commit": "0" * 40,
        "build_id": "B13", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona B13"
    os.environ["LORDS_CLOCK_ISO"] = "2026-09-20T12:00:00Z"
    try:
        имя = f"nova_zona_b13_{tmp_path.name}"
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


def test_b13_default_new_is_premiere_ledger(зона):
    о = запросить(зона, "/new/")
    assert о.статус == 200
    assert "Премьеры" in о.тело
    assert "в этой ленте" in о.тело
    assert "/title/prem-old/" in о.тело
    assert "/title/both/" in о.тело
    assert "/title/prem-future/" in о.тело
    # added-only has no premiere → absent from premiere mode
    assert "/title/added-only/" not in о.тело.split('data-testid="catalog-grid"', 1)[1]


def test_b13_mode_added_uses_published_at(зона):
    о = запросить(зона, "/new/?mode=added")
    assert о.статус == 200
    assert "Добавлено на сайт" in о.тело
    assert "Добавлено ·" in о.тело
    assert "/title/added-only/" in о.тело
    assert "data-testid=\"new-mode-tabs\"" in о.тело
    # Must not label added feed with premiere copy as H1
    assert re.search(r'id="catalog-h1">Добавлено на сайт<', о.тело)


def test_b13_future_premiere_labeled_expected(зона):
    о = запросить(зона, "/new/")
    assert "Ожидается · 15.01.2027" in о.тело
    assert "Добавлено · 15.01.2027" not in о.тело


def test_b13_home_cta_added_matches_mode(зона):
    home = запросить(зона, "/")
    assert "/new/?mode=added" in home.тело
    о = запросить(зона, "/new/?mode=added")
    assert о.статус == 200
    assert "/title/both/" in о.тело


def test_b13_no_provider_episode_tabs_without_ledger(зона):
    о = запросить(зона, "/new/")
    assert "Стало доступно" not in о.тело
    assert "Новые серии" not in о.тело
    # Direct hit on unsupported mode → honest empty, not neighbour fill
    о2 = запросить(зона, "/new/?mode=available")
    assert о2.статус == 200
    grid = о2.тело.split('data-testid="catalog-grid"', 1)[1]
    assert "/title/" not in grid or "Ничего не подошло" in о2.тело
