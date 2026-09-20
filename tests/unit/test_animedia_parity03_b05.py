"""B05 catalog_added ledger / home shelf / /new/ — BLOCKWISE-PARITY-03."""
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


def test_home_b05_zero_px_without_ledger(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    missing = tmp_path / "no-catalog-added.json"
    monkeypatch.setenv("ANIMEDIA_CATALOG_ADDED_LEDGER", str(missing))
    mod.АНИМЕДИА_CATALOG_ADDED_PATH = str(missing)
    html = _вид(mod, catalog, details).главная()
    assert 'data-b05="gap"' in html
    assert 'data-catalog-freshness-gap="1"' in html
    assert "zsec--b05-gap" in html
    assert mod.CATALOG_FRESHNESS_DATA_GAP == 1
    # Must not sell published_at shelf as catalog additions.
    assert "Новые аниме на сайте" not in html
    assert 'data-card-variant="catalog-added"' not in html


def test_new_page_honest_empty_without_ledger(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    missing = tmp_path / "no-catalog-added.json"
    monkeypatch.setenv("ANIMEDIA_CATALOG_ADDED_LEDGER", str(missing))
    mod.АНИМЕДИА_CATALOG_ADDED_PATH = str(missing)
    вид = _вид(mod, catalog, details)
    page = вид.список("/new", {})
    assert "Новое в каталоге" in page
    assert "ledger добавлений ещё не подключён" in page
    assert 'data-b05-page="gap"' in page
    assert 'data-card-variant="episode-row"' not in page
    assert 'class="aeps__row"' not in page
    # published_at must not invent catalog-added cards.
    assert 'data-event-kind="catalog_publish"' not in page


def test_published_at_helper_not_feeding_b05(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    missing = tmp_path / "no-catalog-added.json"
    monkeypatch.setenv("ANIMEDIA_CATALOG_ADDED_LEDGER", str(missing))
    mod.АНИМЕДИА_CATALOG_ADDED_PATH = str(missing)
    вид = _вид(mod, catalog, details)
    legacy = вид._эпизод_события()
    assert legacy
    assert all(e.get("event_kind") == "catalog_publish" for e in legacy)
    assert вид._catalog_added_events() == []
    home = вид.главная()
    assert 'data-b05="gap"' in home


def test_populated_catalog_added_ledger(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    ledger = {
        "events": [
            {
                "event_id": "ca1",
                "title_slug": "alpha-anime",
                "catalog_added_at": "2026-09-18T12:00:00Z",
                "provenance": "test-ledger",
            },
            {
                "event_id": "ca2",
                "title_slug": "beta-series",
                "catalog_added_at": "2026-09-17T08:00:00Z",
            },
            {
                "event_id": "ca3",
                "title_slug": "delta-old",
                "catalog_added_at": "2026-09-16",
            },
        ]
    }
    path = tmp_path / "catalog-added.json"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    monkeypatch.setenv("ANIMEDIA_CATALOG_ADDED_LEDGER", str(path))
    mod.АНИМЕДИА_CATALOG_ADDED_PATH = str(path)
    вид = _вид(mod, catalog, details)
    events = вид._catalog_added_events()
    assert len(events) >= 2
    assert all(e["event_kind"] == "catalog_added" for e in events)
    assert all(e.get("catalog_added_at") for e in events)
    home = вид.главная()
    assert 'data-b05="populated"' in home
    assert "Новое в каталоге" in home
    assert 'data-card-variant="catalog-added"' in home
    assert "Добавлено" in home
    # Forbidden episode-event chrome on catalog cards.
    assert re.search(r'zt--catalog-added[^>]*>[\s\S]*?aeps__num', home) is None
    assert "104 серия" not in home
    # available count wording when seasons exist
    if "Доступно" in home:
        assert "Доступно" in home and "серий" in home
        assert not re.search(r"Доступно\s+\d+\s+серия\b", home)
    page = вид.список("/new", {})
    assert 'data-b05-page="populated"' in page
    assert 'data-card-variant="catalog-added"' in page
    assert 'class="aeps__row"' not in page


def test_rejects_rows_without_catalog_added_at(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    ledger = {
        "events": [
            {
                "event_id": "bad1",
                "title_slug": "alpha-anime",
                "published_at": "2026-09-18T12:00:00Z",
            },
            {
                "event_id": "ok1",
                "title_slug": "beta-series",
                "catalog_added_at": "2026-09-17T08:00:00Z",
            },
        ]
    }
    path = tmp_path / "catalog-added.json"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    monkeypatch.setenv("ANIMEDIA_CATALOG_ADDED_LEDGER", str(path))
    mod.АНИМЕДИА_CATALOG_ADDED_PATH = str(path)
    events = _вид(mod, catalog, details)._catalog_added_events()
    slugs = {e["slug"] for e in events}
    assert "alpha-anime" not in slugs
    assert "beta-series" in slugs


def test_css_b05_grid_breakpoints(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert "zg--catalog-added" in css
    assert "min-width:1600px" in css
    assert "repeat(8," in css
    assert "zsec--b05-gap" in css
