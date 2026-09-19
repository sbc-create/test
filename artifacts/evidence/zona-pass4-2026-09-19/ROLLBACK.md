# ROLLBACK — Zona Pass 4

## Path

```text
/srv/lords/.frontend/.rollback/20260919T211402Z-zona-01-pass4
```

Contains: `lords-frontend.py`, `collection_contract.py`, `template-manifest-zona-01.json`, `meta.json`.

## Procedure

1. Acquire `/srv/lords/.frontend/.deploy.lock`.
2. Restore both Python artifacts and the zona-01 manifest from the rollback directory.
3. `systemctl restart nova-zona-01.service` via existing nsenter wrapper.
4. Confirm `/healthz` build/artifact match the rollback meta.
5. Re-run player golden sample and `/movies/` kind smoke.

Do not open indexing. Do not touch other domains.
