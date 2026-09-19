# SORTING_CONTRACT — Zona Pass 5

Unchanged from Pass4 semantics with densify release:

| Route | Default sort | Tie-break |
| --- | --- | --- |
| `/new/` | premiere `_premiere_date` DESC | title, slug |
| `/movies/`, `/series/`, `/animation/`, `/catalog/` | release freshness (`_premiere_date`, year) DESC | title, slug |
| `sort=recently_added` | `published_at` DESC | title, slug |
| `sort=rating` | rating, votes | title, slug |
| `sort=title` | normalized title ASC | slug |

Year filter uses catalog `year` only (never ingest date).
