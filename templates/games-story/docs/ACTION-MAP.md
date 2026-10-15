# Карта действий games-story, вариант A (chapter-guides)

Проверено на commit `ff3ed16` в Chromium: `bin/games-story qa` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `saga/qa.py` под тем же именем).

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
| nojs_video_link_only | PASS | `True` |
| nojs_guide_route | PASS | `3` |
| ширины 320/390/768/1440 × 19 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 28 страниц×ширин | PASS | 0 нарушений |
| формы с обязательными полями, пагинация | NOT_RUN | в варианте нет |
