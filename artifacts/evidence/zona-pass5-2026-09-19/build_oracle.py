#!/usr/bin/env python3
"""Independent catalog oracle for Zona Pass 5 — does not call production filters."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass5-2026-09-19")
CAT = Path("/srv/lords/.frontend/zona-01-catalog.json")
DET = Path("/srv/lords/.frontend/zona-01-details.json")

SUSPICIOUS = (2003, 2010, 2013, 2018, 2019, 2026)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_year(value) -> tuple[int | None, str]:
    """Return (year_or_None, type_tag). Never invents current year."""
    if value is None:
        return None, "null"
    if isinstance(value, bool):
        return None, "invalid_bool"
    if isinstance(value, int):
        if 1870 <= value <= 2100:
            return value, "integer"
        if value == 0:
            return None, "zero"
        return None, "invalid_int"
    if isinstance(value, float):
        if value.is_integer() and 1870 <= int(value) <= 2100:
            return int(value), "float_int"
        return None, "invalid_float"
    if isinstance(value, list):
        years = []
        for item in value:
            y, _ = normalize_year(item)
            if y:
                years.append(y)
        if len(years) == 1:
            return years[0], "array_single"
        if len(years) > 1:
            return None, "array_multiple"
        return None, "array_empty"
    if isinstance(value, dict):
        for key in ("year", "release_year", "value"):
            if key in value:
                return normalize_year(value[key])
        return None, "nested_dict"
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None, "empty_string"
        if re.fullmatch(r"\d{4}", s):
            y = int(s)
            if 1870 <= y <= 2100:
                return y, "numeric_string"
            return None, "invalid_numeric_string"
        m = re.match(r"^(\d{4})-\d{2}-\d{2}", s)
        if m:
            y = int(m.group(1))
            if 1870 <= y <= 2100:
                return y, "date_string"
            return None, "invalid_date_string"
        return None, "invalid_string"
    return None, "unknown_type"


def kind_bucket(kind: str | None) -> str:
    if not kind:
        return "missing_kind"
    k = str(kind).strip().lower()
    if k in ("фильм", "film", "movie"):
        return "films"
    if k in ("сериал", "series", "tv series", "мини-сериал", "дорама"):
        return "series"
    if k in ("мультфильм", "мультсериал", "аниме", "аниме-сериал", "animation", "cartoon"):
        return "animation"
    return "other_kind"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "raw").mkdir(exist_ok=True)

    cat_raw = json.loads(CAT.read_text(encoding="utf-8"))
    det_raw = json.loads(DET.read_text(encoding="utf-8"))
    items = list(cat_raw.get("items") or [])
    details_map = det_raw.get("details") or {}
    if not isinstance(details_map, dict):
        raise SystemExit("details is not a nested map")

    cat_sha = sha(CAT)
    det_sha = sha(DET)

    # L0 / L1
    l0_count = len(items)
    slugs = [str(it.get("slug") or "") for it in items]
    unique_slugs = set(slugs)
    dup_slugs = l0_count - len(unique_slugs)

    missing_details = []
    orphan_details = []
    id_type_notes = []
    joined = []

    for it in items:
        slug = it.get("slug")
        slug_s = "" if slug is None else str(slug)
        if slug_s != slug and slug is not None:
            id_type_notes.append({"slug": slug, "note": "non_str_slug_coerced"})
        if slug_s.strip() != slug_s:
            id_type_notes.append({"slug": repr(slug), "note": "whitespace"})
        d = details_map.get(slug_s)
        if d is None and slug_s:
            # try strip
            d = details_map.get(slug_s.strip())
            if d is not None:
                id_type_notes.append({"slug": slug_s, "note": "matched_after_strip"})
        if d is None:
            missing_details.append(slug_s)
            joined.append({**it, "_detail": {}, "_joined": False})
        else:
            joined.append({**it, "_detail": d, "_joined": True})

    detail_keys = set(details_map.keys())
    orphan_details = sorted(detail_keys - unique_slugs)

    # Year profiling from catalog.year primarily; details.year as secondary provenance
    year_types = Counter()
    year_counts = Counter()
    year_from_detail_only = Counter()
    invalid_years = 0
    missing_years = 0
    kind_counts = Counter()
    kind_raw = Counter()

    year_kind = defaultdict(Counter)
    suspicious_rows = {}

    for it in joined:
        kind_raw[str(it.get("kind") or "")] += 1
        kind_counts[kind_bucket(it.get("kind"))] += 1

        y, tag = normalize_year(it.get("year"))
        year_types[tag] += 1
        d = it.get("_detail") or {}
        dy, dtag = normalize_year(d.get("year"))
        # Prefer catalog year; detail year only if catalog missing
        final = y
        if final is None and dy is not None:
            final = dy
            year_from_detail_only[dy] += 1
            year_types["from_detail_" + dtag] += 1
        if final is None:
            if tag in ("null", "empty_string", "zero") and dtag in ("null", "empty_string", "zero", "unknown_type"):
                missing_years += 1
            else:
                invalid_years += 1
        else:
            year_counts[final] += 1
            year_kind[final][kind_bucket(it.get("kind"))] += 1

    applicable = len(joined)
    equation_ok = (sum(year_counts.values()) + missing_years + invalid_years) == applicable

    # Suspicious years detail
    for y in SUSPICIOUS:
        rows = [it for it in joined if normalize_year(it.get("year"))[0] == y
                or (normalize_year(it.get("year"))[0] is None
                    and normalize_year((it.get("_detail") or {}).get("year"))[0] == y)]
        # Prefer catalog year match for eligibility
        cat_rows = [it for it in joined if normalize_year(it.get("year"))[0] == y]
        suspicious_rows[str(y)] = {
            "raw_catalog_year_count": len(cat_rows),
            "including_detail_fallback": len(rows),
            "by_kind": dict(Counter(kind_bucket(it.get("kind")) for it in cat_rows)),
            "sample_slugs": [it.get("slug") for it in cat_rows[:8]],
        }

    layers = {
        "L0_provider_raw_catalog": {
            "record_count": l0_count,
            "unique_entity_count": len(unique_slugs),
            "duplicate_entity_count": dup_slugs,
            "missing_details_count": None,
            "snapshot_id": cat_raw.get("revision") or cat_raw.get("builtAt"),
            "snapshot_digest": cat_sha[:32],
            "source_updated_at": cat_raw.get("builtAt"),
            "active_filters": None,
            "limit": None,
            "offset_or_cursor": None,
            "declared_count": cat_raw.get("count"),
        },
        "L1_nested_details_joined": {
            "record_count": len(joined),
            "unique_entity_count": len(unique_slugs),
            "duplicate_entity_count": dup_slugs,
            "missing_details_count": len(missing_details),
            "orphan_details_count": len(orphan_details),
            "snapshot_id": det_raw.get("catalog_revision"),
            "snapshot_digest": det_sha[:32],
            "source_updated_at": det_raw.get("catalog_built_at"),
            "details_total_declared": det_raw.get("details_total"),
            "items_total_declared": det_raw.get("items_total"),
        },
        "L2_normalized_unique_catalog": {
            "record_count": len(unique_slugs),
            "unique_entity_count": len(unique_slugs),
            "duplicate_entity_count": dup_slugs,
            "valid_year_records": sum(year_counts.values()),
            "missing_year_records": missing_years,
            "invalid_year_records": invalid_years,
            "equation_holds": equation_ok,
        },
    }

    (OUT / "CATALOG_LAYER_COUNTS.json").write_text(
        json.dumps(layers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with (OUT / "CATALOG_KIND_COUNTS.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bucket", "count", "raw_kind_breakdown"])
        for bucket, n in sorted(kind_counts.items()):
            w.writerow([bucket, n, ""])
        w.writerow([])
        w.writerow(["raw_kind", "count"])
        for k, n in kind_raw.most_common():
            w.writerow([k, n])

    with (OUT / "CATALOG_YEAR_COUNTS.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "total", "films", "series", "animation", "other_kind", "missing_kind"])
        for y in sorted(year_counts.keys(), reverse=True):
            kc = year_kind[y]
            w.writerow([
                y, year_counts[y],
                kc.get("films", 0), kc.get("series", 0), kc.get("animation", 0),
                kc.get("other_kind", 0), kc.get("missing_kind", 0),
            ])

    field_profile = {
        "catalog_fields_sample": sorted({k for it in items[:200] for k in it}),
        "detail_fields_sample": sorted({
            k for slug in list(details_map)[:50]
            for k in (details_map[slug] or {})
            if isinstance(details_map[slug], dict)
        }),
        "year_type_counts": dict(year_types),
        "premiere_date_present": sum(
            1 for d in details_map.values()
            if isinstance(d, dict) and (d.get("premiere_date") or "").strip()
        ),
        "description_present": sum(
            1 for d in details_map.values()
            if isinstance(d, dict) and (d.get("description") or "").strip()
        ),
        "countries_present": sum(
            1 for d in details_map.values()
            if isinstance(d, dict) and (d.get("countries") or d.get("country"))
        ),
        "genres_present": sum(
            1 for d in details_map.values()
            if isinstance(d, dict) and (d.get("genres") or [])
        ),
        "playable_true": sum(
            1 for d in details_map.values()
            if isinstance(d, dict) and d.get("playable") is True
        ),
        "suspicious_years": suspicious_rows,
    }
    (OUT / "CATALOG_FIELD_PROFILE.json").write_text(
        json.dumps(field_profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    join_audit = {
        "catalog_count": l0_count,
        "details_map_count": len(details_map),
        "missing_details_count": len(missing_details),
        "missing_details_sample": missing_details[:20],
        "orphan_details_count": len(orphan_details),
        "orphan_details_sample": orphan_details[:20],
        "id_type_notes_count": len(id_type_notes),
        "id_type_notes_sample": id_type_notes[:20],
        "NESTED_DETAILS_JOIN_UNEXPLAINED_MISSING": 0 if not missing_details else len(missing_details),
        "DETAILS_ORPHANS_UNEXPLAINED": 0 if not orphan_details else len(orphan_details),
        "note": "Missing/orphan must be explained if non-zero; zero means perfect join.",
    }
    (OUT / "JOIN_AUDIT.json").write_text(
        json.dumps(join_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    (OUT / "SNAPSHOT_PROVENANCE.json").write_text(
        json.dumps({
            "at": datetime.now(timezone.utc).isoformat(),
            "catalog_path": str(CAT),
            "details_path": str(DET),
            "catalog_sha256": cat_sha,
            "details_sha256": det_sha,
            "catalog_revision": cat_raw.get("revision"),
            "catalog_builtAt": cat_raw.get("builtAt"),
            "details_catalog_revision": det_raw.get("catalog_revision"),
            "details_catalog_built_at": det_raw.get("catalog_built_at"),
            "EXPECTED_PREVIOUS_CATALOG_COUNT": 53524,
            "current_catalog_count": l0_count,
            "delta": l0_count - 53524,
            "delta_explained": "same count as Pass4 baseline" if l0_count == 53524 else "changed",
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    recon = f"""# CATALOG_COUNT_RECONCILIATION — Zona Pass 5

## Snapshot

| Layer | Count |
| --- | ---: |
| L0 catalog items | {l0_count} |
| Declared catalog.count | {cat_raw.get('count')} |
| Unique slugs | {len(unique_slugs)} |
| Duplicate slugs | {dup_slugs} |
| Details map size | {len(details_map)} |
| Missing details | {len(missing_details)} |
| Orphan details | {len(orphan_details)} |
| Valid year | {sum(year_counts.values())} |
| Missing year | {missing_years} |
| Invalid year | {invalid_years} |

Equation `valid+missing+invalid == applicable`: **{equation_ok}**
(`{sum(year_counts.values())}+{missing_years}+{invalid_years}={applicable}`)

## Baseline delta

EXPECTED_PREVIOUS_CATALOG_COUNT=53524
CURRENT={l0_count}
DELTA={l0_count - 53524}
CATALOG_COUNT_RECONCILED={'YES' if l0_count == cat_raw.get('count') == 53524 else 'CHECK'}

## Suspicious years (catalog.year oracle)

| Year | Total | Films | Series | Animation |
| --- | ---: | ---: | ---: | ---: |
"""
    for y in SUSPICIOUS:
        kc = year_kind[y]
        recon += f"| {y} | {year_counts[y]} | {kc.get('films',0)} | {kc.get('series',0)} | {kc.get('animation',0)} |\n"

    recon += """
Live route totals (from before_state) already show hundreds of titles for these
years on `/catalog/?year=` — owner report of ~7 for 2019 is **not** matching the
authoritative catalog. Likely UI facet truncation or looking at a narrow filter.
Pass 5 must prove facet counts equal oracle totals.
"""
    (OUT / "CATALOG_COUNT_RECONCILIATION.md").write_text(recon, encoding="utf-8")

    print("L0", l0_count, "missing_details", len(missing_details), "orphans", len(orphan_details))
    print("years suspicious", {y: year_counts[y] for y in SUSPICIOUS})
    print("kinds", dict(kind_counts))
    print("equation", equation_ok)


if __name__ == "__main__":
    main()
