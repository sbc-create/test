"""B06 home remaining modules — filters, top100, shelves, SEO order."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402

EV = ROOT / "artifacts/evidence/animedia-blockwise-parity-03-2026-09-20"
CONTRACT_SHA = (EV / "00-contract" / "CONTRACT_SHA256.txt").read_text(encoding="utf-8").strip()


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def test_contract_digest_unchanged() -> None:
    assert CONTRACT_SHA == "5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3"


def test_home_has_compact_filters(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    for env, attr in (
        ("ANIMEDIA_WEEKLY_POPULAR_SNAPSHOT", "АНИМЕДИА_WEEKLY_POPULAR_PATH"),
        ("ANIMEDIA_TOP100_SNAPSHOT", "АНИМЕДИА_TOP100_PATH"),
        ("ANIMEDIA_CATALOG_ADDED_LEDGER", "АНИМЕДИА_CATALOG_ADDED_PATH"),
    ):
        missing = tmp_path / f"miss-{attr}.json"
        monkeypatch.setenv(env, str(missing))
        setattr(mod, attr, str(missing))
    html = _вид(mod, catalog, details).главная()
    assert 'data-b06="filters"' in html
    assert "ahome-filt" in html
    assert "/catalog/" in html
    assert "max-height:56px" in mod.АНИМЕДИА_СТИЛЬ
    assert "afilt--closed" in mod.АНИМЕДИА_СТИЛЬ
    assert "max-height:112px" in mod.АНИМЕДИА_СТИЛЬ


def test_top100_gap_without_snapshot(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    missing = tmp_path / "no-top.json"
    monkeypatch.setenv("ANIMEDIA_TOP100_SNAPSHOT", str(missing))
    mod.АНИМЕДИА_TOP100_PATH = str(missing)
    html = _вид(mod, catalog, details).главная()
    assert 'data-b06-top100="gap"' in html
    assert 'data-top100-gap="1"' in html
    assert mod.TOP100_DATA_GAP == 1
    assert 'data-b06-top100="populated"' not in html
    assert 'data-card-variant="top100-shelf"' not in html


def test_top100_populated_from_snapshot(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    snap = {
        "schema_version": 1,
        "site_id": "animedia.space",
        "ordered_title_ids": ["alpha-anime", "beta-series", "delta-old", "gamma-movie"],
        "snapshot_revision": "t1",
        "digest": "topdigest1",
        "generated_at": "2026-09-20T00:00:00Z",
    }
    path = tmp_path / "top.json"
    path.write_text(json.dumps(snap), encoding="utf-8")
    monkeypatch.setenv("ANIMEDIA_TOP100_SNAPSHOT", str(path))
    mod.АНИМЕДИА_TOP100_PATH = str(path)
    html = _вид(mod, catalog, details).главная()
    assert 'data-b06-top100="populated"' in html
    assert "Топ‑100" in html
    assert 'data-top100-digest="topdigest1"' in html
    assert 'data-card-variant="top100-shelf"' in html


def test_catalog_shelves_capped_at_two(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    missing = tmp_path / "no-top.json"
    monkeypatch.setenv("ANIMEDIA_TOP100_SNAPSHOT", str(missing))
    mod.АНИМЕДИА_TOP100_PATH = str(missing)
    monkeypatch.setenv("ANIMEDIA_WEEKLY_POPULAR_SNAPSHOT", str(missing))
    mod.АНИМЕДИА_WEEKLY_POPULAR_PATH = str(missing)
    html = _вид(mod, catalog, details, host="animedia.space").главная()
    # Count lower catalog zsec blocks that are not B03/B05/top100/collections/seo.
    # Cap constant must be 2.
    assert mod.АНИМЕДИА_HOME_MAX_CATALOG_SHELVES == 2
    # SEO must follow functional modules.
    seo_pos = html.find('class="zseo"')
    filt_pos = html.find('data-b06="filters"')
    assert filt_pos != -1 and seo_pos != -1 and filt_pos < seo_pos
    # Editorial/comments not invented.
    assert 'data-editorial="0"' in html
    assert 'data-comments="0"' in html
    assert "Новости" not in html
    assert "Комментарии" not in html


def test_seo_after_filters_and_before_footer(fe):
    mod, catalog, details = fe
    html = _вид(mod, catalog, details).главная()
    assert html.find('data-b06="filters"') < html.find('class="zseo"')
    assert html.find('class="zseo"') < html.find('class="zft"')
