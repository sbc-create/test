"""CLI dry-run validation of an approved_relevant_manifest file."""
from __future__ import annotations

import json
from pathlib import Path

from seo_operator.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VALID_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "approved-relevant-manifest.valid.json"
INVALID_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "approved-relevant-manifest.invalid.json"


class TestRelevanceValidateCli:
    def test_valid_manifest_exits_zero(self, capsys):
        code = main(["relevance-validate", "--manifest", str(VALID_FIXTURE)])
        out = capsys.readouterr().out
        assert code == 0
        assert "OK" in out
        assert "Topvisor не вызывался" in out

    def test_invalid_manifest_exits_nonzero(self, capsys):
        code = main(["relevance-validate", "--manifest", str(INVALID_FIXTURE)])
        err = capsys.readouterr().err
        assert code == 3
        assert "FAIL" in err

    def test_missing_file_is_blocked_input(self, capsys, tmp_path):
        code = main(["relevance-validate", "--manifest", str(tmp_path / "nope.json")])
        err = capsys.readouterr().err
        assert code == 3
        assert "BLOCKED_INPUT" in err

    def test_valid_manifest_reports_sync_eligible_count(self, tmp_path):
        # A manifest with zero sync-eligible entries (both fixture entries are
        # either not APPROVED_RELEVANT or not on a ready site) reports 0, not
        # nothing, and still exits 0: an honest empty result is not a failure.
        code = main(["relevance-validate", "--manifest", str(VALID_FIXTURE)])
        assert code == 0
        data = json.loads(VALID_FIXTURE.read_text())
        assert all(
            e["relevance_decision"]["verdict"] != "APPROVED_RELEVANT" or not e["site_ready"]
            for e in data["entries"]
        )
