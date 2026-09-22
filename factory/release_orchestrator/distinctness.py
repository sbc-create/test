"""Template distinctness matrix for multi-site families."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DIMENSIONS = (
    "data_design",
    "ia",
    "home_block_order",
    "card_profile",
    "typography",
    "geometry",
    "navigation",
    "title_passport",
    "recommendations",
    "footer",
    "responsive_screenshots",
)


@dataclass
class DistinctnessReport:
    ok: bool
    matrix: dict[str, dict[str, str]] = field(default_factory=dict)
    collisions: list[str] = field(default_factory=list)
    contact_sheet: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "matrix": self.matrix,
            "collisions": self.collisions,
            "contact_sheet": self.contact_sheet,
        }


def build_distinctness_matrix(sites: list[dict[str, Any]]) -> DistinctnessReport:
    """sites rows must include site_id and per-dimension fingerprint strings."""
    matrix: dict[str, dict[str, str]] = {}
    for site in sites:
        sid = site["site_id"]
        matrix[sid] = {dim: str(site.get(dim) or site.get("design_id") or "") for dim in DIMENSIONS}

    collisions: list[str] = []
    ids = [s["site_id"] for s in sites]
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            same = [dim for dim in DIMENSIONS if matrix[a][dim] and matrix[a][dim] == matrix[b][dim]]
            # Identical across all non-empty dimensions → reject "same template different colors".
            nonempty = [dim for dim in DIMENSIONS if matrix[a][dim] or matrix[b][dim]]
            if nonempty and len(same) == len(nonempty):
                collisions.append(f"{a} indistinguishable from {b}")
            # data_design must differ within a family batch when multiple sites.
            if matrix[a]["data_design"] and matrix[a]["data_design"] == matrix[b]["data_design"]:
                collisions.append(f"{a} and {b} share data_design={matrix[a]['data_design']}")

    contact = [f"{sid}:{matrix[sid]['data_design']}" for sid in ids]
    return DistinctnessReport(ok=not collisions, matrix=matrix, collisions=collisions, contact_sheet=contact)
