# Карта действий plants-home, вариант C (my-collection)

Проверено на commit `163ff51` в Chromium: `python3 -m flora.qa --shots docs/screenshots/163ff51 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

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
| search_keyboard_results | PASS | `2` |
| search_clear | PASS | `True` |
| search_by_latin | PASS | `1` |
| search_no_results_message | PASS | `True` |
| diagnose_from_home | PASS | `True` |
| diagnose_symptom_opens_problem | PASS | `True` |
| diagnose_species_opens_plant | PASS | `True` |
| compare_table_rows | PASS | `19` |
| compare_sorted_by_care | PASS | `True` |
| compare_noindex | PASS | `True` |
| compare_table_keyboard_scroll | PASS | `True` |
| compare_phone_no_sideways_scroll | PASS | `True` |
| 404_has_search_and_home | PASS | `True` |
| empty_collection_submit_blocked | PASS | `True` |
| mine_count_updates | PASS | `True` |
| collection_has_two_labels | PASS | `True` |
| tox_summary_lists_both | PASS | `True` |
| print_labels_calls_print | PASS | `True` |
| print_shows_only_labels | PASS | `True` |
| header_link_leads_to_collection | PASS | `True` |
| header_link_opens_collection | PASS | `True` |
| home_form_remembers_collection | PASS | `True` |
| storage_namespace_own | PASS | `True` |
| nojs_plant_sections | PASS | `6` |
| nojs_print_hidden | PASS | `True` |
| nojs_filter_works | PASS | `True` |
| ширины 320/390/768/1440 × 45 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 44 страниц×ширин | PASS | 0 нарушений |
| формы с обязательными полями, пагинация | NOT_RUN | в варианте нет |
