# Карта действий home-practical, вариант C (home-audit)

Проверено на commit `6b316b8` в Chromium: `python3 -m udobdom.qa --shots docs/screenshots/6b316b8 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| keyboard_first_tab_is_skip | PASS | `True` |
| skip_moves_focus_to_main | PASS | `True` |
| mobile_rooms_bar_hidden | PASS | `True` |
| mobile_menu_opens | PASS | `True` |
| mobile_menu_link_opens_room | PASS | `True` |
| filter_room_task_combo | PASS | `{'total': 13, 'after': 2, 'ok': True}` |
| filter_reset_restores_all | PASS | `True` |
| filter_empty_state_with_exits | PASS | `True` |
| history_back_returns | PASS | `True` |
| history_forward_returns | PASS | `True` |
| search_keyboard_results | PASS | `2` |
| search_clear | PASS | `True` |
| search_empty_query_hint | PASS | `True` |
| search_no_results_message | PASS | `True` |
| toc_jumps_to_steps | PASS | `True` |
| ref_jumps_to_source | PASS | `True` |
| checklist_persists_after_reload | PASS | `True` |
| checklist_status_text | PASS | `Отмечено 2 из 3. Отметки сохраняются на этом устройстве.` |
| checklist_reset | PASS | `True` |
| save_button_pressed | PASS | `True` |
| save_persists_after_reload | PASS | `True` |
| saved_badge | PASS | `1` |
| saved_page_lists_item | PASS | `True` |
| saved_clear_shows_empty | PASS | `True` |
| print_button_calls_print | PASS | `True` |
| print_hides_navigation | PASS | `True` |
| whole_card_clickable | PASS | `True` |
| problem_link_from_material | PASS | `True` |
| problem_shows_checklist_progress | PASS | `True` |
| problem_untouched_items_no_progress | PASS | `True` |
| problem_item_opens_material | PASS | `True` |
| problems_nav_link | PASS | `True` |
| 404_has_search_and_home | PASS | `True` |
| audit_start_opens_first_room | PASS | `True` |
| audit_count_updates | PASS | `True` |
| audit_next_room_carries_choice | PASS | `True` |
| steps_bar_jumps_keeping_choice | PASS | `True` |
| plan_has_both_choices | PASS | `True` |
| plan_progress_counts | PASS | `True` |
| plan_done_persists | PASS | `True` |
| empty_plan_offers_restore | PASS | `True` |
| restore_opens_saved_plan | PASS | `True` |
| header_plan_link_points_to_choice | PASS | `True` |
| storage_namespace_own | PASS | `True` |
| nojs_material_steps | PASS | `4` |
| nojs_save_button_hidden | PASS | `True` |
| nojs_filter_works | PASS | `True` |
| nojs_rooms_reachable | PASS | `True` |
| nojs_audit_to_plan_via_url | PASS | `True` |
| ширины 320/390/768/1440 × 48 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 40 страниц×ширин | PASS | 0 нарушений |
| формы с обязательными полями, пагинация | NOT_RUN | в варианте нет |
