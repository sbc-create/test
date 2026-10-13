# Карта действий food-daily, вариант C (party-list)

Проверено на commit `9514da0` в Chromium: `python3 -m fooddaily.qa_browser --shots docs/screenshots/9514da0 --out docs/verification-browser-qa.json` → `docs/verification-browser-qa.json`, exit 0.
Каждая строка — действие с проверкой результата (описание — в `docs/verification-browser-qa.json` под тем же именем).

| проверка | статус | фактический результат |
| --- | --- | --- |
| mobile:party:no_hscroll | PASS | `True` |
| mobile:home:no_hscroll | PASS | `True` |
| mobile:catalog:no_hscroll | PASS | `True` |
| mobile:recipe:no_hscroll | PASS | `True` |
| mobile:tag:no_hscroll | PASS | `True` |
| mobile:article:no_hscroll | PASS | `True` |
| desktop:party:no_hscroll | PASS | `True` |
| desktop:home:no_hscroll | PASS | `True` |
| desktop:catalog:no_hscroll | PASS | `True` |
| desktop:recipe:no_hscroll | PASS | `True` |
| desktop:tag:no_hscroll | PASS | `True` |
| desktop:article:no_hscroll | PASS | `True` |
| servings_scale_2_to_4 | PASS | `True` |
| shopping_list_items | PASS | `6` |
| shopping_list_after_clear_done | PASS | `5` |
| favorite_counter | PASS | `1` |
| favorites_page_items | PASS | `1` |
| cooking_mode | PASS | `True` |
| filter_supy_cards | PASS | `4` |
| filter_reset_link | PASS | `True` |
| filter_empty_state | PASS | `Ничего не нашлось` |
| search_case_spaces | PASS | `1` |
| search_yo | PASS | `1` |
| search_by_ingredient_tykva | PASS | `2` |
| first_tab_skip_link | PASS | `True` |
| party_empty_submit_blocked | PASS | `True` |
| party_count_updates | PASS | `True` |
| party_list_scaled | PASS | `True` |
| party_bought_persists | PASS | `True` |
| party_header_link_keeps_choice | PASS | `True` |
| party_home_remembers_choice | PASS | `True` |
| party_bad_guests_400_alert | PASS | `True` |
| party_storage_namespace_own | PASS | `True` |
| fridge_header_link | PASS | `True` |
| fridge_hint_counts_two | PASS | `True` |
| fridge_first_has_both_plov | PASS | `True` |
| fridge_results_listed | PASS | `6` |
| fridge_remembers_selection | PASS | `True` |
| fridge_clear_forgets_selection | PASS | `True` |
| fridge_empty_submit_blocked | PASS | `True` |
| fridge_unknown_product_400_alert | PASS | `True` |
| catalog_table_sort_by_time | PASS | `True` |
| catalog_view_noindex | PASS | `True` |
| storage_namespace_own_after_fridge | PASS | `True` |
| nojs_recipe_steps | PASS | `7` |
| nojs_ingredients | PASS | `6` |
| nojs_fav_button_hidden | PASS | `True` |
| ширины 320/390/768/1440 × 56 URL | PASS | 0 замечаний |
| axe-core 4.13.0 × 30 страниц×ширин | PASS | 0 нарушений |
| редактор: без входа — 401 и запрос Basic Auth | PASS | `no_auth_401_with_challenge` |
| редактор: неверный пароль — 401 | PASS | `wrong_password_401` |
| редактор: чужое имя с верным паролем — 401 | PASS | `wrong_user_401` |
| редактор: верные данные — 200 | PASS | `login_200` |
| редактор: страница редактора — noindex | PASS | `editor_noindex` |
| редактор: robots закрывает /redaktor/ (в preview — «Disallow: /») | PASS | `robots_disallow_redaktor` |
| редактор: в sitemap нет /redaktor/ | PASS | `sitemap_has_no_redaktor` |
| редактор: строк в списке столько же, сколько материалов в БД (24) | PASS | `list_rows_match_db` |
| редактор: публичная страница выбранного рецепта — 200 | PASS | `public_page_200_before` |
| редактор: параметр msg экранируется (<script> не исполняется) | PASS | `msg_param_escaped` |
| редактор: POST без CSRF-токена — 403 | PASS | `post_without_csrf_403` |
| редактор: POST без входа — 401 | PASS | `post_without_auth_401` |
| редактор: после отклонённых POST страница не изменилась (200) | PASS | `public_page_200_after_refused_posts` |
| редактор: ссылка из списка открывает материал | PASS | `list_link_opens_item` |
| редактор: «Снять» → сообщение «снято с preview» | PASS | `unpublish_msg` |
| редактор: статус публикации стал hidden | PASS | `unpublish_status_hidden` |
| редактор: публичная страница после снятия — 404 | PASS | `public_page_404_after_unpublish` |
| редактор: снимок сайта изменился только у этого материала | PASS | `snapshot_only_target_removed` |
| редактор: «В preview» → страница снова 200 | PASS | `republish_restores_public_page` |
| редактор: откат к v1 создаёт новую версию, а не стирает историю | PASS | `rollback_creates_new_version` |
| редактор: diff между версиями показан | PASS | `diff_shown` |
| редактор: решение редактора записано (статус editor_rejected на копии) | PASS | `review_recorded` |
| редактор: журнал содержит действия editor:<имя> | PASS | `audit_log_has_editor_actions` |
| редактор: нет горизонтального скролла на 390 и 1440 px | PASS | `no_hscroll_editor_pages` |
| редактор: axe-core 4.13.0 — 0 нарушений | PASS | `axe_zero_editor_pages` |
| редактор: нет ошибок консоли | PASS | `no_console_errors` |

Редактор проверен на `fff36e7` на изолированной копии (порт 8882): `docs/verification-editor.json`, способ — там же.
