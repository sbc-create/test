# ROLLBACK

1. Stop any ratings writer / release pilot lease.
2. Do **not** delete observations blindly if snapshot publish fails — keep last-good gateway.
3. Backup path: `/srv/site-factory/repo/var/ratings/backups/ratings.sqlite.20260919T224506Z.bak`.
4. Restore only onto verified need: copy backup over production DB after stopping writers.
5. Re-run integrity + foreign_key_check before reopening gateway.
6. Publish last-good snapshot if candidate publish failed mid-flight.

Restore drill evidence: `raw/RESTORE_DRILL.json` (isolated copy only).
