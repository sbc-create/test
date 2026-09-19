# OWNER_CONTACTS_LEGAL_REQUIRED — Zona Pass 5

Footer contact and legal links are omitted until owner-approved values exist.

Populate `/srv/lords/.frontend/footer-zona-01.json` (example:
`automation/host/footer-zona-01.example.json`):

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

Do not invent email, Telegram, phone, legal entity, or document URLs.

Until filled:

```text
FOOTER_CONTACT_GATE_PASS=NO
FOOTER_DOCUMENTS_GATE_PASS=NO
OVERALL_VERDICT=NEEDS_OWNER_CONFIG
```
