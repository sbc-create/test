"""Zona blockwise B14–B21 presentation fixes."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

ИСХОДНИК = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"


def _каталог(n=50):
    items = []
    for i in range(n):
        kind = "Фильм" if i % 3 != 1 else "Сериал"
        items.append({
            "slug": f"t-{i:04d}", "title": f"Картина {i:04d}", "kind": kind,
            "year": 2000 + (i % 20), "poster": f"https://poster.example/{i}.webp",
            "url": f"/title/t-{i:04d}/",
            "published_at": f"2026-08-{(i % 28) + 1:02d}T00:00:00Z",
        })
    # Dedicated series with seasons for B18/B20.
    items.append({
        "slug": "show-multi", "title": "Многосезонный сериал", "kind": "Сериал",
        "year": 2022, "poster": "https://poster.example/show.webp",
        "url": "/title/show-multi/",
        "published_at": "2026-09-01T00:00:00Z",
    })
    return {"version": 2, "count": len(items), "items": items, "site": "zona-01",
            "schema": "nova-catalog/2.0.0", "revision": "b14b21",
            "builtAt": "2026-09-20T00:00:00Z"}


def _подробности(catalog):
    details = {}
    for i, it in enumerate(catalog["items"]):
        playable = i % 5 != 0  # mix for B19
        short = f"Short {it['slug']}"
        if it["slug"] == "t-0001":
            full = "X" * 100  # short full text → no expand
        elif it["slug"] == "t-0002":
            full = "Y" * 400  # long → expand
        else:
            full = f"Full description for {it['slug']}."
        details[it["slug"]] = {
            "id": f"id-{it['slug']}",
            "description": full,
            "short_description": short if it["slug"] in ("t-0001", "t-0002") else full,
            "genres": ["драма"], "genre_codes": ["drama"],
            "countries": ["США"],
            "sources": [{"provider": "kp", "source_id": "1",
                         "availability_status": "available"}],
            "external_ids": {"kp": "1"}, "playable": playable,
            "imdb_rating": 6.0 + (i % 30) / 10.0,
            "ratings_by_source": {
                "imdb": {"value": 6.0 + (i % 30) / 10.0, "votes": 10, "source": "imdb"}},
        }
        if it["kind"] == "Сериал" and it["slug"] != "show-multi":
            details[it["slug"]]["seasons"] = [
                {"n": 1, "eps": 5, "avail": 3},
            ]
    details["show-multi"] = {
        "id": "id-show-multi",
        "description": "A show with several seasons.",
        "short_description": "A show with several seasons.",
        "genres": ["драма"], "genre_codes": ["drama"],
        "countries": ["США"],
        "sources": [{"provider": "kp", "source_id": "99",
                     "availability_status": "available"}],
        "external_ids": {"kp": "99"}, "playable": True,
        "imdb_rating": 8.0,
        "ratings_by_source": {
            "imdb": {"value": 8.0, "votes": 100, "source": "imdb"}},
        "seasons": [
            {"n": 1, "eps": 4, "avail": 4},
            {"n": 2, "eps": 3, "avail": 2},
        ],
    }
    # Same short==full path for t-0003 with long text (elif полное branch).
    details["t-0003"]["short_description"] = details["t-0003"]["description"] = "Z" * 400
    details["t-0004"]["short_description"] = details["t-0004"]["description"] = "W" * 80
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
        "build_id": "B14B21", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona B14"
    os.environ["LORDS_CLOCK_ISO"] = "2026-09-20T12:00:00Z"
    try:
        имя = f"nova_zona_b14_{tmp_path.name}"
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


# --- B14 Search ----------------------------------------------------------

def test_b14_empty_q_no_catalog_dump(зона):
    о = запросить(зона, "/search/")
    assert о.статус == 200
    assert "Запрос пуст" in о.тело
    assert 'data-testid="catalog-grid"' not in о.тело
    # Must not dump catalog title cards into empty search
    grid_titles = re.findall(r'href="/title/t-\d{4}/"', о.тело)
    assert len(grid_titles) == 0


def test_b14_long_q_clamped(зона):
    long_q = "A" * 150
    о = запросить(зона, f"/search/?q={long_q}")
    assert о.статус == 200
    assert "120" in о.тело  # clamp note
    # Input preserves clamped value (≤120)
    m = re.search(r'id="q" name="q" value="([^"]*)"', о.тело)
    assert m
    assert len(m.group(1)) <= 120


def test_b14_page2_works(зона):
    о = запросить(зона, "/search/?q=%D0%9A%D0%B0%D1%80%D1%82%D0%B8%D0%BD%D0%B0&page=2")
    assert о.статус == 200
    assert 'data-testid="pagination"' in о.тело or "zpg" in о.тело
    m = re.search(r'rel="canonical" href="([^"]+)"', о.тело)
    assert m
    assert "page=2" in m.group(1)
    assert "page=1" not in m.group(1)


def test_b14_invalid_page_404(зона):
    о = запросить(зона, "/search/?q=%D0%9A%D0%B0%D1%80%D1%82%D0%B8%D0%BD%D0%B0&page=99999")
    assert о.статус == 404


def test_b14_page1_canonical_without_page(зона):
    о = запросить(зона, "/search/?q=%D0%9A%D0%B0%D1%80%D1%82%D0%B8%D0%BD%D0%B0")
    m = re.search(r'rel="canonical" href="([^"]+)"', о.тело)
    assert m
    assert "page=" not in m.group(1)
    assert "q=" in m.group(1)


# --- B15 Breadcrumb + passport -------------------------------------------

def test_b15_breadcrumb_list_and_films_label(зона):
    о = запросить(зона, "/title/t-0000/")
    assert о.статус == 200
    assert "BreadcrumbList" in о.тело
    assert ">Фильмы<" in о.тело or ">Фильмы<" in о.тело.replace("&nbsp;", " ")
    assert 'href="/movies/"' in о.тело
    assert ">Кино<" not in о.тело.split("zcr", 1)[-1][:400] if "zcr" in о.тело else True


def test_b15_series_crumb_uses_series_path(зона):
    о = запросить(зона, "/title/show-multi/season-1/")
    assert о.статус == 200
    assert 'href="/series/"' in о.тело
    assert "/catalog/?kind=" not in о.тело.split("zcr", 1)[-1][:500]


# --- B16 Description expand ----------------------------------------------

def test_b16_short_description_no_expand(зона):
    # t-0001: short≠full but full len=100 < 320 → no expand button
    о = запросить(зона, "/title/t-0001/")
    assert "data-expand-plot" not in о.тело
    # t-0004: short==full, very short → no expand
    о2 = запросить(зона, "/title/t-0004/")
    assert "data-expand-plot" not in о2.тело


def test_b16_long_description_has_expand(зона):
    о = запросить(зона, "/title/t-0002/")
    assert "data-expand-plot" in о.тело
    assert "Развернуть" in о.тело
    о3 = запросить(зона, "/title/t-0003/")
    assert "data-expand-plot" in о3.тело


# --- B17 Player contract -------------------------------------------------

def test_b17_player_contract_attr(зона):
    о = запросить(зона, "/title/t-0000/")
    assert 'data-player-contract="cdnvideohub-player-v1"' in о.тело


# --- B18 Season tabs -----------------------------------------------------

def test_b18_multi_season_tabs(зона):
    о = запросить(зона, "/title/show-multi/")
    assert 'data-testid="season-tabs"' in о.тело
    assert "Сезон 1" in о.тело and "Сезон 2" in о.тело


def test_b18_single_season_no_tabs(зона):
    # First serial in fixture with one season
    serial = next(з for з in зона.Обработчик.данные.items
                  if з["kind"] == "Сериал" and з["slug"] != "show-multi")
    о = запросить(зона, serial["url"])
    assert 'data-testid="season-tabs"' not in о.тело


# --- B19 Recommendations -------------------------------------------------

def test_b19_related_excludes_current_and_policy(зона):
    о = запросить(зона, "/title/t-0003/")
    assert о.статус == 200
    assert 'data-rec-policy="playable_preferred_with_explicit_nonplayable_state_v1"' in о.тело
    section = о.тело.split('data-testid="related-grid"', 1)[1] if 'related-grid' in о.тело else ""
    assert "/title/t-0003/" not in section.split("</section>", 1)[0]


def test_b19_playable_before_nonplayable(зона):
    описание = зона.СЕМЕЙСТВА_1_1["zona"]
    в = зона.ВИДЫ_1_1[описание["вид"]](
        описание, зона.Обработчик.данные, зона.Обработчик.подробности,
        зона.Обработчик.индекс, "Zona B14")
    запись = next(з for з in зона.Обработчик.данные.items if з["slug"] == "t-0003")
    деталь = зона.Обработчик.подробности.get("t-0003")
    похожие = в.похожие(запись, деталь, сколько=12)
    assert all(з["slug"] != "t-0003" for з in похожие)
    playable_flags = [
        (зона.Обработчик.подробности.get(з["slug"]) or {}).get("playable") is True
        for з in похожие]
    if True in playable_flags and False in playable_flags:
        first_non = playable_flags.index(False)
        assert all(playable_flags[:first_non])
        assert not any(playable_flags[first_non:])


# --- B20 Exact episode page ----------------------------------------------

def test_b20_episode_player_before_list_and_nav(зона):
    о = запросить(зона, "/title/show-multi/season-1/episode-2/")
    assert о.статус == 200
    player_pos = о.тело.find('class="zpl"')
    list_pos = о.тело.find("Серии")
    assert player_pos != -1 and list_pos != -1
    assert player_pos < list_pos
    assert 'aria-label="Соседние серии"' in о.тело or "zepnav" in о.тело
    # list nav link present
    assert "/title/show-multi/" in о.тело
    assert 'href="/series/"' in о.тело
    assert "BreadcrumbList" in о.тело


# --- B21 Collections -----------------------------------------------------

def test_b21_collection_hub_card_count(зона):
    о = запросить(зона, "/collections/")
    assert о.статус == 200
    # Hub may be empty without contract hits; when cards exist they show count
    if 'data-testid="collection-card"' in о.тело:
        assert re.search(r"\d+\s+назван", о.тело)
    # Subline total of published hub cards when any
    if 'data-testid="collection-grid"' in о.тело:
        assert re.search(r"\d+\s+подбор", о.тело) or "подборок" in о.тело or "подборки" in о.тело
