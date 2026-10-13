# Карта действий food-daily, вариант C (party-list)

Проверено на commit `e0130d5` в Chromium: `python3 -m fooddaily.qa_browser --shots docs/screenshots/e0130d5 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| mobile:party:no_hscroll | PASS | `True` |
| mobile:home:no_hscroll | PASS | `True` |
| mobile:catalog:no_hscroll | PASS | `True` |
| mobile:recipe:no_hscroll | PASS | `True` |
| mobile:tag:no_hscroll | PASS | `True` |
| mobile:article:no_hscroll | PASS | `True` |
| desktop:party:no_hscroll | PASS | `True` |
| desktop:home:no_hscroll | PASS | `True` |
| desktop:catalog:no_hscroll | PASS | `True` |
| desktop:recipe:no_hscroll | PASS | `True` |
| desktop:tag:no_hscroll | PASS | `True` |
| desktop:article:no_hscroll | PASS | `True` |
| servings_scale_2_to_4 | PASS | `True` |
| shopping_list_items | PASS | `6` |
| shopping_list_after_clear_done | PASS | `5` |
| favorite_counter | PASS | `1` |
| favorites_page_items | PASS | `1` |
| cooking_mode | PASS | `True` |
| filter_supy_cards | PASS | `4` |
| filter_reset_link | PASS | `True` |
| filter_empty_state | PASS | `Ничего не нашлось` |
| search_case_spaces | PASS | `1` |
| search_yo | PASS | `1` |
| search_by_ingredient_tykva | PASS | `2` |
| first_tab_skip_link | PASS | `True` |
| party_empty_submit_blocked | PASS | `True` |
| party_count_updates | PASS | `True` |
| party_list_scaled | PASS | `True` |
| party_bought_persists | PASS | `True` |
| party_header_link_keeps_choice | PASS | `True` |
| party_home_remembers_choice | PASS | `True` |
| party_bad_guests_400_alert | PASS | `True` |
| party_storage_namespace_own | PASS | `True` |
| nojs_recipe_steps | PASS | `7` |
| nojs_ingredients | PASS | `6` |
| nojs_fav_button_hidden | PASS | `True` |
| ширины 320/390/768/1440 × 56 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 30 страниц×ширин | PASS | 0 нарушений |
| редактор (/redaktor/) — секрет C не создавался | NOT_RUN | в варианте нет |
