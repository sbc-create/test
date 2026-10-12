# Карта действий food-appliances, вариант B (step-console)

Проверено на commit `a9c3ec0` в Chromium: `python3 -m techkitchen.qa --shots docs/screenshots/a9c3ec0 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| mobile:home:no_hscroll | PASS | `True` |
| mobile:appliance:no_hscroll | PASS | `True` |
| mobile:category:no_hscroll | PASS | `True` |
| mobile:recipe:no_hscroll | PASS | `True` |
| mobile:recipe_console:no_hscroll | PASS | `True` |
| mobile:mode:no_hscroll | PASS | `True` |
| mobile:guide:no_hscroll | PASS | `True` |
| desktop:home:no_hscroll | PASS | `True` |
| desktop:appliance:no_hscroll | PASS | `True` |
| desktop:category:no_hscroll | PASS | `True` |
| desktop:recipe:no_hscroll | PASS | `True` |
| desktop:recipe_console:no_hscroll | PASS | `True` |
| desktop:mode:no_hscroll | PASS | `True` |
| desktop:guide:no_hscroll | PASS | `True` |
| first_tab_skip | PASS | `True` |
| device_opens_own_table | PASS | `True` |
| table_row_opens_recipe | PASS | `True` |
| setting_chip_in_source_step | PASS | `True` |
| timer_counts_down_15 | PASS | `True` |
| timer_stops | PASS | `True` |
| progress_counts | PASS | `True` |
| marks_persist_after_reload | PASS | `True` |
| storage_keys_own_namespace | PASS | `True` |
| reset_clears | PASS | `True` |
| search_by_mode_results | PASS | `True` |
| modes_nav_opens_guide | PASS | `True` |
| real_404 | PASS | `True` |
| nojs_steps_and_settings | PASS | `True` |
| nojs_timers_and_marks_hidden | PASS | `True` |
| nojs_search_results | PASS | `True` |
| ширины 320/390/768/1440 × 27 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 22 страниц×ширин | PASS | 0 нарушений |
| импорт из источника (сеть) — данные из снимка A | NOT_RUN | в варианте нет |
