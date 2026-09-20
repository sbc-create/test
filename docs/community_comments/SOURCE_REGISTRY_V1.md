# COMMUNITY-COMMENTS-01 — Source Registry V1

**Stage:** COMMUNITY-COMMENTS-01  
**Checked at:** 2026-09-20  
**Owner authorization:** COMMUNITY-COMMENTS-01 owner goal dated 2026-09-20  
**Purpose:** language/structure analysis of public review/comment-like text  
**Storage default:** `STORAGE_MODE=DERIVED_ONLY`  
**Publication:** never republish; never insert into production comments

Machine-readable policy: [`SOURCE_POLICY_V1.json`](SOURCE_POLICY_V1.json)  
Network allowlist: `inventory/network-allowlist.yaml` (refs `community-comments-*`)

## Ethical hard rules

| Rule | Value |
| --- | --- |
| STORAGE_MODE | DERIVED_ONLY (default) |
| RAW_USER_IDENTITIES_STORED | 0 |
| Full external comment text in git | forbidden |
| CAPTCHA / stolen cookies / login bypass | forbidden |
| Translation padding for language quotas | forbidden |
| Production comments insert | forbidden |

DERIVED_ONLY fields kept: source URL, content digest, length, language, labels,
structural template, public title metadata. Usernames, avatars, profile URLs,
emails, phones, IPs, cookies, and social links are stripped before persistence.

## Internal label/source classes (foundation)

| id | class | status |
| --- | --- | --- |
| SRC-CC-HEURISTIC-V1 | internal heuristic labels | active |
| SRC-CC-MOD-QUEUE-V1 | moderator queue decisions | active |
| SRC-CC-PII-SCAN-V1 | PII scanner findings | active |
| SRC-CC-RESEARCH-OBS | research observations corpus | active (this registry) |

## Discovered external sources

| source_name | base_url | policy_class | notes |
| --- | --- | --- | --- |
| AniList Reviews GraphQL | https://graphql.anilist.co | ALLOWED_API | Primary review corpus. GET `?query=` → 404; POST read-only GraphQL required. |
| TVMaze Show API | https://api.tvmaze.com | ALLOWED_PUBLIC_READ_DERIVED_ONLY | Official GET API. Summaries are editorial, **not** user film comments — do not count as ACCEPTED_RESEARCH comments. |
| Open Library | https://openlibrary.org | ALLOWED_PUBLIC_READ_DERIVED_ONLY | Public metadata/ratings JSON. Star ratings without review body ≠ comment observation. |
| Wikipedia EN MediaWiki | https://en.wikipedia.org | REVIEW_REQUIRED | Talk/article excerpts are encyclopedic, not user film comments — prefer skip. |
| Wikipedia RU MediaWiki | https://ru.wikipedia.org | REVIEW_REQUIRED | Same as EN — prefer skip. |
| Wikidata | https://www.wikidata.org | ALLOWED_PUBLIC_READ_DERIVED_ONLY | Title/entity search only; no user comments. |
| Letterboxd | https://letterboxd.com | BLOCKED | Scraper/HTML harvest forbidden by owner goal. |
| Kinopoisk | https://www.kinopoisk.ru | BLOCKED | Scraper forbidden. |
| IMDb | https://www.imdb.com | BLOCKED | Scraper forbidden. |
| MyAnimeList HTML / unofficial scrapers | https://myanimelist.net | BLOCKED | No authorized scraper path. |
| Shikimori topics/comments | https://shikimori.io | REVIEW_REQUIRED | Factory has ratings GraphQL rights; **comment/topic** research not separately authorized in this stage. |

## Category redistribution (documented)

Desired mix assumed Letterboxd/IMDb/Kinopoisk-class film/series comment sources.
Those are **BLOCKED**. Only AniList yields high-volume policy-compliant review text.

| Desired category | Desired N | Resolution |
| --- | --- | --- |
| ANIME | 300 | Fill from AniList anime reviews (may exceed to absorb blocked categories). |
| INTERNATIONAL_FILMS | 200 | **Redistributed → ANIME** — no ALLOWED_API user-comment source. |
| INTERNATIONAL_SERIES | 150 | **Redistributed → ANIME** — TVMaze has no user comments. |
| DORAMA | 100 | Partial from AniList when country/tags indicate KR/JP/CN; remainder → ANIME. |
| TURKISH | 75 | **Redistributed → ANIME** — no ALLOWED source. |
| RUSSIAN_CIS | 75 | **Redistributed → ANIME** — Kinopoisk BLOCKED; Shikimori comments REVIEW_REQUIRED. |
| ANIMATION_FAMILY | 50 | Partial from AniList family/kids markers; else → ANIME. |
| DOCUMENTARY_OTHER | 50 | **Redistributed → ANIME** — no ALLOWED source. |

## Language redistribution

| Target | Resolution |
| --- | --- |
| RUSSIAN_MIN=500 | Unlikely from AniList-only; **do not translate** to pad. Record actual RU count. |
| ENGLISH_TARGET=300 | Expected primary from AniList. |
| OTHER=200 | Accept natural other languages; no padding. |

## Rate / concurrency (collector)

```text
CONCURRENCY_MAX=2
DEFAULT_REQUEST_RATE_RPS<=0.2
RETRIES_MAX=2
backoff=exponential
User-Agent=site-factory-comments-research/1.0 (+COMMUNITY-COMMENTS-01; research-derived-analysis)
```

## Provenance

All allowlist rows cite COMMUNITY-COMMENTS-01 owner goal dated 2026-09-20,
`purpose=research-derived-analysis`. Policy classes and per-source fields live in
`SOURCE_POLICY_V1.json`.
