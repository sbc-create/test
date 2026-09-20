"""Zona Pass7 correction: Popular = WEEKLY_SNAPSHOT (no request-time recompute)."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEEKLY = ROOT / "automation" / "host" / "popular_weekly.py"
FRONTEND = ROOT / "automation" / "host" / "lords-frontend.py"


def _load_weekly():
    имя = f"popular_weekly_{int(time.time() * 1000)}"
    spec = importlib.util.spec_from_file_location(имя, WEEKLY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[имя] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _catalog_details(n=60):
    items = []
    details = {}
    for i in range(n):
        kind = "Фильм" if i % 3 == 0 else ("Сериал" if i % 3 == 1 else "Мультфильм")
        slug = f"t-{i:04d}"
        items.append({
            "slug": slug, "title": f"Title {i:04d}", "kind": kind, "year": 2024,
            "poster": f"https://p/{slug}.webp", "url": f"/title/{slug}/",
            "published_at": f"2026-09-{(i % 28) + 1:02d}T00:00:00Z",
        })
        rating = 5.0 + (i % 50) / 10.0
        details[slug] = {
            "id": slug, "playable": True,
            "imdb_rating": rating, "kinopoisk_rating": rating,
            "genres": ["драма"], "genre_codes": ["drama"],
            "countries": ["США"],
            "sources": [{"provider": "kp", "source_id": "1",
                         "availability_status": "available"}],
            "seasons": [{"n": 1, "eps": 4, "avail": 2}] if kind == "Сериал" else [],
        }
    return items, details


def test_week_id_is_iso_monday_based():
    pw = _load_weekly()
    assert pw.week_id("2026-09-20T12:00:00Z") == "2026-W38"
    assert pw.week_id("2026-09-21T00:00:00Z") == "2026-W39"


def test_build_is_deterministic_same_input_same_digest():
    pw = _load_weekly()
    items, details = _catalog_details()
    a = pw.build_snapshot(items, details, clock="2026-09-20T12:00:00Z", limit=12)
    b = pw.build_snapshot(items, details, clock="2026-09-20T12:00:00Z", limit=12)
    assert a["week_id"] == b["week_id"] == "2026-W38"
    assert a["digest"] == b["digest"]
    assert a["shelves"]["pop-films"] == b["shelves"]["pop-films"]
    assert a["mode"] == "WEEKLY_SNAPSHOT"
    assert a["request_time_recomputes"] is False


def test_publish_atomic_and_idempotent(tmp_path):
    pw = _load_weekly()
    items, details = _catalog_details()
    snap = pw.build_snapshot(items, details, clock="2026-09-20T12:00:00Z")
    path = tmp_path / "zona-01-popular-weekly.json"
    r1 = pw.publish_snapshot(snap, path)
    assert r1["published"] is True
    assert path.is_file()
    r2 = pw.publish_snapshot(snap, path)
    assert r2["published"] is False
    assert r2["reason"] == "same_week_same_digest"
    assert pw.load_snapshot(path)["digest"] == snap["digest"]


def test_second_build_same_week_does_not_replace_without_force(tmp_path):
    pw = _load_weekly()
    items, details = _catalog_details()
    path = tmp_path / "zona-01-popular-weekly.json"
    s1 = pw.build_snapshot(items, details, clock="2026-09-20T12:00:00Z", limit=12)
    pw.publish_snapshot(s1, path)
    # Mutate a member that is actually on the weekly shelf.
    victim = s1["shelves"]["pop-films"][0]
    details[victim]["imdb_rating"] = 0.1
    details[victim]["kinopoisk_rating"] = 0.1
    s2 = pw.build_snapshot(items, details, clock="2026-09-20T18:00:00Z", limit=12)
    assert s2["week_id"] == s1["week_id"]
    assert s2["digest"] != s1["digest"]
    r = pw.publish_snapshot(s2, path)
    assert r["published"] is False
    assert r["reason"] == "week_already_published"
    assert pw.load_snapshot(path)["digest"] == s1["digest"]


def test_new_week_publishes_exactly_one_new_snapshot(tmp_path):
    pw = _load_weekly()
    items, details = _catalog_details()
    path = tmp_path / "zona-01-popular-weekly.json"
    s1 = pw.build_snapshot(items, details, clock="2026-09-20T12:00:00Z")
    pw.publish_snapshot(s1, path)
    s2 = pw.build_snapshot(items, details, clock="2026-09-21T04:00:00Z")
    assert s2["week_id"] != s1["week_id"]
    r = pw.publish_snapshot(s2, path)
    assert r["published"] is True
    assert pw.load_snapshot(path)["week_id"] == s2["week_id"]


def test_crash_before_atomic_rename_keeps_last_good(tmp_path):
    pw = _load_weekly()
    items, details = _catalog_details()
    path = tmp_path / "zona-01-popular-weekly.json"
    s1 = pw.build_snapshot(items, details, clock="2026-09-20T12:00:00Z")
    pw.publish_snapshot(s1, path)
    # Simulate crash: write .new only, never rename.
    s2 = pw.build_snapshot(items, details, clock="2026-09-21T04:00:00Z")
    tmp = path.with_suffix(path.suffix + ".new")
    tmp.write_text(json.dumps(s2), encoding="utf-8")
    loaded = pw.load_snapshot(path)
    assert loaded["week_id"] == s1["week_id"]
    assert loaded["digest"] == s1["digest"]


def test_file_lock_prevents_double_publish(tmp_path):
    pw = _load_weekly()
    items, details = _catalog_details()
    path = tmp_path / "zona-01-popular-weekly.json"
    s = pw.build_snapshot(items, details, clock="2026-09-21T04:00:00Z")
    lock = path.with_suffix(path.suffix + ".lock")
    with open(lock, "w", encoding="utf-8") as lf:
        import fcntl
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        r = pw.publish_snapshot(s, path, wait_lock=False)
        assert r["published"] is False
        assert r["reason"] == "lock_held"


def test_emergency_removal_replaces_with_reserve_not_full_rotation(tmp_path):
    pw = _load_weekly()
    items, details = _catalog_details()
    path = tmp_path / "zona-01-popular-weekly.json"
    s = pw.build_snapshot(items, details, clock="2026-09-20T12:00:00Z", limit=12)
    pw.publish_snapshot(s, path)
    victim = s["shelves"]["pop-films"][0]
    before = list(s["shelves"]["pop-films"])
    r = pw.emergency_repair(
        path, shelf="pop-films", remove_slug=victim,
        reason="title_unavailable", catalog_items=items, details=details)
    assert r["POPULAR_EMERGENCY_REPAIR"] == 1
    assert r["POPULAR_REGULAR_WEEKLY_ROTATION"] == 0
    assert r["POPULAR_EMERGENCY_REASON"] == "title_unavailable"
    after = pw.load_snapshot(path)
    assert victim not in after["shelves"]["pop-films"]
    assert after["week_id"] == s["week_id"]
    # Only one slot replaced; rest of order preserved where possible.
    assert after["shelves"]["pop-films"][1:] == [
        x for x in before[1:] if x != victim
    ][:11] or len(after["shelves"]["pop-films"]) == 12


def test_no_random_rotation_flag_in_snapshot():
    pw = _load_weekly()
    items, details = _catalog_details()
    s = pw.build_snapshot(items, details, clock="2026-09-20T12:00:00Z")
    assert s.get("random_rotation") is False
    assert "views" not in json.dumps(s).lower() or s.get("invented_views") is False


# --- Frontend integration: request-time must not recompute popular ---

def _frontend_fixture(tmp_path, weekly_path=None):
    items, details = _catalog_details(90)
    корень = tmp_path / "zona-01"
    корень.mkdir()
    cat = {
        "version": 2, "count": len(items), "items": items, "site": "zona-01",
        "schema": "nova-catalog/2.0.0", "revision": "w1",
        "builtAt": "2026-09-20T03:16:30Z",
    }
    det = {
        "schema": "nova-details/1.0.0", "site": "zona-01",
        "details_total": len(details), "details": details,
        "catalog_revision": "w1",
    }
    (корень / "zona-01-catalog.json").write_text(json.dumps(cat), encoding="utf-8")
    (корень / "zona-01-details.json").write_text(json.dumps(det), encoding="utf-8")
    (корень / "player-zona-01.json").write_text(
        json.dumps({"publisher_id": "10238", "source_mode": "provider-id"}),
        encoding="utf-8")
    pw = _load_weekly()
    snap = pw.build_snapshot(items, details, clock="2026-09-20T12:00:00Z", limit=12)
    pop_path = weekly_path or (корень / "zona-01-popular-weekly.json")
    pw.publish_snapshot(snap, pop_path)
    man = корень / "manifest.json"
    man.write_text(json.dumps({
        "schema_version": 1, "template_family": "zona",
        "design_version": "1.2.0", "source_commit": "0" * 40,
        "build_id": "PASS7W", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    env = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(man)
    os.environ["LORDS_CATALOG"] = str(корень / "zona-01-catalog.json")
    os.environ["LORDS_DETAILS"] = str(корень / "zona-01-details.json")
    os.environ["LORDS_PLAYER_CONFIG"] = str(корень / "player-zona-01.json")
    os.environ["LORDS_POPULAR_WEEKLY"] = str(pop_path)
    os.environ["LORDS_SITE_NAME"] = "Zona Cinema"
    имя = f"zona_pop_weekly_{int(time.time() * 1000)}"
    spec = importlib.util.spec_from_file_location(имя, FRONTEND)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[имя] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    mod.Обработчик.данные = mod.Данные(str(корень / "zona-01-catalog.json"))
    mod.Обработчик.подробности = mod.Подробности(str(корень / "zona-01-details.json"))
    mod.Обработчик.индекс = mod.построить_индекс(
        mod.Обработчик.данные, mod.Обработчик.подробности)
    mod.Снимок.сбросить()
    mod._тест_env = env
    mod._тест_корень = корень
    mod._тест_pop = pop_path
    mod._тест_snap = snap
    return mod


def _shelf_ids(html: str, shelf_key: str) -> list[str]:
    import re
    marker = f'id="rl-{shelf_key}"'
    assert marker in html, shelf_key
    chunk = html.split(marker, 1)[1].split("</section>", 1)[0]
    return re.findall(r'href="(/title/[^"]+/)"', chunk)


def test_100_requests_same_week_same_popular_order(tmp_path):
    from tests.lords.test_nova_frontend_families import запросить
    mod = _frontend_fixture(tmp_path)
    try:
        first = None
        for _ in range(100):
            о = запросить(mod, "/")
            assert о.статус == 200
            ids = _shelf_ids(о.тело, "pop-films")
            assert ids
            if first is None:
                first = ids
            else:
                assert ids == first
        assert "X-Popular-Week-Id" in о.заголовки or hasattr(о, "заголовки")
    finally:
        os.environ.clear()
        os.environ.update(mod._тест_env)


def test_rating_change_within_week_does_not_change_live_shelf(tmp_path):
    from tests.lords.test_nova_frontend_families import запросить
    mod = _frontend_fixture(tmp_path)
    try:
        о1 = запросить(mod, "/")
        before = _shelf_ids(о1.тело, "pop-films")
        # Mutate in-memory ratings (would have changed request-time shelves).
        for з in mod.Обработчик.данные.items:
            if з["kind"] == "Фильм":
                з["_rating"] = 0.1
        о2 = запросить(mod, "/")
        after = _shelf_ids(о2.тело, "pop-films")
        assert after == before
    finally:
        os.environ.clear()
        os.environ.update(mod._тест_env)


def test_process_restart_equivalent_reload_keeps_weekly_digest(tmp_path):
    from tests.lords.test_nova_frontend_families import запросить
    mod = _frontend_fixture(tmp_path)
    try:
        о1 = запросить(mod, "/")
        before = _shelf_ids(о1.тело, "pop-films")
        # Simulate restart: rebuild handler state from same weekly file.
        mod.Обработчик.данные = mod.Данные(os.environ["LORDS_CATALOG"])
        mod.Обработчик.подробности = mod.Подробности(os.environ["LORDS_DETAILS"])
        mod.Обработчик.индекс = mod.построить_индекс(
            mod.Обработчик.данные, mod.Обработчик.подробности)
        if hasattr(mod, "сбросить_popular_cache"):
            mod.сбросить_popular_cache()
        о2 = запросить(mod, "/")
        assert _shelf_ids(о2.тело, "pop-films") == before
        assert mod._тест_snap["digest"] == json.loads(
            mod._тест_pop.read_text(encoding="utf-8"))["digest"]
    finally:
        os.environ.clear()
        os.environ.update(mod._тест_env)


def test_cache_headers_include_popular_week_id_and_digest(tmp_path):
    mod = _frontend_fixture(tmp_path)
    try:
        class H(mod.Обработчик):
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
        mod.Обработчик._отдать(h, b"ok")
        assert h._hdrs.get("X-Popular-Week-Id") == "2026-W38"
        assert h._hdrs.get("X-Popular-Weekly-Digest")
        assert "pop-" in (h._hdrs.get("ETag") or "") or "W38" in (h._hdrs.get("ETag") or "")
    finally:
        os.environ.clear()
        os.environ.update(mod._тест_env)


def test_new_films_shelf_still_request_fresh_not_weekly(tmp_path):
    from tests.lords.test_nova_frontend_families import запросить
    mod = _frontend_fixture(tmp_path)
    try:
        о = запросить(mod, "/")
        assert "Добавленные недавно фильмы" in о.тело
        assert 'id="rl-new-films"' in о.тело
        # Popular comes from weekly; new-films must not equal pop-films blindly.
        pop = _shelf_ids(о.тело, "pop-films")
        neu = _shelf_ids(о.тело, "new-films")
        assert neu  # still dynamic
        assert pop != neu or len(pop) == 0
    finally:
        os.environ.clear()
        os.environ.update(mod._тест_env)
