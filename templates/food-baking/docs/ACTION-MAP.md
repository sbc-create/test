# Карта действий food-baking, вариант B (oven-bench)

Проверено на commit `4356f03` в Chromium: `python3 -m bakebook.qa --shots docs/screenshots/4356f03 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| mobile:home:no_hscroll | PASS | `True` |
| mobile:catalog:no_hscroll | PASS | `True` |
| mobile:recipe:no_hscroll | PASS | `True` |
| mobile:recipe_pct:no_hscroll | PASS | `True` |
| mobile:dough:no_hscroll | PASS | `True` |
| mobile:pitfalls:no_hscroll | PASS | `True` |
| desktop:home:no_hscroll | PASS | `True` |
| desktop:catalog:no_hscroll | PASS | `True` |
| desktop:recipe:no_hscroll | PASS | `True` |
| desktop:recipe_pct:no_hscroll | PASS | `True` |
| desktop:dough:no_hscroll | PASS | `True` |
| desktop:pitfalls:no_hscroll | PASS | `True` |
| first_tab_skip | PASS | `True` |
| temp_jump_anchor | PASS | `True` |
| temp_row_opens_recipe_at_180 | PASS | `True` |
| timer_counts_down_from_source_80_min | PASS | `True` |
| timer_stops | PASS | `True` |
| steps_progress_text | PASS | `True` |
| marks_persist_after_reload | PASS | `True` |
| storage_keys_own_namespace | PASS | `True` |
| reset_clears_marks | PASS | `True` |
| bakers_pct_butter_50 | PASS | `True` |
| oven_strip_links_to_step | PASS | `True` |
| sort_hot_first | PASS | `True` |
| filter_zavarnoe_rows | PASS | `True` |
| filter_reset | PASS | `True` |
| filter_empty | PASS | `True` |
| search_case_spaces | PASS | `True` |
| search_pechene | PASS | `True` |
| batch_empty_submit_blocked | PASS | `True` |
| batch_count_updates | PASS | `True` |
| batch_oven_groups_shown | PASS | `True` |
| batch_combined_list_rows | PASS | `20` |
| batch_bought_mark_persists | PASS | `True` |
| batch_header_link_keeps_choice | PASS | `True` |
| batch_form_remembers_choice | PASS | `True` |
| batch_unknown_recipe_400_alert | PASS | `True` |
| batch_storage_namespace_own | PASS | `True` |
| real_404 | PASS | `True` |
| nojs_steps | PASS | `True` |
| nojs_pitfalls | PASS | `True` |
| nojs_timers_and_marks_hidden | PASS | `True` |
| ширины 320/390/768/1440 × 29 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 30 страниц×ширин | PASS | 0 нарушений |
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

Редактор проверен на `229f66b` на изолированной копии (порт 8883): `docs/verification-editor.json`, способ — там же.
