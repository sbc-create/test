# Карта действий plants-home, вариант A (plant-catalog)

Проверено на commit `f034b3f` в Chromium: `bin/plants-home qa` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `flora/qa.py` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| keyboard_first_tab_is_skip | PASS | `True` |
| skip_moves_focus_to_main | PASS | `True` |
| light_card_opens_category | PASS | `True` |
| filter_light_and_care | PASS | `True` |
| filter_reset_restores_all | PASS | `True` |
| filter_empty_state_with_exits | PASS | `True` |
| history_back_returns | PASS | `True` |
| history_forward_returns | PASS | `True` |
| whole_card_clickable | PASS | `True` |
| passport_light_link | PASS | `True` |
| problem_link_opens_problem | PASS | `True` |
| toc_jumps_to_section | PASS | `True` |
| checklist_persists_after_reload | PASS | `True` |
| checklist_reset | PASS | `True` |
| print_button_calls_print | PASS | `True` |
| print_hides_navigation | PASS | `True` |
| search_keyboard_results | PASS | `1` |
| search_clear | PASS | `True` |
| search_by_latin | PASS | `1` |
| search_no_results_message | PASS | `True` |
| 404_has_search_and_home | PASS | `True` |
| nojs_plant_sections | PASS | `6` |
| nojs_print_hidden | PASS | `True` |
| nojs_filter_works | PASS | `True` |
| ширины 320/390/768/1440 × 40 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 42 страниц×ширин | PASS | 0 нарушений |
| формы с обязательными полями, пагинация, сохранённое | NOT_RUN | в варианте нет |
