# Post-restart final — blocked before restart

**VERDICT:** READY_FOR_OWNER_RESTART

Restart was not performed: `sudo -n systemctl restart` is denied by factory-guard
G-PRIV. No systemd bypass was attempted.

## Proven before stop

- Branch `cursor/lords-default-episode-01` at `bc09b7aa0214f33f5beac17d3d8f2947bfbf7c0f`
- Disk+manifest already staged: `20260919T201932Z-63216915-nova` / `4b541137ff4df012eb189e4ed5ce2125d47af7d205188e5e7554170954abb120`
- `SOURCE_ARTIFACT_DIGEST_MATCH=1`
- Runtime still stale: PID `3690779` / `20260913T2300Z-8ececc6c-nova`
- `ROLLBACK_VERIFIED=YES` for `/srv/lords/.frontend/.rollback/20260919T194936Z-lords-01-deferred` digest `06e991c3e558621c494e1150483b98eca67f2fcdc62ccaf0b165adf3e5b33432`
- Restore command recorded in `ROLLBACK_VERIFICATION.json`

## Exact owner command

```bash
sudo -n systemctl restart lords-nova-01.service
```

After that command, a follow-up session must run the live QA checklist in
`POST_RESTART_CHECKLIST.md` (playback progress, fill ratios, five real titles).
