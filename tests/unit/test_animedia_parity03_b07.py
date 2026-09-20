"""B07 title passport — description join, ratings, geometry."""
from __future__ import annotations

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


def test_description_present_in_ssr(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    html = вид.тайтл(item, details["details"]["alpha-anime"])
    assert 'data-b07-desc="present"' in html
    assert "Описание альфы" in html
    assert "Описание пока не передано источником" not in html
    assert 'data-title-join="ok"' in html


def test_description_true_gap_one_line(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "gamma-movie")
    det = dict(details["details"]["gamma-movie"])
    det.pop("description", None)
    det.pop("short_description", None)
    html = вид.тайтл(item, det)
    assert 'data-b07-desc="gap"' in html
    assert "Описание пока не передано источником" in html
    # Gap must not leak into meta description.
    assert "Описание пока не передано источником" not in re.search(
        r'<meta name="description" content="([^"]*)"', html).group(1)


def test_ratings_labels_always_visible_missing_not_zero(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "beta-series")
    det = dict(details["details"]["beta-series"])
    # beta fixture may lack ratings
    html = вид.тайтл(item, det)
    assert 'data-b07="ratings"' in html
    assert 'data-rating-source="shikimori"' in html
    assert 'data-rating-source="kp"' in html
    assert 'data-rating-source="imdb"' in html
    # Missing must be em dash, never fabricated 0.
    if 'data-rating-missing="1"' in html:
        assert 'data-missing="1">—</span>' in html
        assert not re.search(r'data-rating-missing="1"[^>]*>[\s\S]*?>0<', html)


def test_no_huge_primary_score_without_policy(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    html = вид.тайтл(item, details["details"]["alpha-anime"])
    # Big primary score block disabled without source-priority policy.
    assert "ztitle__score" not in html or 'class="ztitle__score"' not in html
    assert 'data-player-status=' in html
    assert "ztitle-gap" in mod.АНИМЕДИА_СТИЛЬ
    assert "max-height:24px" in mod.АНИМЕДИА_СТИЛЬ
    assert "240px minmax(0,1fr) 170px" in mod.АНИМЕДИА_СТИЛЬ.replace(" ", "") or \
           "240px minmax(0,1fr) 170px" in mod.АНИМЕДИА_СТИЛЬ


def test_availability_labeled_not_episode_event(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    html = вид.тайтл(item, details["details"]["alpha-anime"])
    assert "Доступно серий" in html
    assert "Количество серий" not in html
