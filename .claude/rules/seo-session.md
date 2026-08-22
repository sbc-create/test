# SEO session operating rules

Binding rules for any session doing SEO work in this repository. `CLAUDE.md`
summarises them; this file is the full text.

## 1. Git

- All work happens on a branch. `main` is never committed to directly.
- Branches are named `claude/<topic>-<session-id>`.
- Every deliverable is committed. An artifact that exists only in a session
  transcript does not exist — a later session cannot see it.
- Commit messages state what changed and why, not which tool produced them.

## 2. Data integrity

- Every data artifact validates against a schema in `schemas/` before commit.
- Filenames follow `<schema-stem>.<label>.json` so the validator can match them
  (for example `seo-audit.example-com.json`).
- A schema is never loosened to make failing data pass. Either the data is
  wrong, or the schema change is a deliberate, tested decision.
- Adding a schema means adding a valid fixture and an invalid fixture. The test
  suite enforces that every schema has a valid fixture; a schema that rejects
  nothing is not a schema.

## 3. Evidence

- Every audit finding records how it was verified in its `evidence` field.
- Every numeric claim (volume, difficulty, position) records its `source`.
- Verification runs are recorded to `docs/verification/latest-run.md` via
  `scripts/record-evidence.sh` and committed. CI rejects a stale record.
- Never report a check as passed without having run it. If a check could not be
  run, say so explicitly and say why.

## 4. Scope

- Do not widen a change beyond what was asked. An audit task does not authorize
  rewriting site content.
- Do not add dependencies without pinning them in `requirements.txt`.
- Do not add a publishing target to `deploy.yml` without explicit instruction —
  publishing is outward-facing and needs a human decision.

## 5. Honesty constraints specific to SEO

SEO invites confident claims that cannot be supported. In this repository:

- Do not predict traffic or ranking outcomes from a set of changes.
- Do not state ranking-system behaviour with more certainty than public
  documentation supports.
- Do not present a third-party estimate as a measurement.
- Do not recommend anything that misrepresents page content to a crawler,
  including markup for content that is not on the page, text hidden from users,
  or pages served differently to crawlers than to people. These carry real
  penalty risk and are out of scope regardless of who asks.
- An empty findings list means "audited and clean". Never emit one for an audit
  that was not actually run.

## 6. Failing checks

- A failing test is a finding about the code, not an obstacle to route around.
- Never skip, delete, or `xfail` a test to reach green.
- If a check fails for a reason outside the current change, report it explicitly
  rather than silently ignoring it.
