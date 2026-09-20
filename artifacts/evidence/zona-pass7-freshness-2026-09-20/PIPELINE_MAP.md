# Pipeline map — Zona content freshness

```
Provider (cdnvideohub / lords-live)
    │  incremental (+ full every 6h inside lords-live)
    ▼
var/lords/.../catalog-cache/lords-01.json
    │  nova-daily-refresh.sh @ 03:30 UTC
    │  (+ details backfill, ratings)
    ▼
atomic publish → /srv/lords/.frontend/zona-01-catalog.json
                 /srv/lords/.frontend/zona-01-details.json
    │  restart nova-zona-01
    ▼
lords-frontend.py (in-memory Данные/Подробности)
    │  request-time shelf builders + collection_contract
    ▼
HTTPS zonafilm.space (Cache-Control: no-store)
```

**Not on Zona path:** `nova-catalog-refresh` (skips), `lords-content-refresh` (lords-01/02/03 static).

**Pass7 fixes:** honest shelf labels; snapshot mtime reload; `X-Catalog-Revision`;
zona-isolated frontend artifact path to stop lords-01 clobbering Zona.
