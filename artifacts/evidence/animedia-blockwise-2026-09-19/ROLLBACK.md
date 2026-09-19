# ROLLBACK — home deploy after BLOCK_01–04

| Field | Value |
| --- | --- |
| Deploy build | `20260919T222328Z-18cd7d7e-nova` |
| Runtime tip | `18cd7d7ecfd829b17917abcd627111f0147f8b79` |
| Artifact SHA256 | `39f91efcefc8a7d933db2e474477854624b724b407bc2865bf2245539dd2bf93` |
| Scope | animedia-01 + animedia-02 only |

## Restore

```bash
FACTORY_OWNER_ROOT_MANDATE=SITE_FACTORY_ROOT_20260909 \
APPLY_SITES=animedia-01,animedia-02 FORCE_INSTALL_FRONTEND=1 \
# pin ANIMEDIA_COMMIT to previous tip 1cc115824ce684fc47f005edfaa393bd61037f94 then:
python3 automation/host/apply-nova-closed-update.py
```

Do not mutate Lords/Zona. Prefer the same apply-nova path used for the forward deploy.
