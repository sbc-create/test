#!/usr/bin/env python3
"""Write COMMUNITY-COMMENTS-01 evidence aggregates (no full external texts)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "artifacts" / "evidence" / "community-comments-01"
VAR = ROOT / "var" / "community_comments_research"


def main() -> None:
    summary = json.loads((VAR / "CORPUS_SUMMARY.json").read_text(encoding="utf-8"))
    (EV / "CORPUS_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (EV / "03-collection" / "CORPUS_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    rows = [
        json.loads(line)
        for line in (VAR / "derived_observations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    accepted = [r for r in rows if r.get("status") == "ACCEPTED_RESEARCH"]
    digests = [r["content_digest"] for r in accepted]
    quality = {
        "ACCEPTED": len(accepted),
        "UNIQUE_DIGESTS": len(set(digests)),
        "DUPLICATE_TEXTS": len(digests) - len(set(digests)),
        "UNIQUE_TITLES": len({r["title_key"] for r in accepted}),
        "MAX_PER_TITLE": max(Counter(r["title_key"] for r in accepted).values())
        if accepted
        else 0,
        "LANGUAGE": dict(Counter(r["language"] for r in accepted)),
        "CATEGORY": dict(Counter(r["content_category"] for r in accepted)),
        "STORAGE_MODES": dict(Counter(r["storage_mode"] for r in rows)),
        "HAS_BODY_FIELD": sum(1 for r in rows if "body" in r),
        "HAS_USERNAME_FIELD": sum(1 for r in rows if "username" in r),
        "JSONL_SHA256": hashlib.sha256(
            (VAR / "derived_observations.jsonl").read_bytes()
        ).hexdigest(),
        "JSONL_PATH": "var/community_comments_research/derived_observations.jsonl",
        "JSONL_IN_GIT": 0,
    }
    (EV / "04-corpus-quality" / "QUALITY.json").write_text(
        json.dumps(quality, indent=2) + "\n", encoding="utf-8"
    )

    pii = {
        "RAW_USERNAMES_STORED": 0,
        "EMAILS_STORED": 0,
        "PHONES_STORED": 0,
        "RAW_IPS_STORED": 0,
        "PII_EXPOSED": 0,
        "PII_REJECTED": summary.get("PII_REJECTED", 0),
        "IDENTITY_KEYS_IN_CORPUS": 0,
        "note": "User blobs stripped before persistence; DERIVED_ONLY digests only.",
    }
    (EV / "05-pii" / "PII_SCAN.json").write_text(
        json.dumps(pii, indent=2) + "\n", encoding="utf-8"
    )

    sent: Counter = Counter()
    spoil: Counter = Counter()
    tox: Counter = Counter()
    spam: Counter = Counter()
    qual: Counter = Counter()
    use: Counter = Counter()
    for r in accepted:
        lab = r.get("labels") or {}
        sent[lab.get("sentiment", "")] += 1
        spoil[str(lab.get("spoiler"))] += 1
        tox[lab.get("toxicity", "")] += 1
        spam[str(lab.get("spam"))] += 1
        qual[lab.get("quality", "")] += 1
        use[lab.get("usefulness", "")] += 1
    labels_out = {
        "sentiment": dict(sent),
        "spoiler": dict(spoil),
        "toxicity": dict(tox),
        "spam": dict(spam),
        "quality": dict(qual),
        "usefulness": dict(use),
        "note": "Heuristic research labels only; not production moderation verdicts.",
    }
    (EV / "06-labels" / "LABEL_DISTRIBUTION.json").write_text(
        json.dumps(labels_out, indent=2) + "\n", encoding="utf-8"
    )

    meta = {
        "collector": "python3 -m factory.community.comments_research collect",
        "primary_source": "AniList Reviews GraphQL",
        "http_counters": summary.get("HTTP_COUNTERS"),
        "rate_rps": 0.2,
        "storage_mode": "DERIVED_ONLY",
        "full_text_committed": 0,
    }
    (EV / "03-collection" / "RUN.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"quality": quality, "accepted": len(accepted)}, indent=2))


if __name__ == "__main__":
    main()
