# Карта действий garden-season, вариант B (region-timeline)

Проверено на commit `65f5054` в Chromium: `bin/garden-season qa` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание проверки — в `sezon/qa.py` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| keyboard_first_tab_is_skip | PASS | `True` |
| skip_moves_focus_to_main | PASS | `True` |
| header_before_choice | PASS | `True` |
| home_region_card_opens_region | PASS | `True` |
| region_remembered_in_header | PASS | `True` |
| chip_filter_reduces | PASS | `True` |
| chip_filters_combine | PASS | `True` |
| filter_reset_restores_all | PASS | `True` |
| filter_empty_state_with_exits | PASS | `True` |
| history_back_returns | PASS | `True` |
| history_forward_returns | PASS | `True` |
| timeline_link_opens_work | PASS | `True` |
| year_rows_match_regions | PASS | `True` |
| year_list_has_region_each | PASS | `True` |
| ref_jumps_to_source | PASS | `True` |
| checklist_persists_after_reload | PASS | `True` |
| checklist_reset | PASS | `True` |
| print_button_calls_print | PASS | `True` |
| print_hides_navigation | PASS | `True` |
| month_pager_next | PASS | `True` |
| empty_month_honest | PASS | `True` |
| search_keyboard_results | PASS | `1` |
| search_clear | PASS | `True` |
| search_no_results_message | PASS | `True` |
| 404_has_search_and_home | PASS | `True` |
| nojs_work_steps | PASS | `5` |
| nojs_print_hidden | PASS | `True` |
| nojs_region_filter_works | PASS | `True` |
| nojs_header_links_to_regions | PASS | `True` |
| ширины 320/390/768/1440 × 59 URL | PASS | 0 замечаний (`docs/verification-viewports.json`) |
| axe-core 4.13.0 × 44 страниц×ширин | PASS | 0 нарушений |
| формы с обязательными полями, пагинация | NOT_RUN | в варианте нет |
