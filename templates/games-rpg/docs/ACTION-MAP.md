# Карта действий games-rpg, вариант A (codex-sections)

Проверено на commit `2bb97b8` в Chromium: `bin/games-rpg qa --shots docs/screenshots/2bb97b8 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| keyboard_first_tab_is_skip | PASS | `True` |
| skip_moves_focus_to_main | PASS | `True` |
| nav_opens_section | PASS | `True` |
| whole_card_opens_entry | PASS | `True` |
| abilities_shown | PASS | `True` |
| patch_badge_opens_version | PASS | `True` |
| build_progression_rows | PASS | `12` |
| build_no_hscroll_on_phone | PASS | `True` |
| quest_stages_persist | PASS | `True` |
| quest_stages_reset | PASS | `True` |
| print_button_calls_print | PASS | `True` |
| print_hides_navigation | PASS | `True` |
| ref_jumps_to_source | PASS | `True` |
| search_keyboard_results | PASS | `1` |
| search_clear | PASS | `True` |
| search_no_results_message | PASS | `True` |
| 404_has_search_and_home | PASS | `True` |
| history_back_returns | PASS | `True` |
| nojs_stages_listed | PASS | `8` |
| nojs_print_hidden | PASS | `True` |
| ширины 320/390/768/1440 × 36 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 30 страниц×ширин | PASS | 0 нарушений |
| формы с обязательными полями, пагинация | NOT_RUN | в варианте нет |
