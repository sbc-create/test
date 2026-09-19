"""Gateway: шаблоны читают snapshot/projection только по canonical_title_id."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factory.ratings.formula import FORMULA_VERSION
from factory.ratings.models import FreshnessState
from factory.ratings.rotation import ROTATION_ALGORITHM_VERSION

HIDDEN = {
    FreshnessState.MISSING.value,
    FreshnessState.EXPIRED.value,
    FreshnessState.CONFLICT.value,
}

UI_LABELS = {
    "shikimori": "Shikimori",
    "amd_online": "AMD",
    "provider_feed_kinopoisk": "КП",
    "kinopoisk": "КП",
    "provider_feed_imdb": "IMDb",
    "imdb": "IMDb",
}


def format_score(score: float) -> str:
    text = f"{score:.1f}".replace(".", ",")
    return text


def format_votes(votes: int | None) -> str | None:
    if votes is None:
        return None
    return f"{votes:,}".replace(",", " ")


def format_ui_line(source_key: str, score: float, votes: int | None = None) -> str:
    label = UI_LABELS.get(source_key, source_key)
    base = f"{label} {format_score(score)}"
    if votes is not None and source_key in ("shikimori", "amd_online"):
        return f"{base} · {format_votes(votes)} оценки"
    return base


class RatingGateway:
    """Чтение готового snapshot + combined/local projections. Сеть запрещена."""

    def __init__(
        self,
        snapshot: dict[str, Any] | Path | None = None,
        *,
        combined: dict[str, dict[str, Any]] | None = None,
        local: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        if isinstance(snapshot, Path):
            self._data = json.loads(snapshot.read_text(encoding="utf-8"))
        elif isinstance(snapshot, dict):
            self._data = snapshot
        else:
            self._data = {"titles": []}
        self._index = {
            t["canonical_title_id"]: t for t in (self._data.get("titles") or [])
        }
        self._combined = combined or {}
        self._local = local or {}

    @classmethod
    def from_store(cls, store, *, primary_source: str = "shikimori") -> RatingGateway:
        from factory.ratings.snapshot import build_snapshot

        snap = build_snapshot(store, primary_source=primary_source)
        combined: dict[str, dict[str, Any]] = {}
        local: dict[str, dict[str, Any]] = {}
        try:
            for row in store.conn.execute("SELECT * FROM rating_combined_projection"):
                combined[row["canonical_title_id"]] = dict(row)
            for row in store.conn.execute("SELECT * FROM rating_local_aggregate"):
                key = row["canonical_title_id"]
                local[key] = dict(row)
        except Exception:  # noqa: BLE001 — table may be absent on old DBs mid-test
            pass
        return cls(snap, combined=combined, local=local)

    def get_all(self, canonical_title_id: str) -> dict[str, Any]:
        title = self._index.get(canonical_title_id)
        if not title:
            return {"canonical_title_id": canonical_title_id, "scores": {}, "primary": None}
        scores = {}
        for src, row in (title.get("scores") or {}).items():
            if row.get("freshness") in HIDDEN:
                continue
            if row.get("score") is None:
                continue
            scores[src] = dict(row)
        return {
            "canonical_title_id": canonical_title_id,
            "scores": scores,
            "primary": title.get("primary"),
            "provenance": {src: row.get("provenance_url") for src, row in scores.items()},
        }

    def get_source(self, canonical_title_id: str, source_key: str) -> dict[str, Any] | None:
        return self.get_all(canonical_title_id)["scores"].get(source_key)

    def get_primary(self, canonical_title_id: str, primary_source: str | None = None) -> dict[str, Any] | None:
        all_ = self.get_all(canonical_title_id)
        key = primary_source or all_.get("primary") or self._data.get("primary_source")
        if not key:
            if len(all_["scores"]) == 1:
                key = next(iter(all_["scores"]))
            else:
                return None
        row = all_["scores"].get(key)
        if not row:
            return None
        return {"source": key, **row, "ui": format_ui_line(key, row["score"], row.get("vote_count"))}

    def batch_lookup(self, canonical_title_ids: list[str]) -> dict[str, dict[str, Any]]:
        return {cid: self.contract(cid) for cid in canonical_title_ids}

    def contract(self, canonical_title_id: str) -> dict[str, Any]:
        """Universal template contract: separate sources, local, combined, rotation."""
        all_ = self.get_all(canonical_title_id)
        rating_sources = []
        for src, row in all_["scores"].items():
            entry = {
                "source": src,
                "score": row.get("score"),
                "voteCount": row.get("vote_count"),
                "fetchedAt": row.get("observed_at"),
                "freshness": row.get("freshness"),
                "provenance": {"url": row.get("provenance_url")},
            }
            comps = row.get("components") or row.get("component_scores")
            if comps:
                entry["components"] = comps
            if row.get("attribution"):
                entry["attribution"] = row["attribution"]
            elif src == "amd_online":
                entry["attribution"] = "Источник: AMD.online"
            if row.get("canonical_source_url"):
                entry["canonicalSourceUrl"] = row["canonical_source_url"]
            elif row.get("provenance_url"):
                entry["canonicalSourceUrl"] = row["provenance_url"]
            rating_sources.append(entry)

        local_row = self._local.get(canonical_title_id)
        local_rating = None
        if local_row and local_row.get("accepted_vote_count"):
            avg = local_row.get("average_score")
            local_rating = {
                "score": float(avg) if avg is not None else None,
                "voteCount": int(local_row["accepted_vote_count"]),
                "scope": local_row.get("scope") or "site_or_network",
            }
            if local_rating["score"] is None:
                local_rating = None

        comb = self._combined.get(canonical_title_id)
        combined_rating = None
        rotation = None
        if comb and comb.get("combined_ui") is not None:
            combined_rating = {
                "score": float(comb["combined_ui"]),
                "formulaVersion": comb.get("formula_version") or FORMULA_VERSION,
                "baselineWeight": comb.get("baseline_weight"),
                "localVoteCount": comb.get("local_vote_count"),
                "state": comb.get("state"),
            }
            rotation = {
                "score": float(comb["combined_ui"]),
                "algorithmVersion": comb.get("rotation_algorithm") or ROTATION_ALGORITHM_VERSION,
            }
        elif comb and comb.get("combined_raw") is None:
            combined_rating = {
                "score": None,
                "formulaVersion": comb.get("formula_version") or FORMULA_VERSION,
                "baselineWeight": comb.get("baseline_weight"),
                "localVoteCount": comb.get("local_vote_count"),
                "state": comb.get("state") or "INSUFFICIENT_LOCAL",
            }

        return {
            "canonical_title_id": canonical_title_id,
            "ratingSources": rating_sources,
            "localRating": local_rating,
            "combinedRating": combined_rating,
            "rotation": rotation,
            # legacy flat scores kept for Stage 1 callers
            "scores": all_["scores"],
        }

    def coverage(self) -> dict[str, Any]:
        total = len(self._index)
        with_any = sum(1 for t in self._index.values() if t.get("scores"))
        return {
            "title_count": total,
            "with_rating": with_any,
            "coverage": (with_any / total) if total else None,
            "schema_version": self._data.get("schema_version"),
            "snapshot_sha256": self._data.get("snapshot_sha256"),
            "source_health": self._data.get("source_health"),
        }

    def ui_lines(self, canonical_title_id: str) -> list[str]:
        all_ = self.get_all(canonical_title_id)
        return [
            format_ui_line(src, row["score"], row.get("vote_count"))
            for src, row in all_["scores"].items()
        ]
