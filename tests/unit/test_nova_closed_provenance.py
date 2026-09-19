"""Точное соответствие source_commit / runtime_commit закрытых nova-доменов."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROV_PATH = ROOT / "automation" / "host" / "nova_closed_provenance.py"


def _load_prov():
    spec = importlib.util.spec_from_file_location("nova_closed_provenance", PROV_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


EXPECTED = {
    "lordserial33.biz": {
        "site": "lords-02",
        "source_commit": "5fc22310fdfb8f0c8748f69e5603e4de3267f27e",
        "runtime_commit": "5fc22310fdfb8f0c8748f69e5603e4de3267f27e",
        "profile": "lords-new",
        "family": "lords",
    },
    "animedia.icu": {
        "site": "animedia-01",
        "source_commit": "b023bd50cced8d281cb3814a75bf72b429afee0b",
        "runtime_commit": "5fc22310fdfb8f0c8748f69e5603e4de3267f27e",
        "profile": "animedia-general",
        "family": "animedia",
    },
    "animedia.space": {
        "site": "animedia-02",
        "source_commit": "b023bd50cced8d281cb3814a75bf72b429afee0b",
        "runtime_commit": "5fc22310fdfb8f0c8748f69e5603e4de3267f27e",
        "profile": "animedia-general",
        "family": "animedia",
    },
    "zonafilm.space": {
        "site": "zona-01",
        "source_commit": "a10e68b2350a020a2f7d5efe28cd98ef2fc89edd",
        "runtime_commit": "5fc22310fdfb8f0c8748f69e5603e4de3267f27e",
        "profile": "zona-general",
        "family": "zona",
    },
}


class TestClosedNovaProvenance:
    def test_exact_source_and_runtime_commits_for_four_domains(self):
        prov = _load_prov()
        by_domain = prov.by_domain()
        assert set(by_domain) == set(EXPECTED)
        for domain, expect in EXPECTED.items():
            row = by_domain[domain]
            assert row["source_commit"] == expect["source_commit"], domain
            assert row["runtime_commit"] == expect["runtime_commit"], domain
            assert row["profile"] == expect["profile"], domain
            assert row["family"] == expect["family"], domain
            assert row["site"] == expect["site"], domain

    def test_zona_source_is_not_substituted_by_runtime(self):
        prov = _load_prov()
        zona = prov.by_domain()["zonafilm.space"]
        assert zona["source_commit"] == prov.ZONA_COMMIT
        assert zona["runtime_commit"] == prov.LORDS_COMMIT
        assert zona["source_commit"] != zona["runtime_commit"]

    def test_build_manifest_keeps_both_fields(self):
        prov = _load_prov()
        м = prov.build_manifest(
            family="zona",
            design_version="1.2.0",
            source_commit=prov.ZONA_COMMIT,
            runtime_commit=prov.LORDS_COMMIT,
            build_id="test-a10e68b2-nova",
            artifact_sha256="a" * 64,
            profile="zona-general",
            built_at="2026-09-18T00:00:00Z",
        )
        assert м["source_commit"] == prov.ZONA_COMMIT
        assert м["runtime_commit"] == prov.LORDS_COMMIT
        assert м["profile"] == "zona-general"
        assert м["template_family"] == "zona"

    @pytest.mark.parametrize("domain", sorted(EXPECTED))
    def test_source_commit_is_full_sha40(self, domain):
        sha = EXPECTED[domain]["source_commit"]
        assert len(sha) == 40
        assert all(c in "0123456789abcdef" for c in sha)
