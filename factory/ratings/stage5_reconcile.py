"""Stage 5 accepted-cap reconciliation — inventory overshoot without deleting rows."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.ratings.stage5_constants import ACCEPTED_TARGET, EVIDENCE_DIR, SOURCE_ALLOWED

STAGE5_RUN_ID = "stage5-supervised-20260919T224456Z-9bc222"


def reconcile_accepted_cap(
    *,
    db_path: Path,
    run_id: str = STAGE5_RUN_ID,
    accepted_target: int = ACCEPTED_TARGET,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    """Classify Stage5 Shikimori observations into within-cap vs overshoot.

    Policy: do **not** delete overshoot rows. They are valid Shikimori
    observations retained for last-good/coverage; the hard-cap bug is fixed
    going forward. Reconciliation is evidence-only.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in conn.execute(
            """SELECT id, canonical_title_id, external_id, normalized_score, vote_count,
                      observed_at, run_id, idempotency_key, payload_sha256
               FROM rating_observations
               WHERE source_key=? AND run_id=?
               ORDER BY id ASC""",
            (SOURCE_ALLOWED, run_id),
        )
    ]
    amd = conn.execute(
        "SELECT COUNT(*) AS c FROM rating_observations WHERE source_key='amd_online'"
    ).fetchone()["c"]
    votes = conn.execute("SELECT COUNT(*) AS c FROM rating_vote_current").fetchone()["c"]
    conn.close()

    within = rows[:accepted_target]
    overshoot = rows[accepted_target:]
    digest = hashlib.sha256(
        json.dumps(
            {
                "run_id": run_id,
                "within_ids": [r["id"] for r in within],
                "overshoot_ids": [r["id"] for r in overshoot],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()

    out = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": run_id,
        "source": SOURCE_ALLOWED,
        "ACCEPTED_TARGET": accepted_target,
        "TOTAL_OBSERVATIONS_FOR_RUN": len(rows),
        "WITHIN_CAP_COUNT": len(within),
        "OVERSHOOT_COUNT": len(overshoot),
        "OVERSHOOT_RETAINED": 1,
        "OVERSHOOT_DELETED": 0,
        "DELETE_POLICY": "retain_valid_observations_no_blind_delete",
        "AMD_ROWS_UNCHANGED": int(amd) == 100,
        "AMD_OBSERVATION_COUNT": int(amd),
        "USER_VOTE_ROWS_UNCHANGED": int(votes) == 0,
        "USER_VOTE_COUNT": int(votes),
        "within_cap_id_range": (
            [within[0]["id"], within[-1]["id"]] if within else []
        ),
        "overshoot_id_range": (
            [overshoot[0]["id"], overshoot[-1]["id"]] if overshoot else []
        ),
        "within_cap_head": [
            {
                "id": r["id"],
                "canonical_title_id": r["canonical_title_id"],
                "external_id": r["external_id"],
            }
            for r in within[:5]
        ],
        "overshoot_all": [
            {
                "id": r["id"],
                "canonical_title_id": r["canonical_title_id"],
                "external_id": r["external_id"],
                "normalized_score": r["normalized_score"],
                "observed_at": r["observed_at"],
            }
            for r in overshoot
        ],
        "reconciliation_digest": digest,
        "note": (
            "First ACCEPTED_TARGET rows by ascending observation id are the "
            "authorized Stage5 cohort. Remaining rows are overshoot retained "
            "as valid last-good data; no production DELETE performed."
        ),
    }
    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "ACCEPTED_CAP_RECONCILIATION.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return out


def main() -> int:
    from factory.paths import PATHS
    from factory.ratings.prod_db import resolve_canonical_db

    ev = PATHS.root / EVIDENCE_DIR
    result = reconcile_accepted_cap(db_path=resolve_canonical_db(), evidence_dir=ev)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
