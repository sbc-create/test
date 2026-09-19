# FOOTER_CONFIG_AUDIT — Zona Pass 4

## Live

* Build: `20260919T211402Z-c624bebc-nova`
* Placeholder texts (`Разделы появятся…`, `Документы не опубликованы`): **absent**
* Empty contact/document columns: **omitted** (fail-closed)
* Marker: `data-contact-config-missing="1"` present
* Visual columns on 1440: brand + sections only (help/docs hidden without config)

## Config contract

Typed path: `/srv/lords/.frontend/footer-zona-01.json` or `ZONA_FOOTER_CONFIG`.
Schema documented in `CONTACTS_AND_DOCUMENTS_REQUIRED.md`.

## Gates

| Gate | Value |
| --- | --- |
| FOOTER_VISUAL_GATE_PASS | 1 |
| FOOTER_CONFIG_CONTRACT_PASS | 1 |
| CONTACT_CONFIG_MISSING | 1 |
| FOOTER_CONTACT_GATE_PASS | 0 |
| FOOTER_DOCUMENTS_GATE_PASS | 0 |
| FOOTER_GATE_PASS | 0 |

Owner must supply real contacts/documents before overall PASS.
