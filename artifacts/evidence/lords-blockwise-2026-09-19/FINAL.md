# FINAL — lords-blockwise-2026-09-19

**VERDICT:** READY_FOR_OWNER_RESTART

**BLOCKER:** FACTORY_GUARD_G_PRIV

Overnight blockwise work completed Blocks 00–03 locally. Critical prior
fixes (default episode + player viewport) remain staged on disk as
`20260919T201932Z-63216915-nova` / `4b541137ff4df012eb189e4ed5ce2125d47af7d205188e5e7554170954abb120`. Blocks 01–02 code exist only
in git HEAD `a7b0bb06f000ce55a90e80a3fbc880db76534f58` and are **not** yet in the staged production artifact.

Runtime still serves `3690779` / `20260913T2300Z-8ececc6c-nova`.

## Owner command

```bash
sudo -n systemctl restart lords-nova-01.service
```

After restart, live-verify episode+player from staged artifact. Then continue
Blocks 04–11 and rebuild a single clean artifact from the latest feature HEAD
before a second authorized restart.
