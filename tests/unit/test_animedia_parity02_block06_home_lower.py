"""BLOCK_06: home lower sections + weekly popular snapshot."""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def test_empty_section_collapses(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    assert вид.секция("empty", "Пусто", "/x/", [], "нет") == ""


def test_popular_weekly_constants(fe):
    mod, _, _ = fe
    assert mod.АНИМЕДИА_POPULAR_WINDOW == "weekly"
    assert mod.АНИМЕДИА_POPULAR_REFRESH_ON_EVERY_REQUEST == 0


def test_popular_order_stable_within_week(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    # ISO week 38 of 2026: Mon 2026-09-14 .. Sun 2026-09-20
    now = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    a = mod.аниме_popular_snapshot(
        вид.д.items, вид.деталь, revision="r1", limit=12, now=now)
    b = mod.аниме_popular_snapshot(
        вид.д.items, вид.деталь, revision="r1", limit=12, now=now)
    assert a["slugs"] == b["slugs"]
    assert a["snapshot_version"] == b["snapshot_version"]
    assert a["week_key"] == "2026-W38"
    assert a["refresh_on_every_request"] == 0
    # Same week, later clock — order must not reshuffle.
    later = datetime(2026, 9, 19, 18, 0, tzinfo=timezone.utc)
    c = mod.аниме_popular_snapshot(
        вид.д.items, вид.деталь, revision="r1", limit=12, now=later)
    assert c["slugs"] == a["slugs"]
    assert c["snapshot_version"] == a["snapshot_version"]
    assert c["week_key"] == a["week_key"]


def test_home_exposes_popular_snapshot_attrs(fe):
    mod, catalog, details = fe
    # Ensure ratings exist so popular shelf can form.
    for slug, det in list(details["details"].items())[:8]:
        det["kinopoisk_rating"] = 7.5 + (hash(slug) % 20) / 10.0
    html = _вид(mod, catalog, details, host="animedia.space").главная()
    assert "Популярное за неделю" in html or "data-popular-window" in html
    if "data-popular-window" in html:
        assert 'data-popular-window="weekly"' in html
        assert "data-popular-snapshot=" in html
        assert "data-popular-week=" in html


def test_no_duplicate_shelf_titles_same_slugs(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details, host="animedia.space").главная()
    # Collect card hrefs per section roughly
    sections = re.findall(
        r'<section class="zsec"[^>]*>.*?</section>', html, flags=re.S)
    seen_sets = []
    for sec in sections:
        slugs = re.findall(r'href="/title/([^"/]+)/"', sec)
        if len(slugs) < 2:
            continue
        key = tuple(slugs)
        assert key not in seen_sets, "identical duplicate shelves"
        seen_sets.append(key)


def test_domains_document_inventory_diff(fe):
    mod, _, _ = fe
    assert mod.АНИМЕДИА_ДОМЕНЫ["animedia.space"]["home_shelves"] != \
        mod.АНИМЕДИА_ДОМЕНЫ["animedia.icu"]["home_shelves"]


def test_no_community_modules_invented(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).главная().lower()
    for bad in ("discord", "форум", "комментари", "лайки пользователей"):
        assert bad not in html
