# OWNER_DATA_REQUIRED — Animedia

Visual/template geometry can close without these fields. Overall site close cannot.

## Contact / legal (`config/animedia-owner.json`)

Copy from `config/animedia-owner.example.json` and fill only real owner-approved values:

| Field | Required for | Notes |
| --- | --- | --- |
| `contact_email` | footer contact | Must contain `@`, no spaces |
| `telegram_url` | promo/footer | Only `https://t.me/…` or `https://telegram.me/…` |
| `privacy_url` | legal link | Absolute `https://` or site-relative `/…` path to real document |
| `terms_url` | legal link | Same as privacy |

Empty strings stay hidden. Invented contacts are forbidden.

## Schedule

Snapshot has no `next_episode_at` / episode air timestamps. Home schedule block stays hidden (`SCHEDULE_DATA_GAP=1`).
Provide source-backed release times before enabling «Сегодня выйдет».

## Relations / franchise

Details currently lack `relations` IDs. Franchise nav stays hidden until relation slugs exist in the catalog.
