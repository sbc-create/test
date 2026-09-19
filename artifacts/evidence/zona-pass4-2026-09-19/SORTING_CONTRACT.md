# SORTING CONTRACT — Zona Pass 4

| Route / mode | Primary key | NULLS | Tie-break |
| --- | --- | --- | --- |
| `/new/` (`newest`) | activity: `_premiere_date` else `published_at` DESC | missing last | title ASC, slug ASC |
| `/movies|/series|/animation|/catalog` default `newest` | `_premiere_date` DESC, then `year` DESC | missing last | title, slug |
| `recently_added` | `published_at` DESC | missing last | title, slug |
| `rating` | rating DESC, votes soft-prefer | unrated last | title, slug |
| `title` | normalized title ASC | — | slug ASC |

URL param: `?sort=newest|recently_added|rating|title` (alias `date`→`newest`).

Selector labels (RU): Сначала новые / Недавно добавленные / По рейтингу / По названию.
