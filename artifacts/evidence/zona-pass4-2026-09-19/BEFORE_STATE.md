# BEFORE_STATE — Zona Pass 4

## Preflight

| Field | Value |
| --- | --- |
| WORKTREE | `/home/claude/wt-zona-finalization-01` |
| BRANCH | `claude/zona-template-finalization-01` |
| START_HEAD | `140d2ca7657e36707179a06a2fd818fd1d1566c5` |
| EXPECTED_START_HEAD match | yes (exact) |
| LIVE_DOMAIN | `https://zonafilm.space` |
| live build | `20260919T172526Z-ac925674-nova` |
| live artifact | `8ebfdca925fcece60a3c321c305cb97142dff595ebb08f6e47bb504c2a6c6e63` |
| live source | `ac925674fb47aa9124ae7ef2a727e7af6d13e0f7` |
| template marker | `Zona · 1.2.0 · ac925674` |
| X-Robots-Tag | `noindex, nofollow` |
| catalog sha256 (prefix) | `14add2ef912f0fe706db40a35c56ad4a` |
| details sha256 (prefix) | `d8f5a25ae8c5b133dbfe7f606bf9c966` |
| catalog revision | `fe5e1331eb39f75852a5aa6f2bca132d` |
| catalog builtAt | `2026-09-19T03:23:34Z` |
| catalog count | 53524 |
| rollback (PASS3) | `/srv/lords/.frontend/.rollback/20260919T172526Z-zona-01-pass3` |

## Reference screenshots

Path given in brief (`live-template-qa/.../zona-ref-home-*.png`) is absent.
Using saved pack:

```text
artifacts/evidence/templates-zona-animedia-visual-parity-006/screenshots/reference/
  zona-reference-home-1440x900.png
  zona-reference-home-768x1024.png
  zona-reference-home-390x844.png
```

## Player contract (accepted, do not regress)

```text
ZONA_PLAYER_CAN_BE_CLOSED=YES
PLAYER_GOLDEN_RUNS=10/10
```

## Open gates from PASS3

```text
CONTACT_CONFIG_MISSING=1
FOOTER_GATE=FAIL
DESCRIPTION_COVERAGE_PERCENT=75.13
MISSING_DESCRIPTION_COUNT=13314
ZONA_TEMPLATE_CAN_BE_CLOSED=NO
ZONA_SEO_CONTENT_CAN_BE_CLOSED=NO
ZONA_OVERALL_CAN_BE_CLOSED=NO
```

## Live defects reproduced (2026-09-19)

See `raw/live-defects-before.json`.

1. `/series/?kind=Сериал&year=2026` → 1030 / 22 pages, alpha titles (`100…`, `102…`).
2. `/movies/` → starts `007`, `009`, `0,0 МГц`, mixed old years.
3. `/series/?kind=Фильм&year=2026` → still series (1030), no redirect.
4. `/movies/?kind=Сериал` → still films (31807).
5. `/movies/?kind=Фильм` duplicates `/movies/` state (no redirect).
6. Pagination/filter chips emit redundant `?kind=` on kind-routes.
7. `/new/` → exactly `Найдено 240 · страница 1 из 5`.
8. `/new/?year=2020` still reports 240 / 5 (cap after filter? actually still 240).
9. `/new/` mixes years via published_at order (2026 + older).
10. First `/new/` titles match `/collection/recently_added/`.
11. «Новые фильмы» = recently imported films including year 2020.
12. `current_season` = max catalog year (2026), copy says «самого свежего года…в каталоге».
13. `/new/` cards have no freshness reason label.
14. Filtered year pages keep generic H1 «Сериалы» / «Кино».
15. Footer placeholders present.

## Scope

Zona template/profile/projection + Zona tests only. No DNS/indexing/push/merge/other domains.
