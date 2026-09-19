# CONTACTS AND DOCUMENTS REQUIRED — Zona Pass 4

Footer contact/legal columns are **omitted** when config is empty (no public placeholders).

Populate `/srv/lords/.frontend/footer-zona-01.json` (or `ZONA_FOOTER_CONFIG`) with **owner-approved** values only:

```json
{
  "schema": "zona-footer-config/1.0.0",
  "about_url": "",
  "contacts_url": "",
  "feedback_url": "",
  "rights_url": "",
  "privacy_url": "",
  "terms_url": "",
  "contact_email": ""
}
```

Rules:

* Do not invent email, Telegram, phone, legal entity, or document URLs.
* Do not copy `admin@zona.plus`.
* After real values exist: every link must return 2xx/3xx; then
  `FOOTER_CONTACT_GATE_PASS=1` and `FOOTER_DOCUMENTS_GATE_PASS=1`.

Current live state: `CONTACT_CONFIG_MISSING=1`, `FOOTER_CONTACT_GATE_PASS=0`.
