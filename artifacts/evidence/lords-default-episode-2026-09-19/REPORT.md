# REPORT — lords-default-episode-2026-09-19

## Verdict

`NEEDS_REPAIR` for live activation: artifact + honest manifest are on disk from this worktree, but `systemctl restart lords-nova-01.service` is `BLOCKED_ACCESS` (interactive authentication required). Process PID started 03:43Z still serves awaiting HTML.

Local/tests: PASS (87 related tests).

## Owner action to close live gap

```bash
systemctl restart lords-nova-01.service
# then verify:
curl -sS https://lordfilm47.space/title/pylnye-utesy/ | grep -E 'data-player data-state|video-player|Выберите серию'
```

Expect: `data-state="resolving"` (or ready after SDK), one `<video-player episode="1">`, no «Выберите серию».

Rollback: `/srv/lords/.frontend/.rollback/20260919T194936Z-lords-01-deferred`

## Race note

During deferred install, `wt-zona-finalization-01` overwrote shared `/srv/lords/.frontend/lords-frontend.py`. Restored this worktree digest `36ce7ead…` and backed up zona bytes under `.rollback/20260919T195100Z-lords-01-zona-overwrite-backup`.
