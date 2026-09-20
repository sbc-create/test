# URL normalization & country route

## Seed ownership

`lordserial33.biz` → **lords-02** (`config/site-profiles/lords-02.json`, nginx `lords-02.conf`).

## Country pipeline (broken)

```
catalog details.countries label (e.g. «Великобритания»)
  → индекс: код = нормализовать(страна)  # keeps Cyrillic → «великобритания»
  → UI href: /country/{код}/               # Cyrillic path
  → route: МАРШРУТ_СТРАНЫ = ^/country/(?P<code>[a-z0-9_-]{1,40})/$
  → match FAIL → HTTP 404
```

Genres correctly use `нормализовать(транслит(жанр))` (latin). Countries do not.

Live proof (lords-02 catalog facets): **8/8** `/country/*/ ` links → 404.
Query form `/catalog/?country=<cyrillic_code>` → 200 (works).
Latin path `/country/velikobritaniya/` → 404 (not in index; index key is Cyrillic).

## Other normalization notes

* `/movies/`, `/series/`, `/animation/` clean kind routes → 200.
* Legacy `/schedule/`, `/genres/` → 308 to `/new/`, `/catalog/`.
* Legacy `/films/`, `/cartoons/` → **404** (no redirect to `/movies/`, `/animation/`).
* Trailing slash required on structured routes.
* `ё/е` folded in `нормализовать`.
