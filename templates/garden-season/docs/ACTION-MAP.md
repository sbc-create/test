# Карта действий garden-season, вариант C (my-plot)

Проверено на commit `ceb8900` в Chromium: `python3 -m sezon.qa --shots docs/screenshots/ceb8900 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| keyboard_first_tab_is_skip | PASS | `True` |
| skip_moves_focus_to_main | PASS | `True` |
| month_strip_opens_october | PASS | `True` |
| month_groups_regions | PASS | `3` |
| pager_next_month | PASS | `True` |
| pager_prev_month | PASS | `True` |
| december_lists_new_works | PASS | `True` |
| filter_region_reduces | PASS | `True` |
| filter_reset_restores_all | PASS | `True` |
| filter_empty_state_with_exits | PASS | `True` |
| history_back_returns | PASS | `True` |
| history_forward_returns | PASS | `True` |
| crop_cell_opens_work | PASS | `True` |
| timing_rows_with_region | PASS | `True` |
| toc_jumps_to_steps | PASS | `True` |
| ref_jumps_to_source | PASS | `True` |
| checklist_persists_after_reload | PASS | `True` |
| checklist_reset | PASS | `True` |
| print_button_calls_print | PASS | `True` |
| print_hides_navigation | PASS | `True` |
| whole_card_clickable | PASS | `True` |
| search_keyboard_results | PASS | `1` |
| search_clear | PASS | `True` |
| search_by_month | PASS | `12` |
| search_no_results_message | PASS | `True` |
| 404_has_search_and_home | PASS | `True` |
| plot_from_home_shows_only_allowed_regions | PASS | `True` |
| plot_months_in_order | PASS | `True` |
| plot_progress_counts | PASS | `True` |
| plot_done_persists | PASS | `True` |
| home_form_remembers_choice | PASS | `True` |
| unknown_region_400_alert | PASS | `True` |
| no_works_honest_empty_state | PASS | `True` |
| header_plot_link_shows_region | PASS | `True` |
| header_plot_link_keeps_choice | PASS | `True` |
| header_plot_link_opens_plan | PASS | `True` |
| storage_namespace_own | PASS | `True` |
| nojs_work_steps | PASS | `5` |
| nojs_print_hidden | PASS | `True` |
| nojs_filter_works | PASS | `True` |
| ширины 320/390/768/1440 × 64 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 48 страниц×ширин | PASS | 0 нарушений |
| формы с обязательными полями, пагинация | NOT_RUN | в варианте нет |
