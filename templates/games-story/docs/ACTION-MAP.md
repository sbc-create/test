# Карта действий games-story, вариант B (progress-tracker)

Проверено на commit `423ba88` в Chromium: `bin/games-story qa` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `saga/qa.py` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| keyboard_first_tab_is_skip | PASS | `True` |
| skip_moves_focus_to_main | PASS | `True` |
| no_external_requests_on_load | PASS | `True` |
| home_counters_zero | PASS | `True` |
| home_opens_tracker | PASS | `True` |
| tracker_totals_update | PASS | `True` |
| tracker_clamps_to_source_max | PASS | `True` |
| tracker_persists_after_reload | PASS | `True` |
| home_counters_after_progress | PASS | `True` |
| guide_tracker_shares_state | PASS | `True` |
| route_rendered | PASS | `True` |
| pager_next_chapter | PASS | `True` |
| tracker_reset_all | PASS | `True` |
| items_type_page | PASS | `True` |
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
| nojs_tracker_disabled_numbers_visible | PASS | `True` |
| ширины 320/390/768/1440 × 22 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 28 страниц×ширин | PASS | 0 нарушений |
| формы с обязательными полями, пагинация | NOT_RUN | в варианте нет |
