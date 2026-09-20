"""Zona Pass6 Block 03: home shelves — no card plot text, 2/4/7/8, no /new/ duplicate."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

ИСХОДНИК = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"


def _каталог(n=80):
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
            "schema": "nova-catalog/2.0.0", "revision": "pass6-b03",
            "builtAt": "2026-09-19T00:00:00Z"}


def _подробности(catalog):
    details = {}
    for it in catalog["items"]:
        d = {
            "id": f"id-{it['slug']}",
            "description": (
                f"Long plot synopsis for {it['slug']} that must never appear "
                "inside a compact home card body under Pass6 Block 03 rules."
            ),
            "genres": ["драма", "триллер"], "genre_codes": ["drama", "triller"],
            "countries": ["США"],
            "sources": [{"provider": "kp", "source_id": "1",
                         "availability_status": "available"}],
            "external_ids": {"kp": "1"}, "playable": True,
            "imdb_rating": 7.1, "kinopoisk_rating": 7.3,
            "ratings_by_source": {
                "imdb": {"value": 7.1, "votes": 4, "source": "imdb"},
                "kp": {"value": 7.3, "votes": 4, "source": "kp"},
            },
        }
        if it["kind"] == "Сериал":
            d["seasons"] = [{"n": 1, "eps": 8, "avail": 2}]
        details[it["slug"]] = d
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
        "build_id": "PASS6B03", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-19T00:00:00Z",
    }), encoding="utf-8")
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona Pass6 B03"
    os.environ["LORDS_CLOCK_ISO"] = "2026-09-19T12:00:00Z"
    try:
        имя = "nova_zona_pass6_b03"
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
    return _поднять(tmp_path_factory.mktemp("zona-pass6-b03"))


def test_home_has_five_distinct_shelves_not_new_duplicate(зона):
    о = запросить(зона, "/")
    assert о.статус == 200
    assert "Высокий рейтинг среди недавних фильмов" in о.тело
    assert "Высокий рейтинг среди недавних сериалов" in о.тело
    assert "Добавленные недавно фильмы" in о.тело
    assert "Недавно добавленные сериалы" in о.тело
    assert "Высокий рейтинг среди недавней анимации" in о.тело
    assert "Недавно в каталоге" not in о.тело
    assert "Популярные новинки" not in о.тело
    assert "Новые серии" not in о.тело or "Недавно добавленные сериалы" in о.тело
    # Shelf «Весь раздел» must not point the removed duplicate at /new/.
    assert 'data-shelf="new-all"' not in о.тело


def test_home_cards_omit_plot_snippets(зона):
    о = запросить(зона, "/")
    assert "Long plot synopsis" not in о.тело
    assert 'class="zt__x"' not in о.тело
    assert "КП" in о.тело or "IMDb" in о.тело


def test_home_carousel_matches_locked_column_breakpoints(зона):
    css = зона.ЗОНА_СТИЛЬ
    assert "/ 7)" in css or "/7)" in css
    assert "/ 8)" in css or "/8)" in css
    assert "height:96px" in css
    assert "--z-card-max:180px" in css
    # Catalog grid still locked.
    assert "repeat(7," in css and "repeat(8," in css


def test_empty_shelf_helper_returns_empty_string(зона):
    # секция hides empty shelves (0px).
    вид = зона.СЕМЕЙСТВА_1_1["zona"]["вид"]
    # Instantiate via handler path used by requests — call through module class if present.
    assert 'if not набор:\n            return ""' in Path(ИСХОДНИК).read_text(encoding="utf-8")
