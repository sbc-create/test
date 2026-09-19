# Rollback — Animedia visual finalization 2026-09-19

## Scope
Only `animedia.icu` (animedia-01) and `animedia.space` (animedia-02).

## Latest automatic backup
`/srv/lords/.frontend/.rollback/pre-closed-update-20260919T194140Z/`

Also available prior snapshots under the same directory (see DEPLOY*.log).

## Restore
1. Copy `lords-frontend.py` and `collection_contract.py` from the chosen rollback dir to `/srv/lords/.frontend/`.
2. Restore `template-manifest-animedia-01.json` and `template-manifest-animedia-02.json`.
3. Restart `nova-animedia-01` and `nova-animedia-02` (or re-run apply-nova with prior provenance tip / design 1.2.1).
4. Confirm marker and player overlay contract.

## Do not
Touch Lords/Zona, DNS, certificates, or indexing.
