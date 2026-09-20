"""BLOCK_01 oracle gates for ANIMEDIA-REFERENCE-PARITY-02."""

from __future__ import annotations

import json
from pathlib import Path

EV = Path("artifacts/evidence/animedia-reference-parity-2026-09-20")
B01 = EV / "03-blocks" / "BLOCK_01"


def test_reference_access_failures_zero():
    access = json.loads((EV / "raw" / "BLOCK_01_REFERENCE_ACCESS.json").read_text())
    assert access["REFERENCE_ACCESS_FAILURES"] == 0


def test_problem_routes_in_before_evidence_both_domains():
    manifest = json.loads((EV / "REFERENCE_MANIFEST.json").read_text())
    for dom in ("icu", "space"):
        before = manifest["ours_before"][dom]
        assert "title_problem" in before
        assert "episode_problem" in before
        assert before["title_problem"]["path"] == "/title/nelyud-film-2-stolknovenie/"
        assert (
            before["episode_problem"]["path"]
            == "/title/master-lda-i-plameni-2/season-2/episode-104/"
        )


def test_data_join_hard_gates_zero():
    join = json.loads((B01 / "DATA_JOIN_ORACLE.json").read_text())
    g = join["gates"]
    assert g["SOURCE_AVAILABLE_NOT_RENDERED"] == 0
    assert g["SOURCE_POSTER_AVAILABLE_BUT_NOT_RENDERED"] == 0
    assert g["SOURCE_DESCRIPTION_AVAILABLE_BUT_NOT_RENDERED"] == 0
    assert g["WRONG_TITLE_ID_MAPPINGS"] == 0
    assert g["AMBIGUOUS_AUTO_MAPPINGS"] == 0


def test_contract_not_mutated_by_block01():
    pinned = (EV / "ACCEPTANCE_CONTRACT_SHA256.txt").read_text().strip()
    assert pinned == "e6aad06dc3f0d633e22bda18eac6b700a321c84e5742e7efffdaedab160ae94c"
    # baseline ROUTE_MATRIX still contains both problem paths
    matrix = json.loads((EV / "ROUTE_MATRIX.json").read_text())
    paths = {r["path"] for r in matrix["routes"]}
    assert "/title/nelyud-film-2-stolknovenie/" in paths
    assert "/title/master-lda-i-plameni-2/season-2/episode-104/" in paths
