# Overnight visual repair — 2026-09-19

## Goal

Bring four closed storefronts closer to their originals (visual + functional),
without DNS/indexing/access/deploy changes. Local commits only.

## Domains

| Domain | Site id | Live profile (preflight) | Live source_commit |
| --- | --- | --- | --- |
| https://lordserial33.biz/ | lords-02 | lords-new | 479f7d2de1e4… |
| https://animedia.space/ | animedia-02 | animedia-general | b023bd50cced… |
| https://animedia.icu/ | animedia-01 | animedia-general | b023bd50cced… |
| https://zonafilm.space/ | zona-01 | zona-general | a10e68b2… (runtime 99ec7829…) |

## References

- Animedia: https://amd.online/
- Zona: https://w140.zona.plus/
- Lords: in-repo Lords UI contract / reference packs (read-only)

## Worktree preflight

- Path: `/home/claude/wt-lords-integration-canary-01`
- Branch: `cursor/lords-integration-canary-01`
- Starting HEAD: `b1522a5201dfd7e9168009c87b3ec5ff62242679`
- Source of changes: this worktree only (not `/srv/site-factory/repo`)
- Unrelated dirty paths left untouched: `seo_operator/*`, prior `live-template-qa` artifacts

## Hard constraints (honoured)

- No new worktrees; no foreign worktrees
- No DNS / indexing / Basic Auth changes
- No merge, push, force-push, reset, stash
- No production deploy / nginx / systemd
- No invented posters, ratings, providers, stream URLs
- No fake player iframes
- No edits to contracts/visual-scoring, reference packs, structure_order, type_h3

## Layout

- `audit/` — route/search/filter/robots JSON from live probes
- `html/` — saved page snippets
- `screenshots/` — Playwright captures when available
- `raw/` — crawl/metrics dumps
- `REPORT.md` — final overnight report

## Phases

1. Preflight (this file)
2. Full live audit
3. Visual / responsive checks
4. P1 fixes (Animedia → Zona → Lords regression guard)
5. Player contract preservation (Lords)
6. Targeted tests + local commits
7. REPORT.md
