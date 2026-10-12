# Карта действий plants-home, вариант B (pick-and-diagnose)

Проверено на commit `694e764` в Chromium: `bin/plants-home qa` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `flora/qa.py` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| keyboard_first_tab_is_skip | PASS | `True` |
| skip_moves_focus_to_main | PASS | `True` |
| pick_submits_choices | PASS | `True` |
| pick_shows_three_toxicity_groups | PASS | `True` |
| pick_nodata_warning | PASS | `True` |
| pick_keeps_choice_after_submit | PASS | `True` |
| pick_restart | PASS | `True` |
| pick_empty_state | PASS | `True` |
| home_diagnose_link_opens_problem | PASS | `True` |
| compare_filter_and_sort | PASS | `True` |
| compare_reset | PASS | `True` |
| history_back_returns | PASS | `True` |
| history_forward_returns | PASS | `True` |
| compare_row_opens_plant | PASS | `True` |
| ifthen_items | PASS | `4` |
| ifthen_link_opens_problem | PASS | `True` |
| checklist_persists_after_reload | PASS | `True` |
| checklist_reset | PASS | `True` |
| print_button_calls_print | PASS | `True` |
| print_hides_navigation | PASS | `True` |
| search_keyboard_results | PASS | `1` |
| search_no_results_message | PASS | `True` |
| 404_has_search_and_home | PASS | `True` |
| nojs_pick_works | PASS | `True` |
| nojs_print_hidden | PASS | `True` |
| ширины 320/390/768/1440 × 43 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 44 страниц×ширин | PASS | 0 нарушений |
| формы с обязательными полями, пагинация | NOT_RUN | в варианте нет |
