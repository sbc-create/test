# ROLLBACK

Install via `lords-nova-canary.py` writes a point under:

```text
/srv/lords/.frontend/.rollback/<UTC>-lords-01/
```

Rollback:

```bash
python3 automation/host/lords-nova-canary.py rollback \
  --site lords-01 \
  --point /srv/lords/.frontend/.rollback/<POINT>-lords-01 \
  --record artifacts/evidence/lords-default-episode-2026-09-19/rollback-record.json
```

Restores previous `lords-frontend.py` + `template-manifest.json` and restarts `lords-nova-01.service` only.

Deferred install point (files on disk, restart pending):

```text
/srv/lords/.frontend/.rollback/20260919T194936Z-lords-01-deferred
```

Zona race backup (if needed):

```text
/srv/lords/.frontend/.rollback/20260919T195100Z-lords-01-zona-overwrite-backup
```
