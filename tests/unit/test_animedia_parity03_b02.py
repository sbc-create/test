"""B02 weekly popular shelf + telegram/ad collapse — BLOCKWISE-PARITY-03."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402

EV = ROOT / "artifacts/evidence/animedia-blockwise-parity-03-2026-09-20"
CONTRACT_SHA = (EV / "00-contract" / "CONTRACT_SHA256.txt").read_text(encoding="utf-8").strip()


def _approved_snapshot(slugs: list[str], *, site_id: str = "animedia.space") -> dict:
    return {
        "schema_version": 1,
        "site_id": site_id,
        "week_id": "2026-W38",
        "timezone": "Europe/Moscow",
        "window_start": "2026-09-14T00:00:00+03:00",
        "window_end": "2026-09-21T00:00:00+03:00",
        "valid_from": "2026-09-14T00:00:00+03:00",
        "valid_to": "2026-09-21T00:00:00+03:00",
        "algorithm_version": "weekly-v1",
        "algorithm_parameters_digest": "deadbeef",
        "input_revision": "vis-1",
        "cutoff_at": "2026-09-14T00:00:00Z",
        "ordered_title_ids": slugs,
        "scores": {s: 1.0 for s in slugs},
        "eligibility_policy": "playable_in_catalog",
        "playable_policy": "current_availability",
        "tie_breaker": "slug_asc",
        "snapshot_revision": "1",
        "generated_at": "2026-09-14T01:00:00Z",
        "digest": "abc123digest",
    }


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def test_contract_digest_unchanged() -> None:
    assert CONTRACT_SHA == "5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3"


def test_missing_approved_snapshot_hides_weekly_shelf(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    missing = tmp_path / "no-weekly.json"
    monkeypatch.setenv("ANIMEDIA_WEEKLY_POPULAR_SNAPSHOT", str(missing))
    mod.АНИМЕДИА_WEEKLY_POPULAR_PATH = str(missing)
    html = _вид(mod, catalog, details).главная()
    assert 'data-popular-gap="1"' in html
    assert 'data-weekly-popular="1"' not in html
    assert "class=\"ahero\"" not in html or "ahero--gap" in html


def test_approved_snapshot_renders_weekly_shelf(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    slugs = [i["slug"] for i in catalog["items"]]
    path = tmp_path / "weekly.json"
    path.write_text(json.dumps(_approved_snapshot(slugs)), encoding="utf-8")
    monkeypatch.setenv("ANIMEDIA_WEEKLY_POPULAR_SNAPSHOT", str(path))
    mod.АНИМЕДИА_WEEKLY_POPULAR_PATH = str(path)
    html = _вид(mod, catalog, details).главная()
    assert 'data-weekly-popular="1"' in html
    assert 'data-popular-gap="1"' not in html
    assert 'data-popular-snapshot="abc123digest"' in html
    assert 'data-popular-week="2026-W38"' in html
    ahero = html.find('data-weekly-popular="1"')
    h1 = html.find('class="zh zh--home"')
    assert ahero > 0 and h1 > ahero


def test_approved_order_stable_two_loads(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    slugs = [i["slug"] for i in catalog["items"]]
    path = tmp_path / "weekly.json"
    path.write_text(json.dumps(_approved_snapshot(slugs)), encoding="utf-8")
    monkeypatch.setenv("ANIMEDIA_WEEKLY_POPULAR_SNAPSHOT", str(path))
    mod.АНИМЕДИА_WEEKLY_POPULAR_PATH = str(path)
    a = mod.аниме_load_approved_weekly_popular(site_id="animedia.space", path=path)
    b = mod.аниме_load_approved_weekly_popular(site_id="animedia.space", path=path)
    assert a["slugs"] == b["slugs"] == slugs
    assert a["digest"] == b["digest"]


def test_less_than_four_valid_hides_shelf(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    path = tmp_path / "weekly.json"
    path.write_text(json.dumps(_approved_snapshot(["alpha-anime", "missing-x"])), encoding="utf-8")
    monkeypatch.setenv("ANIMEDIA_WEEKLY_POPULAR_SNAPSHOT", str(path))
    mod.АНИМЕДИА_WEEKLY_POPULAR_PATH = str(path)
    html = _вид(mod, catalog, details).главная()
    assert 'data-popular-gap="1"' in html
    assert 'data-weekly-popular="1"' not in html


def test_no_invented_telegram(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    monkeypatch.setenv("ANIMEDIA_OWNER_CONFIG", str(tmp_path / "owner.json"))
    mod.АНИМЕДИА_OWNER_CONFIG_PATH = str(tmp_path / "owner.json")
    html = _вид(mod, catalog, details).главная()
    assert "t.me/" not in html
    assert 'class="atg"' not in html


def test_telegram_promo_when_owner_url(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    owner = tmp_path / "owner.json"
    owner.write_text(json.dumps({"telegram_url": "https://t.me/animedia_example"}), encoding="utf-8")
    monkeypatch.setenv("ANIMEDIA_OWNER_CONFIG", str(owner))
    mod.АНИМЕДИА_OWNER_CONFIG_PATH = str(owner)
    html = _вид(mod, catalog, details).главная()
    assert 'class="atg"' in html
    assert "https://t.me/animedia_example" in html


def test_ad_slots_collapsed_css(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert ".zad-home" in css
    assert "height:0" in css
    assert "calc((100% - 144px)/10)" in css
    assert ".atg{" in css


def test_legacy_score_helper_not_display_approved(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    now = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    snap = mod.аниме_popular_snapshot(
        вид.д.items, вид.деталь, revision="r1", limit=12, now=now)
    assert snap.get("display_approved") is False
