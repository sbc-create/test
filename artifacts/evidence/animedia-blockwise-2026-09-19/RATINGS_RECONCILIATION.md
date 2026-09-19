# RATINGS_RECONCILIATION

## Layer counts (ICU catalog/details snapshot)

| Layer | AMD | Shikimori | КП | IMDb |
| --- | ---: | ---: | ---: | ---: |
| `ratings_by_source` keys | 0 | 4427 | 0 | 2259 |
| Legacy `kinopoisk_rating` / `imdb_rating` | — | — | 263 | 2622 |
| Gateway `оценки_по_источникам` rendered | **0** | **4427** | **263** | **2622** |
| Template `.rbs` (same function) | 0 | same | same | same |

SPACE details digest differs (`837c932b…` vs ICU `d40ad6a7…`) but KP legacy count also 263.

## AMD gap

```text
RATINGS_DB_AMD_COUNT=0
RATINGS_SNAPSHOT_AMD_ICU=0
RATINGS_SNAPSHOT_AMD_SPACE=0
RATINGS_GATEWAY_AMD_COUNT=0
RATINGS_RENDERED_AMD_COUNT=0
```

No AMD rows in authorized snapshot → do **not** scrape; leave gap. Label ready as `AnimeMedia` when rows appear.

## Presentation rules verified

- Source labels: `Shikimori` / `КП` / `IMDb` / `AnimeMedia`
- Missing ≠ `0` (`zero_rendered=0`)
- No cross-source vote summing
- User/vitrine ratings (`amd`) separated via `.rbs__l--own`
- Empty state text honest (or hidden when `пусто=False` on title)

## Cases

| Case | slug |
| --- | --- |
| Shikimori only | `22-7` |
| KP only | `bespoleznyy-dezhurnyy-i-shkolnica-so-slishkom-korotkoy-yubkoy` |
| IMDb only | `009-1` |
| multi | `horimiya-2` |
| none | `1999-otdel-protivodeystviya-okkultizmu` |
