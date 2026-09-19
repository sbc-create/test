"""Gateway: шаблоны читают snapshot только по canonical_title_id."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factory.ratings.models import FreshnessState

HIDDEN = {
    FreshnessState.MISSING.value,
    FreshnessState.EXPIRED.value,
    FreshnessState.CONFLICT.value,
}

#: UI labels
UI_LABELS = {
    "shikimori": "Shikimori",
    "provider_feed_kinopoisk": "КП",
    "kinopoisk": "КП",
    "provider_feed_imdb": "IMDb",
    "imdb": "IMDb",
}


def format_score(score: float) -> str:
    """8.6 → '8,6' (UI contract)."""
    text = f"{score:.1f}".replace(".", ",")
    return text


def format_votes(votes: int | None) -> str | None:
    if votes is None:
        return None
    return f"{votes:,}".replace(",", " ")


def format_ui_line(source_key: str, score: float, votes: int | None = None) -> str:
    label = UI_LABELS.get(source_key, source_key)
    base = f"{label} {format_score(score)}"
    if votes is not None and source_key == "shikimori":
        return f"{base} · {format_votes(votes)} оценки"
    return base


class RatingGateway:
    """Чтение готового snapshot. Сеть и парсинг запрещены."""

    def __init__(self, snapshot: dict[str, Any] | Path | None = None) -> None:
        if isinstance(snapshot, Path):
            self._data = json.loads(snapshot.read_text(encoding="utf-8"))
        elif isinstance(snapshot, dict):
            self._data = snapshot
        else:
            self._data = {"titles": []}
        self._index = {
            t["canonical_title_id"]: t for t in (self._data.get("titles") or [])
        }

    @classmethod
    def from_store(cls, store, *, primary_source: str = "shikimori") -> "RatingGateway":
        from factory.ratings.snapshot import build_snapshot

        return cls(build_snapshot(store, primary_source=primary_source))

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
            "provenance": {
                src: row.get("provenance_url") for src, row in scores.items()
            },
        }

    def get_source(self, canonical_title_id: str, source_key: str) -> dict[str, Any] | None:
        all_ = self.get_all(canonical_title_id)
        return all_["scores"].get(source_key)

    def get_primary(self, canonical_title_id: str, primary_source: str | None = None) -> dict[str, Any] | None:
        all_ = self.get_all(canonical_title_id)
        key = primary_source or all_.get("primary") or self._data.get("primary_source")
        if not key:
            # Card shows at most one primary; if unset and only one score — that one.
            if len(all_["scores"]) == 1:
                key = next(iter(all_["scores"]))
            else:
                return None
        row = all_["scores"].get(key)
        if not row:
            return None
        return {"source": key, **row, "ui": format_ui_line(key, row["score"], row.get("vote_count"))}

    def batch_lookup(self, canonical_title_ids: list[str]) -> dict[str, dict[str, Any]]:
        return {cid: self.get_all(cid) for cid in canonical_title_ids}

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
        """Title page may show multiple sources; never invent averages."""
        all_ = self.get_all(canonical_title_id)
        lines = []
        for src, row in all_["scores"].items():
            lines.append(format_ui_line(src, row["score"], row.get("vote_count")))
        return lines
