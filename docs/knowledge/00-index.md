# SEO knowledge pack

Reference material an SEO session loads before doing any work in this
repository. Each document is self-contained; read the ones your task touches.

| Document | Read it when |
| --- | --- |
| [`technical-seo-checklist.md`](technical-seo-checklist.md) | Auditing crawlability, indexation, or site health |
| [`on-page-standards.md`](on-page-standards.md) | Writing or reviewing titles, descriptions, headings, structured data |
| [`keyword-research.md`](keyword-research.md) | Building or revising a keyword plan |
| [`reporting-conventions.md`](reporting-conventions.md) | Producing any deliverable that leaves this repository |

## How this pack relates to the schemas

The knowledge pack explains *why*; the schemas in [`../../schemas/`](../../schemas)
enforce *what*. Where a document states a limit (for example, a 60-character
title), the corresponding schema encodes it, and `scripts/validate_schemas.py`
enforces it. If the two ever disagree, the schema is authoritative and the
document is the bug.

## Ground rules for using this pack

- **Numbers need sources.** Any search volume, difficulty score, or ranking
  claim carries a `source` field. Unsourced numbers do not ship.
- **Findings need evidence.** Every audit finding records how it was verified.
  "Looks wrong" is not a finding.
- **Recommendations are testable.** Prefer "add a self-referencing canonical to
  these 11 URLs" over "improve canonicalization".
