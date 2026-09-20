# Recommendation modules inventory (Phase A)

From `lords-frontend.py` (Lords family):

| MODULE_KEY | UI_LABEL | INPUT_SOURCE | Notes |
|---|---|---|---|
| similar | Похожее | `Вид.похожие()` genre→kind→year | on title page; excludes current via selection logic (verify Phase B) |
| home_films | Фильмы | home shelf filter kind=Фильм | deterministic shelf |
| home_series | Сериалы | kind=Сериал | |
| home_new | Новинки | /new/ ordering | |
| home_animation | Мультфильмы | kind=Мультфильм | |
| collections_* | Подборки / collection pages | `КОЛЛЕКЦИИ` contract | keys from collection registry |
| popular_pool | (internal) | rating-limited pool comment ~L4062 | weekly snapshot contract must be verified against snapshot files in Phase B |

## Gates not yet live-closed

Need Phase B title-page crawl:
* RECOMMENDATION_CURRENT_TITLE_COUNT
* DUPLICATE_IDS / duplicate shelves
* broken links / unplayable
* POPULAR_WEEKLY_CONTRACT_PASS against snapshot path + cadence metadata
