# Карта действий games-survival, вариант A (craft-tree)

Проверено на commit `e5e1a10` в Chromium: `bin/games-survival qa --shots docs/screenshots/e5e1a10 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| keyboard_first_tab_is_skip | PASS | `True` |
| skip_moves_focus_to_main | PASS | `True` |
| home_chain_opens_item | PASS | `True` |
| made_from_link_opens_ingredient | PASS | `True` |
| nav_opens_section | PASS | `True` |
| whole_card_opens_entry | PASS | `True` |
| item_recipes_shown | PASS | `2` |
| recipe_count_from_source | PASS | `True` |
| used_for_link_opens_product | PASS | `True` |
| product_lists_back_link | PASS | `True` |
| version_badge_opens_version | PASS | `True` |
| item_no_hscroll_on_phone | PASS | `True` |
| print_button_calls_print | PASS | `True` |
| print_hides_navigation | PASS | `True` |
| ref_jumps_to_source | PASS | `True` |
| search_keyboard_results | PASS | `4` |
| search_clear | PASS | `True` |
| search_no_results_message | PASS | `True` |
| 404_has_search_and_home | PASS | `True` |
| history_back_returns | PASS | `True` |
| nojs_recipes_and_links | PASS | `True` |
| nojs_print_hidden | PASS | `True` |
| ширины 320/390/768/1440 × 33 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 30 страниц×ширин | PASS | 0 нарушений |
| формы с обязательными полями, пагинация | NOT_RUN | в варианте нет |
