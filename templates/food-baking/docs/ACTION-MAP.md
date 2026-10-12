# Карта действий food-baking, вариант B (oven-bench)

Проверено на commit `3f222ce` в Chromium: `python3 -m bakebook.qa --shots docs/screenshots/3f222ce --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| mobile:home:no_hscroll | PASS | `True` |
| mobile:catalog:no_hscroll | PASS | `True` |
| mobile:recipe:no_hscroll | PASS | `True` |
| mobile:recipe_pct:no_hscroll | PASS | `True` |
| mobile:dough:no_hscroll | PASS | `True` |
| mobile:pitfalls:no_hscroll | PASS | `True` |
| desktop:home:no_hscroll | PASS | `True` |
| desktop:catalog:no_hscroll | PASS | `True` |
| desktop:recipe:no_hscroll | PASS | `True` |
| desktop:recipe_pct:no_hscroll | PASS | `True` |
| desktop:dough:no_hscroll | PASS | `True` |
| desktop:pitfalls:no_hscroll | PASS | `True` |
| first_tab_skip | PASS | `True` |
| temp_jump_anchor | PASS | `True` |
| temp_row_opens_recipe_at_180 | PASS | `True` |
| timer_counts_down_from_source_80_min | PASS | `True` |
| timer_stops | PASS | `True` |
| steps_progress_text | PASS | `True` |
| marks_persist_after_reload | PASS | `True` |
| storage_keys_own_namespace | PASS | `True` |
| reset_clears_marks | PASS | `True` |
| bakers_pct_butter_50 | PASS | `True` |
| oven_strip_links_to_step | PASS | `True` |
| sort_hot_first | PASS | `True` |
| filter_zavarnoe_rows | PASS | `True` |
| filter_reset | PASS | `True` |
| filter_empty | PASS | `True` |
| search_case_spaces | PASS | `True` |
| search_pechene | PASS | `True` |
| real_404 | PASS | `True` |
| nojs_steps | PASS | `True` |
| nojs_pitfalls | PASS | `True` |
| nojs_timers_and_marks_hidden | PASS | `True` |
| ширины 320/390/768/1440 × 29 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 30 страниц×ширин | PASS | 0 нарушений |
| редактор (/redaktor/) — секрет B не создавался | NOT_RUN | в варианте нет |
