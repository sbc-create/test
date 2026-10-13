# Карта действий food-weekly, вариант C (own-week)

Проверено на commit `a613ec9` в Chromium: `python3 -m weekplan.qa --shots docs/screenshots/a613ec9 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| mobile:own:no_hscroll | PASS | `True` |
| mobile:home:no_hscroll | PASS | `True` |
| mobile:catalog:no_hscroll | PASS | `True` |
| mobile:week:no_hscroll | PASS | `True` |
| mobile:day:no_hscroll | PASS | `True` |
| mobile:shopping:no_hscroll | PASS | `True` |
| desktop:own:no_hscroll | PASS | `True` |
| desktop:home:no_hscroll | PASS | `True` |
| desktop:catalog:no_hscroll | PASS | `True` |
| desktop:week:no_hscroll | PASS | `True` |
| desktop:day:no_hscroll | PASS | `True` |
| desktop:shopping:no_hscroll | PASS | `True` |
| swap_url_has_zamena_or_s | PASS | `True` |
| swapped_marker | PASS | `1` |
| shopping_after_swap_url | PASS | `True` |
| shopping_rows_before_after | PASS | `[110, 110]` |
| shopping_changed_after_swap | PASS | `True` |
| bought_mark_persists | PASS | `True` |
| invalid_swap_warning | PASS | `True` |
| first_tab_skip | PASS | `True` |
| home_cta_opens_own_week | PASS | `True` |
| own_count_updates | PASS | `True` |
| own_week_shopping_listed | PASS | `True` |
| own_selection_kept | PASS | `True` |
| own_bought_persists | PASS | `True` |
| header_link_returns_to_own_week | PASS | `True` |
| seed_from_plan_fills_week | PASS | `True` |
| bad_people_400_alert | PASS | `True` |
| storage_namespace_own | PASS | `True` |
| nojs_week_dishes | PASS | `23` |
| nojs_swap_works | PASS | `True` |
| ширины 320/390/768/1440 × 38 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 20 страниц×ширин | PASS | 0 нарушений |
| обновление каталога food-daily (сеть между preview) — используется снимок | NOT_RUN | в варианте нет |
