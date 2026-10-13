# Карта действий food-baking, вариант C (bake-batch)

Проверено на commit `9824976` в Chromium: `python3 -m bakebook.qa --shots docs/screenshots/9824976 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| mobile:batch:no_hscroll | PASS | `True` |
| mobile:home:no_hscroll | PASS | `True` |
| mobile:catalog:no_hscroll | PASS | `True` |
| mobile:recipe:no_hscroll | PASS | `True` |
| mobile:dough:no_hscroll | PASS | `True` |
| mobile:pitfalls:no_hscroll | PASS | `True` |
| desktop:batch:no_hscroll | PASS | `True` |
| desktop:home:no_hscroll | PASS | `True` |
| desktop:catalog:no_hscroll | PASS | `True` |
| desktop:recipe:no_hscroll | PASS | `True` |
| desktop:dough:no_hscroll | PASS | `True` |
| desktop:pitfalls:no_hscroll | PASS | `True` |
| timer_counts_down_from_source_80_min | PASS | `Осталось 79:59 · стоп` |
| weigh_checkbox | PASS | `True` |
| oven_temp_text | PASS | `175 °C` |
| filter_zavarnoe_rows | PASS | `2` |
| filter_empty | PASS | `Таких рецептов пока нет` |
| search_case_spaces | PASS | `2` |
| search_pechene | PASS | `4` |
| first_tab_skip | PASS | `True` |
| empty_batch_submit_blocked | PASS | `True` |
| batch_count_updates | PASS | `True` |
| oven_groups_shown | PASS | `True` |
| combined_list_listed | PASS | `True` |
| bought_mark_persists | PASS | `True` |
| header_link_keeps_batch | PASS | `True` |
| home_form_remembers_batch | PASS | `True` |
| unknown_recipe_400_alert | PASS | `True` |
| storage_namespace_own | PASS | `True` |
| nojs_steps | PASS | `9` |
| nojs_pitfalls | PASS | `2` |
| nojs_timers_hidden | PASS | `True` |
| ширины 320/390/768/1440 × 30 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 26 страниц×ширин | PASS | 0 нарушений |
| редактор: без входа — 401 и запрос Basic Auth | PASS | `no_auth_401_with_challenge` |
| редактор: неверный пароль — 401 | PASS | `wrong_password_401` |
| редактор: чужое имя с верным паролем — 401 | PASS | `wrong_user_401` |
| редактор: верные данные — 200 | PASS | `login_200` |
| редактор: страница редактора — noindex | PASS | `editor_noindex` |
| редактор: robots закрывает /redaktor/ (в preview — «Disallow: /») | PASS | `robots_disallow_redaktor` |
| редактор: в sitemap нет /redaktor/ | PASS | `sitemap_has_no_redaktor` |
| редактор: строк в таблице столько же, сколько рецептов в content.json | PASS | `list_rows_match_content` |
| редактор: история версий совпадает с history.jsonl | PASS | `history_rows_match_file` |
| редактор: POST не принимается (501): редактор только читает | PASS | `post_not_accepted` |
| редактор: на странице нет форм изменения | PASS | `read_only_no_forms` |
| редактор: нет горизонтального скролла на 390 и 1440 px | PASS | `no_hscroll_editor_pages` |
| редактор: axe-core 4.13.0 — 0 нарушений | PASS | `axe_zero_editor_pages` |
| редактор: нет ошибок консоли | PASS | `no_console_errors` |

Редактор проверен на `9824976` на изолированной копии (порт 8884): `docs/verification-editor.json`, способ — там же.
