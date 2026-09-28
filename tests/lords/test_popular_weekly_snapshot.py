"""Weekly popular shelf snapshot contract (LORDS-MULTISITE-AUDIT-01 Block 04).

POPULAR_REFRESH_MODE=WEEKLY_SNAPSHOT:
* identical digest across sequential calls in the same ISO week
* identical digest after process-local cache clear when disk sidecar exists
* rebuild only on week rollover or explicit force_rebuild
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


@pytest.fixture
def fe(tmp_path, monkeypatch):
    snap = tmp_path / "popular-weekly.json"
    monkeypatch.setenv("LORDS_POPULAR_SNAPSHOT", str(snap))
    monkeypatch.delenv("LORDS_POPULAR_REBUILD", raising=False)

    # Minimal import without full manifest: load only the helper section by
    # executing the module with a throwaway manifest + empty catalog.
    корень = tmp_path / "site"
    корень.mkdir()
    cat = {
        "version": 2, "count": 0, "items": [], "fields_absent": [],
        "site": "pop-test", "schema": "nova-catalog/2.0.0",
        "revision": "t", "builtAt": "2026-09-13T00:00:00Z",
    }
    (корень / "pop-test-catalog.json").write_text(
        json.dumps(cat), encoding="utf-8")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords",
        "design_version": "1.1.0", "source_commit": "0" * 40,
        "build_id": "TEST-POP", "artifact_sha256": "0" * 64,
        "profile": "lords-new", "built_at": "2026-09-13T00:00:00Z",
    }), encoding="utf-8")
    monkeypatch.setenv("LORDS_TEMPLATE_MANIFEST", str(манифест))
    monkeypatch.setenv("LORDS_CATALOG", str(корень / "pop-test-catalog.json"))
    monkeypatch.setenv("LORDS_SITE_NAME", "Pop Test")
    monkeypatch.delenv("LORDS_DETAILS", raising=False)

    имя = "nova_popular_weekly_contract"
    спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
    мод = importlib.util.module_from_spec(спец)
    sys.modules[имя] = мод
    спец.loader.exec_module(мод)
    мод.сброс_популярного_кэша()
    return мод, snap


def _записи():
    return [
        {"slug": "a", "title": "A", "kind": "Фильм", "year": 2024,
         "published_at": "2026-09-10T00:00:00Z", "_rating": 9.0},
        {"slug": "b", "title": "B", "kind": "Фильм", "year": 2023,
         "published_at": "2026-09-09T00:00:00Z", "_rating": 8.5},
        {"slug": "c", "title": "C", "kind": "Сериал", "year": 2022,
         "published_at": "2026-09-08T00:00:00Z", "_rating": 8.0},
        {"slug": "d", "title": "D", "kind": "Фильм", "year": 2021,
         "published_at": "2026-09-07T00:00:00Z", "_rating": 7.0},
    ]


def test_same_week_two_calls_same_digest(fe):
    мод, snap = fe
    t = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    a1, w1, d1 = мод.популярные_недельный(
        _записи(), lambda з: float(з["_rating"]), сколько=3, сейчас=t)
    a2, w2, d2 = мод.популярные_недельный(
        _записи(), lambda з: float(з["_rating"]), сколько=3, сейчас=t)
    assert w1 == w2 == "2026-W38"
    assert d1 == d2
    assert [з["slug"] for з in a1] == [з["slug"] for з in a2] == ["a", "b", "c"]
    assert snap.is_file()


def test_restart_simulation_reads_disk(fe):
    мод, snap = fe
    t = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    _, _, d1 = мод.популярные_недельный(
        _записи(), lambda з: float(з["_rating"]), сколько=3, сейчас=t)
    мод.сброс_популярного_кэша()
    # Mid-week catalog rating flip must NOT change order while disk week holds.
    flipped = _записи()
    flipped[0]["_rating"] = 1.0
    flipped[3]["_rating"] = 9.9
    a2, w2, d2 = мод.популярные_недельный(
        flipped, lambda з: float(з["_rating"]), сколько=3, сейчас=t)
    assert w2 == "2026-W38"
    assert d2 == d1
    assert [з["slug"] for з in a2] == ["a", "b", "c"]


def test_new_week_rebuilds(fe):
    мод, snap = fe
    t1 = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    _, w1, d1 = мод.популярные_недельный(
        _записи(), lambda з: float(з["_rating"]), сколько=3, сейчас=t1)
    t2 = t1 + timedelta(days=7)
    # Force different scores so a rebuild is observable.
    flipped = _записи()
    flipped[0]["_rating"] = 1.0
    flipped[3]["_rating"] = 9.9
    a2, w2, d2 = мод.популярные_недельный(
        flipped, lambda з: float(з["_rating"]), сколько=3, сейчас=t2)
    assert w1 != w2
    assert d1 != d2
    assert [з["slug"] for з in a2][0] == "d"


def test_force_rebuild_same_week(fe):
    мод, snap = fe
    t = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    _, _, d1 = мод.популярные_недельный(
        _записи(), lambda з: float(з["_rating"]), сколько=3, сейчас=t)
    flipped = _записи()
    flipped[0]["_rating"] = 1.0
    flipped[3]["_rating"] = 9.9
    a2, _, d2 = мод.популярные_недельный(
        flipped, lambda з: float(з["_rating"]), сколько=3, сейчас=t,
        force_rebuild=True)
    assert d1 != d2
    assert [з["slug"] for з in a2][0] == "d"


def test_source_declares_weekly_mode():
    src = ИСХОДНИК.read_text(encoding="utf-8")
    assert "WEEKLY_SNAPSHOT" in src
    assert "def популярные_недельный" in src
    assert 'data-popular-mode="WEEKLY_SNAPSHOT"' in src
