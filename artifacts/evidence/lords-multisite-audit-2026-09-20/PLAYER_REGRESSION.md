# Player regression (Phase A)

* PLAYER_FIX_HEAD=`0a5fe648415d30d8f22bed016205c3cd878d7b3f` is ancestor of HEAD.
* Disk `/srv/lords/.frontend/lords-frontend.py` contains `data-player-layout-contract="full-bleed-v1"`.
* lords-01 runtime headers: build `20260919T224500Z-0a5fe648-nova`, artifact sha matches disk.
* lords-02/03 headers still advertise older manifest digests while executing shared disk (lineage drift).
* Repo fixture gate `playwright.lords-viewport.config.js` remains the release-blocking contract test.
* LIVE_REAL_PROVIDER_TITLES_TESTED=0 in this Phase A window (audit-only; full live player matrix in Phase B after fixes/deploys).
