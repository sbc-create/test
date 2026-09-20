# Owner summary — LORDS-MULTISITE-AUDIT-01 Phase A

## Sites (exactly 3)

1. lords-01 / lordfilm47.space / lords-nova-01.service:9110 / lords-general
2. lords-02 / lordserial33.biz / nova-lords-02.service:9111 / lords-new  ← seed domain
3. lords-03 / 1lordserials1.online / nova-lords-03.service:9112 / lords-curated

## Top findings

1. **Every country filter chip is a dead link** (8/8 on lords-02 catalog). Shared bug: Cyrillic country codes vs ASCII-only route regex.
2. **No live 5xx** in this audit window (132 routes). Seed series+year=2016 returns 200. Historical 502 not reproduced; logs not readable without adm.
3. **Comedy count 14913 is correct** for lords-02 (matches oracle).
4. **Manifest/header digest drift** on lords-02/03 vs shared disk `b9de6b62…` (player contract is on disk).
5. Compact filters / card geometry / recommendation weekly contract → Phase B.

## Do not

* Blind restart to “fix” 502
* Change nginx without approval
* One CSS skin for all three profiles
