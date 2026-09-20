"""B10 recommendations — approved snapshot / DETERMINISTIC_METADATA_RELATED_V1 / 0px."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402

EV = ROOT / "artifacts/evidence/animedia-blockwise-parity-03-2026-09-20"
CONTRACT_SHA = (EV / "00-contract" / "CONTRACT_SHA256.txt").read_text(encoding="utf-8").strip()


def _expand_related_catalog(catalog: dict, details: dict) -> None:
    """Add enough same-type shared-genre titles for ≥4 related candidates."""
    extras = [
        ("epsilon-tv", "Эпсилон", 2023, ["драма", "комедия"]),
        ("zeta-tv", "Зета", 2022, ["драма"]),
        ("eta-tv", "Эта", 2021, ["комедия"]),
        ("theta-tv", "Тета", 2020, ["драма", "фэнтези"]),
        ("iota-movie", "Йота", 2019, ["фэнтези"], "movie"),
    ]
    for row in extras:
        slug, title, year, genres = row[0], row[1], row[2], row[3]
        ctype = row[4] if len(row) > 4 else "tv"
        catalog["items"].append({
            "slug": slug, "title": title, "kind": "Аниме",
            "year": year, "published_at": "2026-01-01T00:00:00Z",
            "poster": f"/poster/{slug}.webp", "url": f"/title/{slug}/",
        })
        details["details"][slug] = {
            "description": f"Описание {title}.",
            "genres": genres,
            "type": ctype,
            "seasons": [{"n": 1, "eps": 12, "avail": 12}] if ctype == "tv" else [],
            "playable": True,
        }
    catalog["count"] = len(catalog["items"])


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


@pytest.fixture
def fe_related(tmp_path):
    mod, catalog, details = _load(tmp_path, version="1.2.4")
    _expand_related_catalog(catalog, details)
    # Rebuild view index with expanded catalog.
    (tmp_path / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    (tmp_path / "details.json").write_text(json.dumps(details), encoding="utf-8")
    return mod, catalog, details


def test_contract_digest_unchanged() -> None:
    assert CONTRACT_SHA == "5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3"


def test_rec_constants_and_css(fe):
    mod, _, _ = fe
    assert mod.АНИМЕДИА_REC_TITLE == "Похожее аниме"
    assert mod.АНИМЕДИА_REC_FALLBACK_ALGORITHM == "DETERMINISTIC_METADATA_RELATED_V1"
    assert mod.АНИМЕДИА_REC_MIN_ITEMS == 4
    css = mod.АНИМЕДИА_СТИЛЬ
    assert "zg--recommendation" in css
    assert "zsec--rel-gap" in css
    assert "repeat(6,minmax(0,1fr))" in css


def test_empty_when_fewer_than_four_candidates(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    recs = вид.похожие(item, details["details"]["alpha-anime"])
    assert recs == []
    html = вид.тайтл(item, details["details"]["alpha-anime"])
    assert 'data-rec-state="empty"' in html
    assert "Похожее аниме" not in html or 'data-rec-state="empty"' in html
    assert "Смотрите также" not in html
    assert "персональн" not in html.lower()


def test_deterministic_fallback_populated(fe_related):
    mod, catalog, details = fe_related
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    det = details["details"]["alpha-anime"]
    a = [з["slug"] for з in вид.похожие(item, det)]
    b = [з["slug"] for з in вид.похожие(item, det)]
    assert a == b
    assert len(a) >= 4
    assert "alpha-anime" not in a
    assert len(a) == len(set(a))
    meta = вид._rec_meta
    assert meta["source"] == "DETERMINISTIC_METADATA_RELATED_V1"
    assert meta["algorithm_version"] == "DETERMINISTIC_METADATA_RELATED_V1"
    assert meta["digest"]
    assert meta["membership_digest"]
    assert meta.get("fallback") is True
    html = вид.тайтл(item, det)
    assert "Похожее аниме" in html
    assert 'data-rec-source="DETERMINISTIC_METADATA_RELATED_V1"' in html
    assert 'data-rec-fallback="1"' in html
    assert 'data-card-grid="recommendation"' in html
    assert "Смотрите также" not in html
    assert "Top-100" not in html and "топ-100" not in html.lower()


def test_same_type_and_shared_genre_only(fe_related):
    mod, catalog, details = fe_related
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    recs = вид.похожие(item, details["details"]["alpha-anime"])
    slugs = {з["slug"] for з in recs}
    # iota-movie is movie + fantasy — must not appear for tv seed.
    assert "iota-movie" not in slugs
    for slug in slugs:
        det = details["details"][slug]
        assert det.get("type") == "tv"
        codes = set(mod._аниме_genre_codes(det))
        seed_codes = set(mod._аниме_genre_codes(details["details"]["alpha-anime"]))
        assert codes & seed_codes


def test_sort_playable_shared_year_slug(fe_related):
    mod, catalog, details = fe_related
    # Make theta non-playable; should sort after playable peers.
    details["details"]["theta-tv"]["playable"] = False
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    slugs = [з["slug"] for з in вид.похожие(item, details["details"]["alpha-anime"])]
    if "theta-tv" in slugs:
        playable_before = []
        for s in slugs:
            if s == "theta-tv":
                break
            playable_before.append(s)
        assert playable_before  # at least one playable ahead
        assert all(details["details"][s].get("playable") for s in playable_before)


def test_approved_snapshot_beats_fallback(fe_related, tmp_path, monkeypatch):
    mod, catalog, details = fe_related
    snap = {
        "schema_version": "animedia.recommendation_snapshot.v1",
        "site_id": "animedia",
        "by_title": {
            "alpha-anime": {
                "ordered_title_ids": [
                    "zeta-tv", "eta-tv", "epsilon-tv", "theta-tv", "beta-series",
                ],
                "algorithm_version": "owner-rec-v1",
                "digest": "deadbeefcafebabe0123456789abcdef",
                "membership_digest": "aabbccddeeff00112233445566778899",
                "generated_at": "2026-09-20T00:00:00Z",
            }
        },
    }
    path = tmp_path / "recs.json"
    path.write_text(json.dumps(snap), encoding="utf-8")
    monkeypatch.setattr(mod, "АНИМЕДИА_RECOMMENDATIONS_PATH", str(path))
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    slugs = [з["slug"] for з in вид.похожие(item, details["details"]["alpha-anime"])]
    assert slugs[:4] == ["zeta-tv", "eta-tv", "epsilon-tv", "theta-tv"]
    assert вид._rec_meta["source"] == "RecommendationSnapshot"
    assert вид._rec_meta["algorithm_version"] == "owner-rec-v1"
    assert вид._rec_meta.get("fallback") is not True
    html = вид.тайтл(item, details["details"]["alpha-anime"])
    assert 'data-rec-source="RecommendationSnapshot"' in html
    assert 'data-rec-fallback="0"' in html


def test_no_invented_personalization_labels(fe_related):
    mod, catalog, details = fe_related
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    html = вид.тайтл(item, details["details"]["alpha-anime"])
    low = html.lower()
    assert "рекомендовано вам" not in low
    assert "для вас" not in low
    assert "популярн" not in html[html.find("Похожее аниме"): html.find("Похожее аниме") + 200].lower() if "Похожее аниме" in html else True
