# Карта действий food-baking, вариант C (bake-batch)

Проверено на commit `ff617d0` в Chromium: `python3 -m bakebook.qa --shots docs/screenshots/ff617d0 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| mobile:batch:no_hscroll | PASS | `True` |
| mobile:home:no_hscroll | PASS | `True` |
| mobile:catalog:no_hscroll | PASS | `True` |
| mobile:recipe:no_hscroll | PASS | `True` |
| mobile:dough:no_hscroll | PASS | `True` |
| mobile:pitfalls:no_hscroll | PASS | `True` |
| desktop:batch:no_hscroll | PASS | `True` |
| desktop:home:no_hscroll | PASS | `True` |
| desktop:catalog:no_hscroll | PASS | `True` |
| desktop:recipe:no_hscroll | PASS | `True` |
| desktop:dough:no_hscroll | PASS | `True` |
| desktop:pitfalls:no_hscroll | PASS | `True` |
| timer_counts_down_from_source_80_min | PASS | `Осталось 79:59 · стоп` |
| weigh_checkbox | PASS | `True` |
| oven_temp_text | PASS | `175 °C` |
| filter_zavarnoe_rows | PASS | `2` |
| filter_empty | PASS | `Таких рецептов пока нет` |
| search_case_spaces | PASS | `2` |
| search_pechene | PASS | `4` |
| first_tab_skip | PASS | `True` |
| empty_batch_submit_blocked | PASS | `True` |
| batch_count_updates | PASS | `True` |
| oven_groups_shown | PASS | `True` |
| combined_list_listed | PASS | `True` |
| bought_mark_persists | PASS | `True` |
| header_link_keeps_batch | PASS | `True` |
| home_form_remembers_batch | PASS | `True` |
| unknown_recipe_400_alert | PASS | `True` |
| storage_namespace_own | PASS | `True` |
| nojs_steps | PASS | `9` |
| nojs_pitfalls | PASS | `2` |
| nojs_timers_hidden | PASS | `True` |
| ширины 320/390/768/1440 × 30 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 26 страниц×ширин | PASS | 0 нарушений |
| редактор (/redaktor/) — секрет C не создавался | NOT_RUN | в варианте нет |
