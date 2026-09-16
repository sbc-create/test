# Карта страниц направления Yummy

Карта **не написана здесь заново**. У направления Yummy она уже существует
в коде приложения — `src/site-blueprint/page-matrix.ts` — и является там
источником истины: по ней собираются canonical, robots, sitemap и JSON-LD.
Вторая карта, написанная рядом, разошлась бы с первой и стала бы ложью про
чужой репозиторий. Поэтому здесь — извлечение, снятое чтением, без единой
правки в репозитории приложения.

Строк в матрице: **52**, из них реализовано **45**, объявлено индексируемыми **12**.

## Чем эта карта отличается от карты Lords

Lords описывается манифестом профиля и собирается фабрикой, поэтому его
карта выводится из собранных документов. Yummy — приложение, которое
собирает страницы на запросе; его карта декларативна и живёт в коде
приложения. Разница не косметическая: карту Lords можно проверить, сверив
с готовым HTML, а карту Yummy — только запустив приложение. Оценка ключевых
страниц Yummy по рубрике поэтому и не приводится: без запуска приложения
она была бы утверждением о непроведённой проверке.

## Матрица

| Тип страницы | Адрес | Индексируемость | HTTP | Реализовано |
|---|---|---|---|---|
| homepage | `/` | indexable when substantive | 200 | да |
| catalog | `/catalog` | indexable when substantive | 200; page beyond last → 404 | да |
| catalog-pagination | `/catalog?page={n}` | indexable when page exists and has items | 200 or 404 | да |
| catalog-filter | `/catalog?genre=&type=&year=&status=&sort=` | always noindex; empty/nonsensical → 404 | 404 when empty or nonsensical; otherwise 200 noindex | да |
| ongoing | `/catalog/ongoing` | indexable when substantive | 200 | да |
| announcements | `/catalog/announcement` | indexable when substantive | 200 | да |
| schedule | `/catalog/schedule` | indexable when substantive | 200 | да |
| updates | `/catalog/anime-updates` | indexable when substantive | 200 | да |
| top | `/catalog/top` | indexable when substantive | 200 | да |
| random | `/catalog/random` | always noindex, never in sitemap | 307/308 to title or 404 | да |
| add-anime | `/catalog/add-anime` | always noindex | 200 | да |
| title | `/anime/{slug}` | indexable when real published API title | 200 or 404 | да |
| film | `/anime/{slug}` | same as title; no fictional season/episode URL | 200 or 404 | да |
| title-placeholder | `/anime/preview` | always noindex | 200 | да |
| season | `/anime/{slug}/season/{seasonNumber}` | S4 gated; isSeasonIndexable | 200 or 404 | да |
| episode | `/anime/{slug}/season/{seasonNumber}/episode/{episodeNumber}` | S4 gated; isEpisodeIndexable | 200/404/410/308 per episodeHttpPolicy | да |
| genre-landing | `/catalog/genre/{genreSlug}` | only allowlisted curated landings | not routed until allowlist | **нет** |
| year-landing | `/catalog/year/{year}` | only allowlisted years | not routed until allowlist | **нет** |
| type-landing | `/catalog/type/{typeSlug}` | only allowlisted types | not routed until allowlist | **нет** |
| news-list | `/posts` | indexable when original articles exist | 200 | да |
| news-article | `/posts/{slug}` | original article with author and dates | 200 | да |
| reviews-list | `/reviews` | noindex until original reviews | 200 | да |
| review | `/reviews/{slug}` | original review, real author, no fake aggregate | not routed | **нет** |
| videoblog-list | `/blogger` | always noindex stub | 200 | да |
| videoblog-item | `/blogger/{slug}` | gated original video page | not routed | **нет** |
| users | `/users` | always noindex | 200 | да |
| profile | `/users/{id}` | noindex until moderated substantive content | not routed | **нет** |
| login | `/login` | always noindex | 200 | да |
| register | `/register` | always noindex | 200 | да |
| password-reset | `/password-reset` | always noindex | not routed | **нет** |
| search | `/search` | always noindex | 200 | да |
| faq | `/pages/faq` | indexable when substantive | 200 | да |
| html-sitemap | `/sitemap` | indexable when substantive | 200 | да |
| about | `/about` | legal-gated | 200 | да |
| info | `/pages/info` | legal-gated | 200 | да |
| sources | `/pages/sources` | legal-gated | 200 | да |
| privacy | `/legal/privacy` | legal-gated | 200 | да |
| terms | `/legal/terms` | legal-gated | 200 | да |
| rightsholders | `/legal/rightsholders` | legal-gated | 200 | да |
| support | `/support` | legal-gated | 200 | да |
| admin-moderation | `/admin/moderation` | always noindex | 200 | да |
| dev-player | `/dev/player` | always noindex | 200 non-prod / 404 prod | да |
| dev-ui | `/dev/ui` | always noindex | 200 non-prod / 404 prod | да |
| api | `/api/*` | always noindex | 200 health/ready | да |
| xml-sitemap | `/sitemap.xml` | not a content page | 200 | да |
| catalog-item-redirect | `/catalog/item/{slug}` | redirect, not indexed | 308 | да |
| announcements-redirect | `/catalog/announcements` | redirect | 308 | да |
| news-redirect | `/news` | redirect | 308 | да |
| editorial-policy | `/pages/editorial` | legal-gated when published | 200 | да |
| corrections-policy | `/pages/corrections` | legal-gated when published | 200 | да |
| age-policy | `/pages/age-policy` | legal-gated when published | 200 | да |
| content-report | `/pages/report` | legal-gated when published | 200 | да |

## Строки, объявленные, но не реализованные

* `/catalog/genre/{genreSlug}` — genre-landing
* `/catalog/year/{year}` — year-landing
* `/catalog/type/{typeSlug}` — type-landing
* `/reviews/{slug}` — review
* `/blogger/{slug}` — videoblog-item
* `/users/{id}` — profile
* `/password-reset` — password-reset
