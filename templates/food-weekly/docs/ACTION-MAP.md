# Карта действий food-weekly, вариант B (agenda-trips)

Проверено на commit `96c0c98` в Chromium: `python3 -m weekplan.qa --shots docs/screenshots/96c0c98 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| mobile:home:no_hscroll | PASS | `True` |
| mobile:catalog:no_hscroll | PASS | `True` |
| mobile:week:no_hscroll | PASS | `True` |
| mobile:day:no_hscroll | PASS | `True` |
| mobile:shopping:no_hscroll | PASS | `True` |
| desktop:home:no_hscroll | PASS | `True` |
| desktop:catalog:no_hscroll | PASS | `True` |
| desktop:week:no_hscroll | PASS | `True` |
| desktop:day:no_hscroll | PASS | `True` |
| desktop:shopping:no_hscroll | PASS | `True` |
| first_tab_skip | PASS | `True` |
| home_table_opens_week | PASS | `True` |
| weeknav_jumps_to_thursday | PASS | `True` |
| swap_in_url | PASS | `True` |
| swapped_marker | PASS | `True` |
| trip_link_keeps_swaps_and_anchor | PASS | `True` |
| trip1_changed_after_swap | PASS | `True` |
| trip_counter_counts_left | PASS | `True` |
| bought_marks_persist_per_trip | PASS | `True` |
| storage_keys_own_namespace | PASS | `True` |
| whole_list_expands | PASS | `True` |
| invalid_swap_warning | PASS | `True` |
| real_404 | PASS | `True` |
| nojs_week_dishes | PASS | `True` |
| nojs_swap_works | PASS | `True` |
| nojs_trips_listed | PASS | `True` |
| ширины 320/390/768/1440 × 36 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 20 страниц×ширин | PASS | 0 нарушений |
| обновление каталога food-daily (сеть между preview) — используется снимок | NOT_RUN | в варианте нет |
