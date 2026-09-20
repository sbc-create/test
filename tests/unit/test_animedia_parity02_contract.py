"""Pin ANIMEDIA-REFERENCE-PARITY-02 acceptance contract after BLOCK_00 freeze."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

EV = Path("artifacts/evidence/animedia-reference-parity-2026-09-20")
CONTRACT_FILES = [
    "REFERENCE_CONTRACT.json",
    "ROUTE_MATRIX.json",
    "REQUIRED_SECTION_GRAPH.json",
    "VISUAL_THRESHOLDS.json",
    "SCREENSHOT_MANIFEST.expected.json",
]
EXPECTED_SHA = "e6aad06dc3f0d633e22bda18eac6b700a321c84e5742e7efffdaedab160ae94c"


def _bundle_sha() -> str:
    parts: list[bytes] = []
    for name in sorted(CONTRACT_FILES):
        raw = (EV / name).read_bytes()
        parts.append(name.encode() + b"\0" + raw)
    return hashlib.sha256(b"\n".join(parts)).hexdigest()


def test_acceptance_contract_sha256_matches_freeze():
    pinned = (EV / "ACCEPTANCE_CONTRACT_SHA256.txt").read_text().strip()
    assert pinned == EXPECTED_SHA
    assert _bundle_sha() == EXPECTED_SHA


def test_problem_routes_present_and_required():
    matrix = json.loads((EV / "ROUTE_MATRIX.json").read_text())
    paths = {r["path"] for r in matrix["routes"]}
    assert "/title/nelyud-film-2-stolknovenie/" in paths
    assert "/title/master-lda-i-plameni-2/season-2/episode-104/" in paths
    for r in matrix["routes"]:
        if r.get("problem"):
            assert r.get("required") is True


def test_thresholds_not_lowered_below_baseline():
    thr = json.loads((EV / "VISUAL_THRESHOLDS.json").read_text())
    scores = thr["scores"]
    assert scores["OVERALL_REFERENCE_SCORE_MIN"] >= 85
    assert scores["MIN_ROUTE_SCORE"] >= 80
    assert scores["HOME_SCORE_MIN"] >= 85
    assert scores["TITLE_SCORE_MIN"] >= 85
    assert scores["EPISODE_SCORE_MIN"] >= 85
    assert scores["HEADER_SCORE_MIN"] >= 85
    assert thr["self_reported_visual_score_allowed"] is False


def test_control_titles_include_forced_problem_slugs():
    contract = json.loads((EV / "REFERENCE_CONTRACT.json").read_text())
    titles = contract["control_title_selection"]["titles"]
    slugs = {t["slug"] for t in titles}
    assert "nelyud-film-2-stolknovenie" in slugs
    assert "master-lda-i-plameni-2" in slugs
    assert len(titles) == 20
