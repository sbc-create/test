# Карта действий games-survival, вариант B (craft-planner)

Проверено на commit `0bf2310` в Chromium: `bin/games-survival qa --shots docs/screenshots/0bf2310 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| keyboard_first_tab_is_skip | PASS | `True` |
| skip_moves_focus_to_main | PASS | `True` |
| home_form_opens_plan | PASS | `True` |
| plan_base_coal_16_torches | PASS | `True` |
| plan_steps_in_order | PASS | `True` |
| steps_status_counts | PASS | `True` |
| steps_persist_after_reload | PASS | `True` |
| storage_uses_variant_namespace | PASS | `True` |
| steps_reset_clears | PASS | `True` |
| print_button_calls_print | PASS | `True` |
| print_hides_navigation_and_form | PASS | `True` |
| number_field_blocks_over_max | PASS | `True` |
| bad_quantity_400_with_alert | PASS | `True` |
| nav_opens_catalogue_table | PASS | `True` |
| catalogue_row_opens_entry | PASS | `True` |
| uses_row_opens_plan | PASS | `True` |
| entry_form_plans_quantity | PASS | `True` |
| version_badge_opens_version | PASS | `True` |
| entry_no_hscroll_on_phone | PASS | `True` |
| ref_jumps_to_source | PASS | `True` |
| search_keyboard_results | PASS | `4` |
| search_clear | PASS | `True` |
| search_no_results_message | PASS | `True` |
| 404_has_search_and_home | PASS | `True` |
| history_back_returns | PASS | `True` |
| nojs_plan_computed_on_server | PASS | `True` |
| nojs_reset_and_print_hidden | PASS | `True` |
| ширины 320/390/768/1440 × 38 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 36 страниц×ширин | PASS | 0 нарушений |
| формы с обязательными полями, пагинация | NOT_RUN | в варианте нет |
