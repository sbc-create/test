"""Animedia home episode feed: events, pagination, timestamps, density contracts."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "automation" / "host"
FRONTEND = HOST / "lords-frontend.py"


def _load(tmp: Path, *, n_titles: int = 25, version: str = "1.2.3"):
    manifest = {
        "schema_version": 1,
        "template_family": "animedia",
        "design_version": version,
        "source_commit": "a" * 40,
        "runtime_commit": "b" * 40,
        "build_id": "home-pag-test",
        "artifact_sha256": "c" * 64,
        "profile": "animedia-space",
        "built_at": "2026-09-19T00:00:00Z",
    }
    (tmp / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    items = []
    details = {}
    for i in range(n_titles):
        slug = f"title-{i:03d}"
        items.append(
            {
                "slug": slug,
                "title": f"Тайтл {i}",
                "kind": "Аниме",
                "year": 2020 + (i % 5),
                "published_at": f"2026-09-{(19 - (i % 18)):02d}T{(8 + i % 12):02d}:15:00Z",
                "poster": f"/poster/{i}.webp",
                "url": f"/title/{slug}/",
                "id": f"uuid-{i}",
            }
        )
        details[slug] = {
            "id": f"uuid-{i}",
            "playable": True,
            "seasons": [{"n": 1, "eps": 24, "avail": max(1, (i % 20) + 1)}],
        }
    # one title without seasons — ineligible
    items.append(
        {
            "slug": "movie-only",
            "title": "Только фильм",
            "kind": "Аниме",
            "year": 2024,
            "published_at": "2026-09-19T20:00:00Z",
            "poster": "",
            "url": "/title/movie-only/",
            "id": "uuid-movie",
        }
    )
    details["movie-only"] = {"id": "uuid-movie", "playable": True, "seasons": []}
    # duplicate avail mapping should dedupe
    (tmp / "catalog.json").write_text(
        json.dumps({"items": items, "revision": "r1", "count": len(items)}),
        encoding="utf-8",
    )
    (tmp / "details.json").write_text(
        json.dumps({"catalog_revision": "r1", "details": details}),
        encoding="utf-8",
    )
    (tmp / "player.json").write_text(
        json.dumps({"publisher_id": "pub", "token": "tok"}), encoding="utf-8"
    )
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(tmp / "manifest.json")
    os.environ["LORDS_CATALOG"] = str(tmp / "catalog.json")
    os.environ["LORDS_DETAILS"] = str(tmp / "details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(tmp / "player.json")
    os.environ["LORDS_TEMPLATE_FAMILY"] = "animedia"
    os.environ["LORDS_SITE_NAME"] = "Animedia"
    os.environ["LORDS_PUBLIC_ORIGIN"] = "https://animedia.space"
    for key in list(sys.modules):
        if "lords" in key and "frontend" in key:
            del sys.modules[key]
    name = f"animedia_home_pag_{tmp.name}"
    spec = importlib.util.spec_from_file_location(name, FRONTEND)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod, items, details


def _вид(mod, items, details, host="animedia.space"):
    данные = mod.Данные.__new__(mod.Данные)
    данные.items = [dict(з) for з in items]
    for з in данные.items:
        з["_n"] = mod.нормализовать(з["title"])
        з["_формы"] = [з["_n"]]
    данные.years = sorted({з["year"] for з in данные.items}, reverse=True)
    данные.kinds = ["Аниме"]
    данные.absent = []
    подроб = mod.Подробности.__new__(mod.Подробности)
    подроб.записи = details
    подроб.источник = ""
    подроб.покрытие = len(details)
    подроб.catalog_revision = "r1"
    подроб.catalog_built_at = ""
    индекс = mod.построить_индекс(данные, подроб)
    вид = mod.ВидАнимедиа(mod.СЕМЕЙСТВА_1_1["animedia"], данные, подроб, индекс, "Animedia")
    вид.хост = host
    return вид


def _ids(html: str) -> list[str]:
    return re.findall(r'data-event-id="([^"]+)"', html)


@pytest.fixture()
def fe(tmp_path):
    return _load(tmp_path, n_titles=25)


class TestEpisodeEvents:
    def test_inventory_eligibility_and_dedupe(self, fe):
        mod, items, details = fe
        вид = _вид(mod, items, details)
        events = вид._эпизод_события()
        assert len(events) == 25  # movie-only excluded
        keys = [(e["title_id"], e["season_number"], e["episode_number"], e["source_episode_id"]) for e in events]
        assert len(keys) == len(set(keys))
        for e in events:
            assert e["episode_number"] > 0
            assert e["url"].startswith("/title/")
            assert e["published_at_precision"] in {"datetime", "date", "none"}
            assert e["source_provenance"]

    def test_deterministic_sort(self, fe):
        mod, items, details = fe
        вид = _вид(mod, items, details)
        a = [e["event_id"] for e in вид._эпизод_события()]
        b = [e["event_id"] for e in вид._эпизод_события()]
        assert a == b
        pubs = [e["published_at"] for e in вид._эпизод_события()]
        assert pubs == sorted(pubs, reverse=True)

    def test_timestamp_semantics(self, fe):
        mod, _, _ = fe
        assert "Сегодня" in mod._аниме_формат_времени_анонса("2026-09-19T18:01:00Z", "datetime") or \
               "19.09.2026" in mod._аниме_формат_времени_анонса("2026-09-19T18:01:00Z", "datetime")
        date_only = mod._аниме_формат_времени_анонса("2026-09-18", "date")
        assert date_only == "18.09.2026"
        assert "00:00" not in date_only
        assert "Сегодня" not in date_only
        assert mod._аниме_формат_времени_анонса("", "none") == ""


class TestPagination:
    def test_home_top10_matches_new_page1(self, fe):
        mod, items, details = fe
        вид = _вид(mod, items, details)
        home = вид.главная()
        p1 = вид.список("/new", {})
        assert _ids(home) == _ids(p1)
        assert len(_ids(home)) == 10
        assert "ahome-eps" in home
        assert "/new/?page=2" in home
        assert 'aria-current="page"' in home

    def test_pages_partition_full_set(self, fe):
        mod, items, details = fe
        вид = _вид(mod, items, details)
        events = вид._эпизод_события()
        p1 = _ids(вид.список("/new", {}))
        p2 = _ids(вид.список("/new", {"page": ["2"]}))
        p3 = _ids(вид.список("/new", {"page": ["3"]}))
        assert len(p1) == 10 and len(p2) == 10 and len(p3) == 5
        assert set(p1).isdisjoint(p2)
        assert set(p2).isdisjoint(p3)
        assert set(p1) | set(p2) | set(p3) == {e["event_id"] for e in events}

    def test_invalid_pages_are_404(self, fe):
        mod, items, details = fe
        вид = _вид(mod, items, details)
        for raw in ("0", "-1", "abc", "99"):
            html = вид.список("/new", {"page": [raw]})
            assert "не найдена" in html.lower() or "404" in html
            assert getattr(вид, "_http_status", 200) == 404
        вид.список("/new", {})
        assert getattr(вид, "_http_status", 200) == 200

    def test_canonical_page_urls(self, fe):
        mod, items, details = fe
        вид = _вид(mod, items, details)
        p1 = вид.список("/new", {})
        p2 = вид.список("/new", {"page": ["2"]})
        assert 'rel="canonical" href="https://animedia.space/new/"' in p1
        assert 'rel="canonical" href="https://animedia.space/new/?page=2"' in p2

    def test_prev_next_states(self, fe):
        mod, items, details = fe
        вид = _вид(mod, items, details)
        p1 = вид.список("/new", {})
        p3 = вид.список("/new", {"page": ["3"]})
        assert 'aria-disabled="true">←' in p1 or "←" in p1
        assert 'rel="next"' in p1
        assert 'rel="prev"' in p3
        assert 'aria-disabled="true">→' in p3 or p3.count("→") >= 1


class TestCssIsolation:
    def test_density_rules_are_namespaced(self, fe):
        mod, _, _ = fe
        css = mod.АНИМЕДИА_СТИЛЬ
        assert ".ahome-eps" in css
        assert "height:82px" in css
        assert "width:64px" in css
        # must not rewrite global article/img card player
        assert "article{" not in css.replace(" ", "")
        assert ".ahero .zrl__track>*" in css
        assert "168px" in css


class TestDomainConsistency:
    def test_icu_and_space_share_event_order(self, fe):
        mod, items, details = fe
        a = [e["event_id"] for e in _вид(mod, items, details, "animedia.icu")._эпизод_события()]
        b = [e["event_id"] for e in _вид(mod, items, details, "animedia.space")._эпизод_события()]
        assert a == b
