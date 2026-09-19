# Post-restart checklist (owner / follow-up session)

Do not treat SSR `resolving` as success. Require terminal client `ready`.

- [ ] `systemctl is-active lords-nova-01.service` → active
- [ ] MainPID changed from pre-restart value
- [ ] ActiveEnterTimestamp newer than pre-restart
- [ ] Runtime build_id == `20260919T201028Z-ef17a709-nova`
- [ ] Runtime source_commit == FEATURE_HEAD `ef17a7094ad7f7663ecff29fb5338998d3defe03`
- [ ] Runtime artifact digest == deployed `36ce7eada5691b7ed949c0c301c45e1123dd6ddbf9c667701566ea37e883d1a6`
- [ ] `/title/pylnye-utesy/` reaches terminal player `ready` (not SSR-only resolving)
- [ ] Default episode is S1E1 or first actually playable
- [ ] Prompt «Выберите серию» absent on generic hub with playable seasons
- [ ] Provider requests before click = 1
- [ ] Player instances ≤ 1
- [ ] unavailable / false-ready / false-failure = 0
- [ ] autoplay = 0
- [ ] Reload generic route still selects first playable
- [ ] Reload exact episode route preserves requested episode
- [ ] At least five additional generic series hubs pass
- [ ] One exact episode route keeps the concrete episode

Verdict after checks: PASS live or NEEDS_REPAIR. Do not close the task until live PASS.
