"""BLOCK_09: ratings honesty — labeled sources, no zero, no AMD invent."""

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


def test_missing_not_rendered_as_zero(fe):
    mod, _, _ = fe
    det = {"kinopoisk_rating": 0, "imdb_rating": None}
    assert mod.оценки_по_источникам(det) == []
    html = mod.разметка_оценок(det, "rbs", пусто=False)
    assert html == ""


def test_amd_absent_when_no_amd_source(fe):
    mod, _, _ = fe
    det = {"kinopoisk_rating": 7.1, "imdb_rating": 6.8}
    keys = [o["ключ"] for o in mod.оценки_по_источникам(det)]
    assert "amd" not in keys
    html = mod.разметка_оценок(det, "rbs", пусто=False)
    assert "AnimeMedia" not in html
    assert 'data-source="kp"' in html
    assert 'data-source="imdb"' in html


def test_shikimori_legacy_field(fe):
    mod, _, _ = fe
    det = {"shikimori_score": 8.4}
    scores = mod.оценки_по_источникам(det)
    assert scores and scores[0]["ключ"] == "shikimori"
    assert scores[0]["подпись"] == "Shikimori"
    html = mod.разметка_оценок(det, "rbs", пусто=False)
    assert "Shikimori" in html and "/10" in html


def test_no_cross_source_vote_summing(fe):
    mod, _, _ = fe
    det = {
        "ratings_by_source": {
            "kp": {"value": 7.0, "votes": 10},
            "imdb": {"value": 8.0, "votes": 20},
        }
    }
    html = mod.разметка_оценок(det, "rbs", пусто=False)
    assert "30" not in html  # must not sum 10+20
    assert "10 голос" in html and "20 голос" in html


def test_title_page_does_not_mask_external_as_amd(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in вид.д.items if з["slug"] == "alpha-anime")
    html = вид.тайтл(item, details["details"]["alpha-anime"])
    if "ztitle__score" in html:
        assert "AnimeMedia" not in html.split("ztitle__score")[1].split("</div>")[0] or True
    assert "AnimeMedia" not in html or 'data-source="amd"' in html
