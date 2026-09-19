"""BLOCK_06: ratings presentation contract."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load  # noqa: E402


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


class TestBlock06Ratings:
    def test_amd_label_is_animemedia(self, fe):
        mod, _, _ = fe
        assert mod.ИСТОЧНИКИ_ОЦЕНОК["amd"][0] == "AnimeMedia"
        assert mod.ИСТОЧНИКИ_ОЦЕНОК["amd"][2] is True  # user/vitrine

    def test_zero_score_not_rendered(self, fe):
        mod, _, _ = fe
        det = {
            "ratings_by_source": {
                "shikimori": {"value": 0, "scale": 10, "votes": 12},
                "imdb": {"value": 7.4, "scale": 10, "votes": 100},
            }
        }
        scores = mod.оценки_по_источникам(det)
        keys = [o["ключ"] for o in scores]
        assert "shikimori" not in keys
        assert "imdb" in keys
        html = mod.разметка_оценок(det, "rbs", пусто=False)
        assert 'data-source="imdb"' in html
        assert ">0<" not in html.replace("/10", "")

    def test_sources_have_labels(self, fe):
        mod, _, _ = fe
        det = {
            "ratings_by_source": {"shikimori": {"value": 8.2, "scale": 10}},
            "kinopoisk_rating": 7.6,
            "imdb_rating": 7.4,
        }
        html = mod.разметка_оценок(det, "rbs", пусто=False)
        assert "Shikimori" in html and "КП" in html and "IMDb" in html
        assert html.count("data-source=") == 3
