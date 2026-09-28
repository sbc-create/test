# NEXT_REPAIR_PROMPT — after LORDS-THREE-DISTINCT-TEMPLATES-DEEP-AUDIT-01

Use this as the next `/goal` body. **Read-only audit is done.** This prompt is for repair + canary redeploy only.

```text
STAGE=LORDS-THREE-DISTINCT-TEMPLATES-REPAIR-01
MODE=FIX_FROM_AUDIT
BASE_AUDIT=artifacts/evidence/lords-three-distinct-deep-audit-2026-09-20/
BASE_DEPLOY_BUILD=20260920T193847Z-3c90aab-nova
BASE_ARTIFACT_SHA256=5dd817fe6ee12070609e16123cccc5cd3a6eace80fa895993227d2b3b2ad78cc
SITES=lords-02 (canary) → lords-01 → lords-03
```

## 1. P0
None open. If any P0 appears during repair, stop rollout and roll back current site only.

## 2. P1 (must fix before owner visual review)

### P1-A Load resilience (F-P1-01)
- Reproduce gently (rate-limited) on lords-02/03.
- Fix timeouts/backpressure/worker handling.
- Gate: 300 sequential GETs, HTTP_5XX_COUNT=0 per site.

### P1-B Distinctness (F-P1-02)
- Profile-specific H1 + intro + nav emphasis.
- Profile-specific collection sets (no shared anime tile on cinema).
- Advance passport cards: series episode-horizontal consistency; curated mosaic/editorial depth — not color-only.
- Gate: blind ATF identification ≥2/3; THREE_TEMPLATES_VISUALLY_DISTINCT=YES with evidence.

## 3. P2

1. Disjoint cinema Премьеры vs Новинки (F-P2-01)
2. Anime copy removal / profile copy binding (F-P2-02)
3. Rail occupancy fill policy (F-P2-03)
4. Broken posters on cinema series rail (F-P2-04)
5. Title overflow clamp (F-P2-05)
6. Unique collections per profile (F-P2-06)
7. Playwright player instance max=1 on real provider titles (F-P2-07)
8. Series film-rail truncation (F-P2-08)

## 4. Shared components
Follow `SHARED_COMPONENT_BACKLOG.md`. Keep one artifact + per-site manifests; do not invent a second binary that can overwrite tenants.

## 5. Per-profile specifics
- lords-01: `PER_SITE_BACKLOG_LORDS01.md`
- lords-02: `PER_SITE_BACKLOG_LORDS02.md`
- lords-03: `PER_SITE_BACKLOG_LORDS03.md`

## 6. Local tests
- Full Lords pytest
- Targeted: search, invalid page 404, filters, freshness disjoint shelves, recommendation contract, card overflow, design-id tests, domain isolation
- New tests for: adjacent-rail disjointness; profile collection copy; poster onerror fallback

## 7. Artifact
- Build from feature HEAD after fixes
- Prove data-design bindings: cinema-v2 / series-feed-v2 / curated-v2
- No `lords-sheet` fallback

## 8. Sequential canary deploy
1. lords-02 canary — stage, verified rollback, restart (owner if G-PRIV), smoke×2
2. lords-01 — only after lords-02 PASS
3. lords-03 — only after lords-01 PASS
- On failure: rollback **only** current site

## 9. Smoke×2
Same contract as deploy stage: home/catalog/search/filter/title/episode/invalid 404/nonexistent 404; design + build + artifact match; indexability unchanged.

## 10. Post-live visual matrix
- Re-capture home/catalog/title @1440 and @390 for all three
- Re-run occupancy on home rails
- Re-score distinctness
- Do **not** claim READY_FOR_OWNER_VISUAL_REVIEW until P1=0 and P2 closed or owner-accepted

## Hard limits
No DNS/robots/indexability/DB/paid/push/merge. No deep redesign beyond audit findings.
