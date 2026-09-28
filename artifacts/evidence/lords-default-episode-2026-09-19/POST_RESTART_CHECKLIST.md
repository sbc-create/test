# Post-restart checklist (owner / follow-up session)

Do not treat SSR `resolving` as success. Require terminal client `ready`.

- [ ] `systemctl is-active lords-nova-01.service` → active
- [ ] MainPID changed from pre-restart value
- [ ] ActiveEnterTimestamp newer than pre-restart
- [ ] Runtime build_id == `20260919T201932Z-63216915-nova`
- [ ] Runtime source_commit == FEATURE_HEAD `63216915c75ab75fe579363ef40d318774053350`
- [ ] Runtime artifact digest == deployed `4b541137ff4df012eb189e4ed5ce2125d47af7d205188e5e7554170954abb120`
- [ ] `/title/pylnye-utesy/` reaches terminal player `ready` (not SSR-only resolving)
- [ ] Default episode is S1E1 or first actually playable
- [ ] Prompt «Выберите серию» absent on generic hub with playable seasons
- [ ] Prompt «состояние неизвестно» absent
- [ ] Player iframe fills media viewport (≥98% width and height) at 1440/768/390
- [ ] Provider requests before click = 1
- [ ] Player instances ≤ 1
- [ ] unavailable / false-ready / false-failure = 0
- [ ] autoplay = 0
- [ ] Reload generic route still selects first playable
- [ ] Reload exact episode route preserves requested episode
- [ ] At least five additional generic series hubs pass
- [ ] One exact episode route keeps the concrete episode
- [ ] «Поцелуй меня дерзко» player viewport fill passes

Verdict after checks: PASS live or NEEDS_REPAIR. Do not close the task until live PASS.
