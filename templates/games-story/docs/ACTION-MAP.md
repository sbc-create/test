# Карта действий games-story, вариант C (atlas)

Проверено на commit `3ca1947` в Chromium: `python3 -m saga.qa --shots docs/screenshots/3ca1947 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| keyboard_first_tab_is_skip | PASS | `True` |
| skip_moves_focus_to_main | PASS | `True` |
| no_external_requests_on_load | PASS | `True` |
| nav_opens_game | PASS | `True` |
| whole_card_opens_guide | PASS | `True` |
| route_rendered | PASS | `True` |
| progress_persists_after_reload | PASS | `True` |
| game_page_shows_chapter_progress | PASS | `True` |
| home_tally_red_from_source | PASS | `True` |
| home_tally_sides | PASS | `True` |
| home_tally_full_chapters | PASS | `True` |
| progress_reset | PASS | `True` |
| pager_next_chapter | PASS | `True` |
| pager_prev_chapter | PASS | `True` |
| toc_jumps | PASS | `True` |
| video_no_iframe_before_click | PASS | `True` |
| video_iframe_after_click | PASS | `True` |
| video_external_request_only_after_click | PASS | `True` |
| print_button_calls_print | PASS | `True` |
| print_hides_navigation | PASS | `True` |
| search_keyboard_results | PASS | `9` |
| search_clear | PASS | `True` |
| search_no_results_message | PASS | `True` |
| 404_has_search_and_home | PASS | `True` |
| home_where_am_i_finds_checkpoint | PASS | `True` |
| checkpoint_opens_chapter | PASS | `True` |
| live_filter_narrows | PASS | `True` |
| live_filter_clears | PASS | `True` |
| character_chip_opens_page | PASS | `True` |
| character_page_links_chapter | PASS | `True` |
| mechanics_table_rows | PASS | `True` |
| unknown_character_404 | PASS | `True` |
| nojs_video_link_only | PASS | `True` |
| nojs_guide_route | PASS | `3` |
| ширины 320/390/768/1440 × 29 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 32 страниц×ширин | PASS | 0 нарушений |
| формы с обязательными полями, пагинация | NOT_RUN | в варианте нет |
