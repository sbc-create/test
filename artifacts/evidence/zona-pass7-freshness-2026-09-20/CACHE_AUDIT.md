# Cache audit — Zona Pass7

## HTTP
- Live `Cache-Control: no-store` (no-store)
- `X-Robots-Tag: noindex, nofollow`
- Before repair: no `X-Catalog-Revision` on HTML
- After repair: `X-Catalog-Revision` + weak ETag `W/"cat-{revision}"` participate in cache identity

## Process memory
- Catalog/details loaded at process start into `Обработчик.данные`
- Pass7 adds mtime/revision reload without full deploy
- `Снимок` collection cache invalidated when catalog revision changes

## CDN / browser
- no-store on HTML responses — intermediaries must not reuse across revisions
- CACHE_POLICY_STATUS was WARN for undocumented TTL; documented as no-store + revision ETag

## Stale process
- Service PID started 2026-09-20T03:35:10Z after daily publish
- Artifact file on disk did NOT match zona manifest (lords-01 overwrite) — RUNTIME_DRIFT

## Snapshot digests
- catalog sha256: 99235834548f7acc4ac8bf116996fb3f15589063febb8cf5a07b0d220685cc8b
- details sha256: 87d65c9696b2f96644f1b56f8f1351b3d8dd1b9e74b1f469fed5f05443d0db20
- catalog revision: ecc664ad462bab47b51e8a9a151d5ec7
- catalog builtAt: 2026-09-20T03:16:30Z
- counts: catalog=53548 details=53548 (Pass6 baseline 53524; +24 from 2026-09-20 daily)
