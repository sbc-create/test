"""BLOCK_04: home top shelf order and empty ad collapse."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def test_hero_before_h1_when_approved(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    import json
    slugs = [i["slug"] for i in catalog["items"]]
    path = tmp_path / "weekly.json"
    path.write_text(json.dumps({
        "schema_version": 1, "site_id": "animedia.space", "week_id": "2026-W38",
        "timezone": "Europe/Moscow",
        "window_start": "2026-09-14T00:00:00+03:00",
        "window_end": "2026-09-21T00:00:00+03:00",
        "valid_from": "2026-09-14T00:00:00+03:00",
        "valid_to": "2026-09-21T00:00:00+03:00",
        "algorithm_version": "weekly-v1",
        "algorithm_parameters_digest": "x",
        "input_revision": "vis-1", "cutoff_at": "2026-09-14T00:00:00Z",
        "ordered_title_ids": slugs, "scores": {},
        "eligibility_policy": "p", "playable_policy": "p",
        "tie_breaker": "slug", "snapshot_revision": "1",
        "generated_at": "2026-09-14T01:00:00Z", "digest": "d1",
    }), encoding="utf-8")
    monkeypatch.setenv("ANIMEDIA_WEEKLY_POPULAR_SNAPSHOT", str(path))
    mod.АНИМЕДИА_WEEKLY_POPULAR_PATH = str(path)
    html = _вид(mod, catalog, details).главная()
    ahero = html.find('data-weekly-popular="1"')
    h1 = html.find('class="zh zh--home"')
    assert ahero > 0 and h1 > ahero


def test_empty_ad_slots_collapsed_css(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert ".zad-home" in css
    assert "height:0" in css


def test_no_invented_telegram_url(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).главная()
    assert "t.me/" not in html
    assert "telegram.me/" not in html
    assert 'href="#"' not in html
