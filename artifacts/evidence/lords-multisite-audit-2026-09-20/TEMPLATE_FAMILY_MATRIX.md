# Template family matrix (Lords ×3)

All three live instances share one executable (`/srv/lords/.frontend/lords-frontend.py`)
and one CSS/JS template family name `lords`, but three **profiles**:

| SITE_KEY | DOMAIN | SYSTEMD_UNIT | PORT | PROFILE | Manifest source_commit | Manifest artifact_sha256 (header) | Disk artifact_sha256 | Header↔disk match |
|---|---|---|---|---|---|---|---|---|
| lords-01 | lordfilm47.space | lords-nova-01.service | 9110 | lords-general | 0a5fe648… | b9de6b62… | b9de6b62… | YES |
| lords-02 | lordserial33.biz | nova-lords-02.service | 9111 | lords-new | 5fc22310… | b08519b2… | b9de6b62… | NO |
| lords-03 | 1lordserials1.online | nova-lords-03.service | 9112 | lords-curated | a1691c56… | 9229879e… | b9de6b62… | NO |

## Visual isolation contract (must remain separate)

Per `СЕМЕЙСТВА_1_1["lords"]` + profile CSS branches in `lords-frontend.py`:

* template family name: `lords` (shared)
* visual tokens / header / footer / home composition / filter chrome / card geometry / detail / recommendation chrome: profile-scoped (`lords-general` / `lords-new` / `lords-curated`)

Phase B must not flatten these into one skin.

## Lineage finding

Processes were restarted (lords-02/03 today ~09:17–09:19 UTC) so they execute **current disk bytes**,
but response headers `X-Site-Factory-Artifact-Sha256` / `Build-Id` still mirror **per-site manifests**
that claim older digests for lords-02/03. Treat header digest as manifest claim, not proof of file bytes.
