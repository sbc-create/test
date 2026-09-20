"""Evaluate existing DERIVED_ONLY 1000 research observations — no raw text restore."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def evaluate(corpus_summary: Path, quality: Path | None = None) -> dict:
    summary = json.loads(corpus_summary.read_text(encoding="utf-8"))
    labels = {}
    if quality and quality.exists():
        labels = json.loads(quality.read_text(encoding="utf-8"))
    return {
        "RESEARCH_CORPUS_BALANCED_FOR_ALL_SITE_VERTICALS": "NO",
        "accepted": summary.get("RESEARCH_OBSERVATIONS_ACCEPTED"),
        "unique_titles": summary.get("UNIQUE_TITLES"),
        "source_domains": summary.get("SOURCE_DOMAINS") or summary.get("UNIQUE_SOURCE_DOMAINS"),
        "category_skew": {
            "ANIME": summary.get("ANIME_OBSERVATIONS"),
            "DORAMA": summary.get("DORAMA_OBSERVATIONS"),
            "ANIMATION": summary.get("ANIMATION_OBSERVATIONS"),
            "FILM": summary.get("FILM_OBSERVATIONS"),
            "SERIES": summary.get("SERIES_OBSERVATIONS"),
        },
        "language_skew": {
            "ru": summary.get("RUSSIAN_OBSERVATIONS"),
            "en": summary.get("ENGLISH_OBSERVATIONS"),
            "other": summary.get("OTHER_LANGUAGE_OBSERVATIONS"),
        },
        "label_distribution_from_stage01": labels.get("sentiment") or labels.get("quality") or {},
        "spoiler_policy_note": "Spoilers collapse, never auto-delete",
        "spam_policy_note": "High-confidence spam → hide; low confidence → hold",
        "toxicity_policy_note": "Criticism allowed; hate/threat force-hide",
        "false_positive_risk": "MEDIUM — AniList-skewed English reviews; not representative of RU/film/series",
        "bias_note": "ANIME/DORAMA over-represented; do not claim all verticals covered",
        "USER_COMMENT_TEXT_IN_EVIDENCE": 0,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = evaluate(
        root / "artifacts/evidence/community-comments-01/CORPUS_SUMMARY.json",
        root / "artifacts/evidence/community-comments-01/06-labels/LABEL_DISTRIBUTION.json",
    )
    dest = root / "artifacts/evidence/community-comments-02/06-corpus-eval"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "CORPUS_EVAL.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
