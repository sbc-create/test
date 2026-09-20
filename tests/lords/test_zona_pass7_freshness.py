"""Zona Pass7: content freshness contracts — shelves, timestamps, cache, reload."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

ИСХОДНИК = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"
КОНТРАКТ = Path(__file__).resolve().parents[2] / "automation" / "host" / "collection_contract.py"


def _item(i: int, *, kind=None, published_day=None, year=None, rating=None):
    kind = kind or ("Фильм" if i % 3 == 0 else ("Сериал" if i % 3 == 1 else "Мультфильм"))
    day = published_day if published_day is not None else (i % 28) + 1
    return {
        "slug": f"t-{i:04d}", "title": f"Title {i:04d}", "kind": kind,
        "year": year if year is not None else 2020 + (i % 6),
        "poster": f"https://poster.example/{i}.webp",
        "url": f"/title/t-{i:04d}/",
        "published_at": f"2026-09-{day:02d}T00:00:00Z",
        "published_at_estimated": False,
        "_test_rating": rating,
    }


def _каталог(items):
    return {
        "version": 2, "count": len(items), "items": items, "site": "zona-01",
        "schema": "nova-catalog/2.0.0", "revision": "pass7-rev-a",
        "builtAt": "2026-09-20T03:16:30Z",
    }


def _подробности(items):
    details = {}
    for it in items:
        rating = it.pop("_test_rating", None)
        d = {
            "id": f"id-{it['slug']}", "playable": True,
            "genres": ["драма", "триллер"], "genre_codes": ["drama", "triller"],
            "countries": ["США"],
            "sources": [{"provider": "kp", "source_id": "1",
                         "availability_status": "available"}],
            "external_ids": {"kp": "1"},
            "premiere_date": f"{it['year']}-06-15",
        }
        if rating:
            d["imdb_rating"] = rating
            d["kinopoisk_rating"] = rating
            d["ratings_by_source"] = {
                "imdb": {"value": rating, "votes": 10, "source": "imdb"},
            }
        elif rating is None:
            d["imdb_rating"] = 7.0
            d["kinopoisk_rating"] = 7.0
            d["ratings_by_source"] = {
                "imdb": {"value": 7.0, "votes": 10, "source": "imdb"},
            }
        # rating == 0 → intentionally no score (recently-added only)
        if it["kind"] == "Сериал":
            d["seasons"] = [{"n": 1, "eps": 8, "avail": 2}]
        details[it["slug"]] = d
    # Special cases for contract tests.
    if "new-film" in details:
        details["new-film"]["premiere_date"] = "2026-09-15"
    if "backfill" in details:
        details["backfill"]["premiere_date"] = "1985-06-01"
    if "future-film" in details:
        details["future-film"]["premiere_date"] = "2027-01-01"
    if "rated-film" in details:
        details["rated-film"]["imdb_rating"] = 9.8
        details["rated-film"]["kinopoisk_rating"] = 9.7
        details["rated-film"]["ratings_by_source"] = {
            "imdb": {"value": 9.8, "votes": 100, "source": "imdb"},
        }
    return {
        "schema": "nova-details/1.0.0", "site": "zona-01",
        "details_total": len(details), "source": "test",
        "catalog_revision": "pass7-rev-a",
        "items_total": len(details), "details": details,
    }


def _база_items():
    items = [_item(i) for i in range(90)]
    # Named fixtures — published_at AFTER any base day (base uses Sep 01–28).
    specials = [
        {"slug": "new-film", "title": "New Film", "kind": "Фильм", "year": 2024,
         "published_at": "2026-10-02T12:00:00Z", "_test_rating": 0},
        {"slug": "old-film", "title": "Old Film", "kind": "Фильм", "year": 1999,
         "published_at": "2026-08-01T00:00:00Z", "_test_rating": 0},
        {"slug": "future-film", "title": "Future Film", "kind": "Фильм", "year": 2027,
         "published_at": "2026-09-18T00:00:00Z", "_test_rating": 0},
        {"slug": "backfill", "title": "Backfill Classic", "kind": "Фильм", "year": 1985,
         "published_at": "2026-10-02T11:00:00Z", "_test_rating": 0},
        {"slug": "old-series", "title": "Old Series", "kind": "Сериал", "year": 2020,
         "published_at": "2026-08-02T00:00:00Z", "_test_rating": 0},
        {"slug": "new-series", "title": "New Series", "kind": "Сериал", "year": 2024,
         "published_at": "2026-10-02T13:00:00Z", "_test_rating": 0},
        {"slug": "rated-film", "title": "Rated Film", "kind": "Фильм", "year": 2023,
         "published_at": "2026-09-10T00:00:00Z", "_test_rating": 9.8},
    ]
    for s in specials:
        items.append({
            "slug": s["slug"], "title": s["title"], "kind": s["kind"],
            "year": s["year"],
            "poster": f"https://poster.example/{s['slug']}.webp",
            "url": f"/title/{s['slug']}/",
            "published_at": s["published_at"],
            "published_at_estimated": False,
            "_test_rating": s.get("_test_rating"),
        })
    return items


def _поднять(tmp_path):
    корень = tmp_path / "zona-01"
    корень.mkdir(parents=True, exist_ok=True)
    items = _база_items()
    cat = _каталог(items)
    details = _подробности([dict(it) for it in items])
    (корень / "zona-01-catalog.json").write_text(
        json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    (корень / "zona-01-details.json").write_text(
        json.dumps(details, ensure_ascii=False), encoding="utf-8")
    (корень / "player-zona-01.json").write_text(
        json.dumps({"publisher_id": "10238", "source_mode": "provider-id"}),
        encoding="utf-8")
    pw_spec = importlib.util.spec_from_file_location(
        f"pw_pass7_{int(time.time() * 1000)}",
        Path(__file__).resolve().parents[2] / "automation" / "host" / "popular_weekly.py")
    pw = importlib.util.module_from_spec(pw_spec)
    assert pw_spec.loader is not None
    pw_spec.loader.exec_module(pw)
    snap = pw.build_snapshot(
        items, details["details"], clock="2026-09-20T12:00:00Z", limit=12)
    pw.publish_snapshot(snap, корень / "zona-01-popular-weekly.json")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "zona",
        "design_version": "1.2.0", "source_commit": "0" * 40,
        "build_id": "PASS7", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_SITE_NAME"] = "Zona Cinema"
    имя = f"zona_pass7_{int(time.time() * 1000)}"
    spec = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
    модуль = importlib.util.module_from_spec(spec)
    sys.modules[имя] = модуль
    assert spec.loader is not None
    spec.loader.exec_module(модуль)
    модуль.Обработчик.данные = модуль.Данные(str(корень / "zona-01-catalog.json"))
    модуль.Обработчик.подробности = модуль.Подробности(
        str(корень / "zona-01-details.json"))
    модуль.Обработчик.индекс = модуль.построить_индекс(
        модуль.Обработчик.данные, модуль.Обработчик.подробности)
    модуль.Снимок.сбросить()
    модуль._тест_корень = корень
    модуль._тест_env = старое
    return модуль


def запросить(модуль, путь: str):
    from tests.lords.test_nova_frontend_families import запросить as _з
    return _з(модуль, путь)


@pytest.fixture()
def зона(tmp_path):
    м = _поднять(tmp_path)
    yield м
    os.environ.clear()
    os.environ.update(м._тест_env)


def test_recently_added_movies_shelf_prefers_catalog_published_at(зона):
    о = запросить(зона, "/")
    assert о.статус == 200
    assert "Добавленные недавно фильмы" in о.тело
    assert 'id="rl-new-films"' in о.тело
    sec = о.тело.split('id="rl-new-films"', 1)[1].split("</section>", 1)[0]
    assert "/title/new-film/" in sec
    if "/title/old-film/" in sec:
        assert sec.find("/title/new-film/") < sec.find("/title/old-film/")


def test_premiere_and_published_at_not_mixed_on_new_route(зона):
    набор, _ = зона.отбор(зона.Обработчик.данные, зона.Обработчик.индекс, {}, "/new")
    slugs = [з["slug"] for з in набор]
    assert slugs.index("new-film") < slugs.index("old-film")
    assert slugs.index("new-film") < slugs.index("backfill")


def test_new_series_shelf_uses_catalog_published_not_year(зона):
    о = запросить(зона, "/")
    assert "Недавно добавленные сериалы" in о.тело
    assert 'id="rl-new-eps"' in о.тело
    body = о.тело.split('id="rl-new-eps"', 1)[1].split("</section>", 1)[0]
    assert "/title/new-series/" in body
    if "/title/old-series/" in body:
        assert body.find("/title/new-series/") < body.find("/title/old-series/")


def test_metadata_edit_does_not_invent_episode_event():
    имя = "cc_pass7_contract"
    spec = importlib.util.spec_from_file_location(имя, КОНТРАКТ)
    cc = importlib.util.module_from_spec(spec)
    sys.modules[имя] = cc
    assert spec.loader is not None
    spec.loader.exec_module(cc)
    спец = cc.спецификация("zona", "new_episodes")
    assert спец is not None
    assert спец.title == "Недавно добавленные сериалы"
    assert спец.freshness_rule == "published_at"
    assert "дат" in спец.description.lower() or "эпизод" in спец.description.lower()


def test_future_release_not_confused_with_recently_added(зона):
    набор, _ = зона.отбор(
        зона.Обработчик.данные, зона.Обработчик.индекс,
        {"sort": ["recently_added"], "kind": ["Фильм"]}, "/movies")
    assert набор[0]["slug"] == "new-film"
    assert набор[0]["slug"] != "future-film"


def test_backfill_old_film_classified_by_published_at(зона):
    набор, _ = зона.отбор(
        зона.Обработчик.данные, зона.Обработчик.индекс,
        {"sort": ["recently_added"]}, "/catalog")
    slugs = [з["slug"] for з in набор]
    assert slugs.index("backfill") < slugs.index("old-film")
    нов, _ = зона.отбор(зона.Обработчик.данные, зона.Обработчик.индекс, {}, "/new")
    нов_slugs = [з["slug"] for з in нов]
    assert нов_slugs.index("new-film") < нов_slugs.index("backfill")


def test_weekly_snapshot_includes_high_rating_at_build(зона):
    о = запросить(зона, "/")
    assert "Высокий рейтинг среди недавних фильмов" in о.тело
    sec = о.тело.split("Высокий рейтинг среди недавних фильмов", 1)[1].split("<section", 1)[0]
    assert "/title/rated-film/" in sec


def test_unchanged_input_stable_shelf_digest(зона):
    о1 = запросить(зона, "/")
    о2 = запросить(зона, "/")
    assert о1.тело == о2.тело


def test_cache_headers_include_catalog_revision(зона):
    # Test helper stubs _отдать; call the real method once.
    class H(зона.Обработчик):
        def __init__(self):
            self.path = "/"
            self.command = "GET"
            self.headers = {"Host": "test.example"}
            self._hdrs = {}

        def send_response(self, код):
            self._код = код

        def send_header(self, имя, значение):
            self._hdrs[имя] = значение

        def end_headers(self):
            pass

        def wfile_write(self, data):
            pass

    h = H()
    h.wfile = type("W", (), {"write": lambda self, b: None})()
    зона.Обработчик._отдать(h, b"ok")
    assert h._hdrs.get("X-Catalog-Revision") == "pass7-rev-a"
    assert h._hdrs.get("Cache-Control") == "no-store"
    assert "pass7-rev-a" in (h._hdrs.get("ETag") or "")


def test_snapshot_reload_picks_up_new_catalog_without_restart(зона):
    о1 = запросить(зона, "/")
    assert "/title/brand-new/" not in о1.тело
    корень = зона._тест_корень
    cat = json.loads((корень / "zona-01-catalog.json").read_text(encoding="utf-8"))
    cat["items"].insert(0, {
        "slug": "brand-new", "title": "Brand New", "kind": "Фильм", "year": 2026,
        "poster": "https://poster.example/brand.webp", "url": "/title/brand-new/",
        "published_at": "2026-09-20T12:00:00Z", "published_at_estimated": False,
    })
    cat["count"] = len(cat["items"])
    cat["revision"] = "pass7-rev-b"
    cat["builtAt"] = "2026-09-20T12:00:00Z"
    det = json.loads((корень / "zona-01-details.json").read_text(encoding="utf-8"))
    det["details"]["brand-new"] = {
        "id": "id-brand-new", "playable": True,
        "imdb_rating": 8.0, "kinopoisk_rating": 8.0,
        "genres": ["драма"], "genre_codes": ["drama"],
        "countries": ["США"],
        "sources": [{"provider": "kp", "source_id": "9",
                     "availability_status": "available"}],
        "external_ids": {"kp": "9"},
        "premiere_date": "2026-09-20",
    }
    det["details_total"] = len(det["details"])
    det["catalog_revision"] = "pass7-rev-b"
    tmp_c = корень / "zona-01-catalog.json.new"
    tmp_d = корень / "zona-01-details.json.new"
    tmp_c.write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    tmp_d.write_text(json.dumps(det, ensure_ascii=False), encoding="utf-8")
    tmp_c.replace(корень / "zona-01-catalog.json")
    tmp_d.replace(корень / "zona-01-details.json")
    time.sleep(0.05)
    os.utime(корень / "zona-01-catalog.json", None)
    os.utime(корень / "zona-01-details.json", None)
    о2 = запросить(зона, "/")
    assert "/title/brand-new/" in о2.тело
    assert зона.Обработчик.данные.revision == "pass7-rev-b"


def test_empty_update_keeps_last_good(зона):
    before = запросить(зона, "/").тело
    корень = зона._тест_корень
    bad = корень / "zona-01-catalog.json.new"
    bad.write_text(json.dumps({
        "version": 2, "count": 0, "items": [], "revision": "empty",
        "builtAt": "2026-09-20T13:00:00Z", "site": "zona-01",
        "schema": "nova-catalog/2.0.0",
    }), encoding="utf-8")
    bad.replace(корень / "zona-01-catalog.json")
    time.sleep(0.05)
    os.utime(корень / "zona-01-catalog.json", None)
    after = запросить(зона, "/").тело
    assert after == before
    assert len(зона.Обработчик.данные.items) > 0


def test_idempotent_republish_same_revision(зона):
    о1 = запросить(зона, "/")
    корень = зона._тест_корень
    os.utime(корень / "zona-01-catalog.json", None)
    о2 = запросить(зона, "/")
    assert "Добавленные недавно фильмы" in о2.тело
    assert о1.тело.count("data-shelf=") == о2.тело.count("data-shelf=")


def test_no_duplicate_ids_inside_home_shelves(зона):
    о = запросить(зона, "/")
    for m in re.finditer(r'data-shelf="([^"]+)"[\s\S]*?</section>', о.тело):
        slugs = re.findall(r'href="(/title/[^"]+/)"', m.group(0))
        assert len(slugs) == len(set(slugs)), m.group(1)


def test_related_excludes_current_title(зона):
    о = запросить(зона, "/title/new-film/")
    assert о.статус == 200
    if "Похожее" in о.тело:
        sec = о.тело.split("Похожее", 1)[1].split("</section>", 1)[0]
        assert "/title/new-film/" not in sec


def test_noindex_preserved(зона):
    class H(зона.Обработчик):
        def __init__(self):
            self.path = "/"
            self.command = "GET"
            self.headers = {"Host": "test.example"}
            self._hdrs = {}

        def send_response(self, код):
            pass

        def send_header(self, имя, значение):
            self._hdrs[имя] = значение

        def end_headers(self):
            pass

    h = H()
    h.wfile = type("W", (), {"write": lambda self, b: None})()
    зона.Обработчик._отдать(h, b"ok")
    assert "noindex" in h._hdrs.get("X-Robots-Tag", "")


def test_popular_label_is_not_invented_popularity(зона):
    о = запросить(зона, "/")
    assert "Высокий рейтинг среди недавних" in о.тело
    assert "Популярные новинки фильмов" not in о.тело
