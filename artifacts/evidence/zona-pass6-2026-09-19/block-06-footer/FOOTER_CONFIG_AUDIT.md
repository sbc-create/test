# Block 06 — Footer config audit

## Visual
- Desktop: brand + Разделы + Каталог (fallback when contacts missing)
- Tablet ≥700: brand + 2 link columns
- Mobile ≤699: brand `grid-column:1/-1`, then two side-by-side link columns
- No empty Help/Docs columns
- Touch targets on footer links ≥44px min-height

## Data (owner-required — NOT invented)
Searched approved config only (`footer-zona-01.json`, example files, site profiles).
Zona profile has **no** populated contact/legal fields.

| Field | Status |
| --- | --- |
| LEGAL_OWNER_DISPLAY_NAME | MISSING |
| PUBLIC_CONTACT_EMAIL | MISSING |
| RIGHTSHOLDER_COMPLAINT_EMAIL | MISSING |
| PRIVACY_URL | MISSING |
| TERMS_URL | MISSING |
| RIGHTSHOLDER_URL | MISSING |

```text
FOOTER_VISUAL_PASS=YES
FOOTER_DATA_PASS=NO
CONTACT_DATA_GAP=1
LEGAL_CONFIG_INCOMPLETE=1
OWNER_ACTION_REQUIRED=YES
```

Populate `/srv/lords/.frontend/footer-zona-01.json` from
`automation/host/footer-zona-01.example.json` with owner-approved values only.
