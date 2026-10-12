# Карта действий food-daily, вариант B (fridge-first)

Проверено на commit `0f52eaf` в Chromium: `python3 -m fooddaily.qa_browser --shots docs/screenshots/0f52eaf --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| mobile:home:no_hscroll | PASS | `True` |
| mobile:catalog:no_hscroll | PASS | `True` |
| mobile:recipe:no_hscroll | PASS | `True` |
| mobile:fridge:no_hscroll | PASS | `True` |
| mobile:tag:no_hscroll | PASS | `True` |
| mobile:article:no_hscroll | PASS | `True` |
| desktop:home:no_hscroll | PASS | `True` |
| desktop:catalog:no_hscroll | PASS | `True` |
| desktop:recipe:no_hscroll | PASS | `True` |
| desktop:fridge:no_hscroll | PASS | `True` |
| desktop:tag:no_hscroll | PASS | `True` |
| desktop:article:no_hscroll | PASS | `True` |
| servings_scale_2_to_4 | PASS | `True` |
| shopping_list_items | PASS | `6` |
| shopping_list_after_clear_done | PASS | `5` |
| favorite_counter | PASS | `1` |
| favorites_page_items | PASS | `1` |
| step_marks | PASS | `True` |
| fridge | PASS | `True` |
| header_fridge_link | PASS | `True` |
| catalog_sort_by_time | PASS | `True` |
| filter_supy_rows | PASS | `4` |
| filter_reset_link | PASS | `True` |
| filter_empty_state | PASS | `Ничего не нашлось` |
| search_case_spaces | PASS | `1` |
| search_yo | PASS | `1` |
| search_by_ingredient_tykva | PASS | `2` |
| first_tab_skip_link | PASS | `True` |
| nojs_recipe_steps | PASS | `7` |
| nojs_ingredients | PASS | `6` |
| nojs_fav_button_hidden | PASS | `True` |
| ширины 320/390/768/1440 × 57 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 38 страниц×ширин | PASS | 0 нарушений |
| редактор (/redaktor/) — нужен секрет B, не создавался | NOT_RUN | в варианте нет |
