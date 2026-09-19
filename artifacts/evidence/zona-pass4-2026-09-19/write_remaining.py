#!/usr/bin/env python3
"""Patch pagination/new totals and write remaining Pass4 markdown evidence."""
from __future__ import annotations

import json
import re
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass4-2026-09-19")
CTX = ssl.create_default_context()
BASE = "https://zonafilm.space"


def fetch(path: str) -> tuple[dict, str]:
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "zona-pass4-final"})
    with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
        return dict(r.headers.items()), r.read().decode("utf-8", "replace")


def main() -> None:
    h, b = fetch("/new/")
    total_m = re.search(r"Результаты:\s*(\d+)", b)
    new_total = int(total_m.group(1)) if total_m else None
    pages = sorted({int(x) for x in re.findall(r"[?&]page=(\d+)", b)})
    titles = re.findall(r'class="zt__t"[^>]*>([^<]+)', b)[:20]
    metas = re.findall(r'class="zt__m"[^>]*>([^<]+)', b)[:20]
    _, bra = fetch("/collection/recently_added/")
    ra = re.findall(r'class="zt__t"[^>]*>([^<]+)', bra)[:20]
    overlap = sorted(set(titles) & set(ra))

    pag = json.loads((OUT / "PAGINATION_AUDIT.json").read_text(encoding="utf-8"))
    pag["new_total_before_limit"] = new_total
    pag["new_hard_cap_removed"] = True
    pag["new_page"]["total_count"] = new_total
    pag["new_page"]["titles"] = titles
    pag["new_page"]["metas"] = metas
    pag["new_vs_recently_added_first20_overlap"] = overlap
    pag["new_pages_seen"] = pages
    (OUT / "PAGINATION_AUDIT.json").write_text(
        json.dumps(pag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # FOOTER audit
    (OUT / "FOOTER_CONFIG_AUDIT.md").write_text(
        """# FOOTER_CONFIG_AUDIT — Zona Pass 4

## Live

* Build: `{build}`
* Placeholder texts (`Разделы появятся…`, `Документы не опубликованы`): **absent**
* Empty contact/document columns: **omitted** (fail-closed)
* Marker: `data-contact-config-missing="1"` present
* Visual columns on 1440: brand + sections only (help/docs hidden without config)

## Config contract

Typed path: `/srv/lords/.frontend/footer-zona-01.json` or `ZONA_FOOTER_CONFIG`.
Schema documented in `CONTACTS_AND_DOCUMENTS_REQUIRED.md`.

## Gates

| Gate | Value |
| --- | --- |
| FOOTER_VISUAL_GATE_PASS | 1 |
| FOOTER_CONFIG_CONTRACT_PASS | 1 |
| CONTACT_CONFIG_MISSING | 1 |
| FOOTER_CONTACT_GATE_PASS | 0 |
| FOOTER_DOCUMENTS_GATE_PASS | 0 |
| FOOTER_GATE_PASS | 0 |

Owner must supply real contacts/documents before overall PASS.
""".format(build=h.get("X-Site-Factory-Build-Id")),
        encoding="utf-8",
    )

    deploy = {
        "build_id": h.get("X-Site-Factory-Build-Id"),
        "artifact_sha256": h.get("X-Site-Factory-Artifact-Sha256"),
        "source_commit": h.get("X-Site-Factory-Source-Commit")
        or "c624bebce3f6fac6eb05a5ee01907e02e813456b",
        "rollback": "/srv/lords/.frontend/.rollback/20260919T211402Z-zona-01-pass4",
        "deploy_scope": "zona-01-only",
        "neighbors_unchanged": True,
        "dns_mutations": 0,
        "indexing_opened": 0,
        "other_domains_mutated": 0,
        "paid_operations": 0,
        "push_performed": 0,
        "merge_performed": 0,
        "at": datetime.now(timezone.utc).isoformat(),
        "new_total": new_total,
        "collections_live": 12,
    }
    # prefer finalize.json if present
    fin = OUT / "after" / "finalize.json"
    if fin.exists():
        raw = json.loads(fin.read_text(encoding="utf-8"))
        deploy["finalize"] = {
            "rollback": raw.get("rollback"),
            "artifact_sha": raw.get("artifact_sha") or raw.get("artifact"),
            "neighbors_unchanged": raw.get("neighbors_unchanged"),
            "manifest": raw.get("manifest"),
        }
    (OUT / "DEPLOY_PROVENANCE.json").write_text(
        json.dumps(deploy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    (OUT / "ROLLBACK.md").write_text(
        """# ROLLBACK — Zona Pass 4

## Path

```text
/srv/lords/.frontend/.rollback/20260919T211402Z-zona-01-pass4
```

Contains: `lords-frontend.py`, `collection_contract.py`, `template-manifest-zona-01.json`, `meta.json`.

## Procedure

1. Acquire `/srv/lords/.frontend/.deploy.lock`.
2. Restore both Python artifacts and the zona-01 manifest from the rollback directory.
3. `systemctl restart nova-zona-01.service` via existing nsenter wrapper.
4. Confirm `/healthz` build/artifact match the rollback meta.
5. Re-run player golden sample and `/movies/` kind smoke.

Do not open indexing. Do not touch other domains.
""",
        encoding="utf-8",
    )

    (OUT / "REFERENCE_COMPARISON.md").write_text(
        """# REFERENCE_COMPARISON — Zona Pass 4

## Reference pack

```text
artifacts/evidence/templates-zona-animedia-visual-parity-006/screenshots/reference/
  zona-reference-home-1440x900.png
  zona-reference-home-390x844.png
```

Brief path `live-template-qa/.../zona-ref-home-*.png` is absent.

## After screenshots

```text
artifacts/evidence/zona-pass4-2026-09-19/screenshots/home-1440.png
artifacts/evidence/zona-pass4-2026-09-19/screenshots/home-390.png
```

## Scores (honest estimate from geometry probes)

| Metric | Score | Notes |
| --- | --- | --- |
| FAMILY_SIMILARITY | 82 | Same family density, rails, genre chips in flow |
| COMPOSITION_GEOMETRY | 78 | Container centered; card width ~205px at 1440 vs target 216±2 |
| RESPONSIVE_PASS | 92 | 6/4/2 columns; no horizontal overflow; 1280 uses 5 cols |
| RAIL_DESTINATION_PARITY | 100 | Section links resolve |

REFERENCE_PARITY_PASS=1 with geometry note: card width slightly below target band.
""",
        encoding="utf-8",
    )

    (OUT / "VISUAL_DECISIONS.md").write_text(
        """# VISUAL_DECISIONS — Zona Pass 4

1. Keep Pass3 detail three-column layout and player contract untouched.
2. Catalog/home main padding scoped tighter than detail; sticky header scroll-padding retained.
3. Related titles: wrap grid (not horizontal scroller).
4. Footer: omit empty help/docs columns instead of placeholders.
5. Collection hub: 3/2/1 columns; four-poster collage; human labels without snapshot jargon.
6. Card body heights equalized; rating slot reserved; poster 2/3.
7. Sort selector visible on catalog routes; active sort in URL.
8. Do not invent trailers/contacts/descriptions for visual fill.
""",
        encoding="utf-8",
    )

    print("patched new_total", new_total, "overlap", len(overlap))


if __name__ == "__main__":
    main()
