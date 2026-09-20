"""B00 independent gates for ANIMEDIA-BLOCKWISE-PARITY-03."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

EV = Path("artifacts/evidence/animedia-blockwise-parity-03-2026-09-20")
CONTRACT = EV / "00-contract"
PASSPORTS = EV / "passports"
MANIFESTS = EV / "manifests"
BASE = EV / "01-reference-baseline"
GATES = EV / "gates"

REQUIRED_PASSPORT_KEYS = [
    "block_id",
    "routes",
    "intent",
    "ownership",
    "versioned_contract_id",
    "reference_evidence",
    "entity_or_event_type",
    "source_path",
    "provenance",
    "eligibility",
    "sort_key",
    "dedupe_key",
    "visible_timestamp_semantic",
    "required_fields",
    "optional_fields",
    "freshness_sla",
    "max_stale",
    "snapshot_revision",
    "display_policy_by_state",
    "desktop_geometry",
    "tablet_geometry",
    "mobile_geometry",
    "interactions",
    "cta_route",
    "seo_contract",
    "tests",
    "evidence_paths",
    "remaining_data_gap",
]
REQUIRED_STATES = [
    "normal",
    "empty",
    "missing_required",
    "missing_optional",
    "stale",
    "error",
]
ALLOWED_OWNERSHIP = {
    "template",
    "core_data",
    "search",
    "player",
    "seo",
    "owner_values",
}
ALLOWED_POLICY = {
    "populated",
    "hidden",
    "explicit_empty",
    "blocked",
    "explicit_field_placeholder",
    "last_good_with_badge",
    "explicit_error",
    "page_error",
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _contract_corpus() -> list[Path]:
    files = sorted(
        [
            *CONTRACT.glob("*.json"),
            PASSPORTS / "BLOCK_PASSPORTS.json",
            MANIFESTS / "LOCAL_FIXTURE_MANIFEST.json",
            MANIFESTS / "LIVE_ENTITY_MANIFEST.json",
        ]
    )
    return [f for f in files if f.name != "FILE_DIGESTS.json"]


@pytest.fixture(scope="module")
def freeze() -> dict:
    assert (GATES / "B00_FREEZE.json").is_file()
    return json.loads((GATES / "B00_FREEZE.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def independent() -> dict:
    assert (GATES / "B00_INDEPENDENT_GATES.json").is_file()
    return json.loads((GATES / "B00_INDEPENDENT_GATES.json").read_text(encoding="utf-8"))


def test_evidence_root_present() -> None:
    assert EV.is_dir()
    assert (EV / "03-blocks" / "BLOCK_B00.md").is_file()


def test_reference_baseline_nine_captures() -> None:
    log = json.loads((BASE / "CAPTURE_LOG.json").read_text(encoding="utf-8"))
    assert log["REFERENCE_ACCESS_FAILURES"] == 0
    ok = [e for e in log["entries"] if e.get("ok")]
    assert len(ok) == 9
    for route in ("home", "collections", "title"):
        for vp in ("d1440", "t768", "m390"):
            d = BASE / route / vp
            assert (d / "full.png").is_file()
            assert (d / "above-fold.png").is_file()
            assert (d / "dom.json").is_file()


def test_contract_sha256_matches_corpus(freeze: dict) -> None:
    digests = {
        str(f.relative_to(EV)): _sha256_file(f) for f in _contract_corpus()
    }
    lines = "\n".join(f"{k}={v}" for k, v in sorted(digests.items())) + "\n"
    computed = _sha256_text(lines)
    assert freeze["CONTRACT_SHA256"] == computed
    assert (CONTRACT / "CONTRACT_SHA256.txt").read_text(encoding="utf-8").strip() == computed
    assert freeze["CONTRACT_MUTATED"] == 0


def test_passport_manifest_complete() -> None:
    data = json.loads((PASSPORTS / "BLOCK_PASSPORTS.json").read_text(encoding="utf-8"))
    blocks = {b["block_id"]: b for b in data["blocks"]}
    for i in range(0, 17):
        bid = f"B{i:02d}"
        assert bid in blocks, bid
        b = blocks[bid]
        for key in REQUIRED_PASSPORT_KEYS:
            assert key in b, f"{bid} missing {key}"
        assert b["ownership"] in ALLOWED_OWNERSHIP
        dps = b["display_policy_by_state"]
        for st in REQUIRED_STATES:
            assert st in dps
            assert dps[st] in ALLOWED_POLICY
            assert "|" not in dps[st]


def test_display_policies_frozen() -> None:
    pol = json.loads((CONTRACT / "DISPLAY_POLICIES_FROZEN.json").read_text(encoding="utf-8"))
    assert pol.get("frozen") is True
    assert pol.get("DISPLAY_POLICIES_FROZEN") == 1
    for name, p in pol["policies"].items():
        for st in REQUIRED_STATES:
            if st in p:
                assert p[st] in ALLOWED_POLICY, f"{name}.{st}"
                assert "|" not in str(p[st])


def test_independent_gates_pass(independent: dict, freeze: dict) -> None:
    assert independent["REFERENCE_BASELINE_VALID"] == 1
    assert independent["PASSPORT_MANIFEST_VALID"] == 1
    assert independent["DISPLAY_POLICIES_FROZEN"] == 1
    assert independent["pass"] is True
    assert freeze["REFERENCE_BASELINE_VALID"] == 1
    assert freeze["PASSPORT_MANIFEST_VALID"] == 1
    assert freeze["DISPLAY_POLICIES_FROZEN"] == 1


def test_manifest_expected_counts_frozen() -> None:
    expected = json.loads(
        (CONTRACT / "SCREENSHOT_MANIFEST.expected.json").read_text(encoding="utf-8")
    )
    local = json.loads((MANIFESTS / "LOCAL_FIXTURE_MANIFEST.json").read_text(encoding="utf-8"))
    live = json.loads((MANIFESTS / "LIVE_ENTITY_MANIFEST.json").read_text(encoding="utf-8"))
    local_n = local.get("case_count", len(local.get("cases", [])))
    live_n = live.get("case_count", len(live.get("cases", [])))
    assert expected["SCREENSHOT_MATRIX_EXPECTED_LOCAL"] == local_n == 114
    assert expected["SCREENSHOT_MATRIX_EXPECTED_LIVE"] == live_n == 84


def test_provenance_inventory_honest_gaps() -> None:
    inv = json.loads((CONTRACT / "DATA_PROVENANCE_INVENTORY.json").read_text(encoding="utf-8"))
    assert inv["published_at_semantic"] == "AMBIGUOUS"
    assert inv["TRUE_PROVIDER_PLAYABLE_EVENT_COUNT"] == 0
    assert inv["TRUE_EPISODE_RELEASE_EVENT_COUNT"] == 0
    assert inv["CATALOG_ADDED_EVENT_COUNT"] == 0
    assert inv["provider_playable_ledger"] is None
    assert inv["catalog_added_ledger"] is None
    assert inv["episode_air_feed"] is None


def test_indexability_before_present() -> None:
    idx = json.loads((CONTRACT / "INDEXABILITY_BEFORE.json").read_text(encoding="utf-8"))
    for domain in ("animedia.icu", "animedia.space"):
        assert domain in idx
        assert "noindex" in idx[domain]["meta_robots"]


def test_geometry_tolerances_locked() -> None:
    tol = json.loads((CONTRACT / "GEOMETRY_TOLERANCES.json").read_text(encoding="utf-8"))
    assert tol["section_order_presence_deviations"] == 0
    assert tol["overflow_overlap_px"] == 0
    assert tol["b03_empty_heading_panel_max_px"] == 96
