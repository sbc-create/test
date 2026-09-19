# Lords repair FINAL — 2026-09-19

## Verdict: **PASS**

Both remaining P1s closed with evidence:

1. Full SEO-bundle/snapshot contract (existing field names only), fail-closed on deploy/apply.
2. Prior 502 root cause proven as same-port single-worker restart without HTTP readiness; `/healthz` gate + regression tests prevent silent recurrence.

## Commits

| Hash | Role |
| --- | --- |
| `5fc2231` | fix(lords): SEO snapshot contract + deploy `/healthz` gate + SEO field gaps |
| `0673fe8` | chore(nova): provenance → `5fc2231` |
| `4fe8d1a` | fix(nova): apply imports SEO validator from worktree |

Prior P0 tip retained in history: `a0db875` / `ed8effd` / `810e826`.

## Live

| Field | Value |
| --- | --- |
| DEPLOY_PERFORMED | **1** — lords-02 only |
| DEPLOY_SCOPE | lords-02-only |
| DNS_MUTATIONS | **0** |
| INDEXING_OPENED | **0** |
| OTHER_DOMAINS_MUTATED | **0** |
| PUSH_PERFORMED | **0** |
| MERGE_PERFORMED | **0** |
| ROLLBACK_PATH | `/srv/lords/.frontend/.rollback/pre-closed-update-20260919T135218Z` |
| LIVE_BUILD_ID | `20260919T135218Z-5fc22310-nova` |
| LIVE_DIGEST | artifact `b08519b2f023329c…`; marker `Lords · 1.1.0 · 5fc22310` |
| CONTENT_SNAPSHOT_ID | `0394d6411fb76ce0…` (sha256 catalog+details) |

## P1 — SEO-bundle/snapshot contract

Canonical composition (no parallel format, no invented `catalog_snapshot_id`):

* Nova provenance: `source_commit`, `runtime_commit`, `build_id`, `artifact_sha256`, `profile`, `design_version`, `template_family`, `built_at`
* Release identity: `content_snapshot_id`, `content_count`
* Pages (`Meta` / uniqueness): `path`, `page_type`, `title`, `description`, `h1`, `canonical`, `indexable=false`
* `indexing_expected: "closed"` — preparing the bundle does **not** open indexing

Required `page_type` coverage (matrix + template-manifest section enum):
`home`, `catalog_index`, `movies_index`, `series_index`, `animation_index`, `collections_index`, `collection`, `title`, `season`, `episode`, `search`.

Fail-closed: empty / partial / stale / wrong-build / wrong `content_snapshot_id` rejected by `factory/lords/seo_snapshot.py`; deploy writes snapshot via `lords-seo-snapshot.py`; apply re-validates against live manifest + catalog digest.

Runtime SEO gaps closed so contract holds on live HTML:

* collection detail: `<h1>` + meta description
* search: meta description
* `/movies|series|animation/` self-canonical (no silent `/catalog/`)

Evidence: `raw/seo-snapshot-lords-02.json`, `raw/p1-close-verify.json` (11/11 pages 200, desc+h1, noindex).

## P1 — Root cause of prior 502 + guard

### Observed symptom

Ticket `P2-502` / earlier FINAL: ~20s global 502 under burst on `lordserial33.biz`. Timestamped nginx/journal capture of that window remains unread (`Permission denied` / no journal ACL) — duration claim is **not** journal-proven. Mechanism **is** proven.

### Failing code path

`automation/host/deploy-nova-lords.sh` (pre-fix):

1. `systemctl restart nova-lords-02.service` on **same** port nginx already proxies (`9111 → 9111` in apply logs).
2. `sleep 3` + `systemctl is-active` only — no HTTP probe.
3. Cold bind in `lords-frontend.py` happens **after** catalog/details/index load → port down while nginx still proxies → **global** 502 on all routes.

### Input / state that triggers it

Closed nova apply with `FORCE_INSTALL_FRONTEND=1` (or any restart) while nginx keeps upstream `127.0.0.1:9111`. Apply logs: `nginx 9111 → 9111`.

### Reproducing evidence (this deploy)

`raw/lords-02-apply-seo-healthz-2.log`:

```text
[nova] lords-02: /healthz ready after 14 attempt(s)
```

14 × 0.5s ≈ **7s** before listen. Previous `sleep 3` would have declared success while upstream was still dead → nginx 502. This is a deterministic lower bound on the restart gap; it does not require inventing the historical ~20s journal.

### Fix

After `systemctl restart`, poll `http://127.0.0.1:${PORT}/healthz` up to 40×; **abort** before nginx cutover claim if not ready. Apply also re-checks `/healthz` and SEO snapshot.

### Why it cannot silently recur

Deploy cannot return success on `is-active` alone. Regression tests lock the script pattern (`test_deploy_nova_lords_polls_healthz_before_nginx`).

### Live after fix

100 sequential + 20 parallel GETs → **0 × 5xx** (`raw/p1-close-verify.json`).

## Tests

* `tests/unit/test_lords_seo_snapshot.py` — missing / empty / partial / stale / wrong-build / valid + healthz/apply wiring
* `tests/unit/test_lords_repair_2026_09_19.py` — search desc, movies canonical, collection h1
* `tests/unit/test_nova_closed_provenance.py`, `test_lords_player_episode_avail.py`
* `git diff --check` on touched sources: clean
* 42 targeted tests green

## HTTP / load / indexing

| Check | Result |
| --- | --- |
| Main routes + title/season/episode/collection | 200 |
| seq 100 / par 20 | codes `[200]`, five_xx **0** |
| `X-Robots-Tag` / meta robots | `noindex, nofollow` |
| `robots.txt` | `Disallow: /` |
| ep7 sudmed | `data-state="unavailable"`, **0** `<video-player` |

## Remaining blockers

**none** (for the two P1s in scope). P2 progressive catalog / pixel parity unchanged and out of this close-out.

## Evidence paths

* `artifacts/evidence/lords-repair-2026-09-19/raw/lords-02-apply-seo-healthz-2.log`
* `artifacts/evidence/lords-repair-2026-09-19/raw/seo-snapshot-lords-02.json`
* `artifacts/evidence/lords-repair-2026-09-19/raw/p1-close-verify.json`
* `artifacts/evidence/lords-repair-2026-09-19/raw/ep7-sudmed.html`
