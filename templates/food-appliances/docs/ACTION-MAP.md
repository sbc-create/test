# Карта действий food-appliances, вариант C (device-queue)

Проверено на commit `bb5a44d` в Chromium: `python3 -m techkitchen.qa --shots docs/screenshots/bb5a44d --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| mobile:queue:no_hscroll | PASS | `True` |
| mobile:home:no_hscroll | PASS | `True` |
| mobile:appliance:no_hscroll | PASS | `True` |
| mobile:category:no_hscroll | PASS | `True` |
| mobile:recipe:no_hscroll | PASS | `True` |
| mobile:mode:no_hscroll | PASS | `True` |
| mobile:guide:no_hscroll | PASS | `True` |
| desktop:queue:no_hscroll | PASS | `True` |
| desktop:home:no_hscroll | PASS | `True` |
| desktop:appliance:no_hscroll | PASS | `True` |
| desktop:category:no_hscroll | PASS | `True` |
| desktop:recipe:no_hscroll | PASS | `True` |
| desktop:mode:no_hscroll | PASS | `True` |
| desktop:guide:no_hscroll | PASS | `True` |
| display_link_targets_step | PASS | `True` |
| search_by_mode_results | PASS | `2` |
| first_tab_skip | PASS | `True` |
| empty_queue_submit_blocked | PASS | `True` |
| queue_count_updates | PASS | `True` |
| queue_two_devices | PASS | `True` |
| aerogril_grouped_by_temp | PASS | `True` |
| done_mark_persists | PASS | `True` |
| header_link_keeps_queue | PASS | `True` |
| home_form_remembers_queue | PASS | `True` |
| unknown_recipe_400_alert | PASS | `True` |
| storage_namespace_own | PASS | `True` |
| nojs_recipe_steps | PASS | `6` |
| nojs_search_results | PASS | `6` |
| ширины 320/390/768/1440 × 30 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 22 страниц×ширин | PASS | 0 нарушений |
| импорт из источника (сеть) — данные из снимка A | NOT_RUN | в варианте нет |
