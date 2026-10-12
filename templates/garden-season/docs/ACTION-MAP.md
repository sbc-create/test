# Карта действий garden-season, вариант A (month-calendar)

Проверено на commit `31fec6c` в Chromium: `bin/garden-season qa` → `docs/verification-browser-qa.json`, exit 0.

| тип страницы | блок | действие | ожидаемый результат | фактический результат | статус |
| --- | --- | --- | --- | --- | --- |
| любая | шапка | Tab, Enter на «К содержимому» | фокус на skip-ссылке, затем в main | `keyboard_first_tab_is_skip`=True, `skip_moves_focus_to_main`=True | PASS |
| любая | лента месяцев | клик «окт» | открыт октябрь, пункт ленты отмечен текущим | `month_strip_opens_october`=True | PASS |
| месяц | группы | открыть октябрь | работы в секциях по регионам | `month_groups_regions`=3 | PASS |
| месяц | листание | «Ноябрь →», «← Октябрь» | соседние месяцы | `pager_next_month`=True, `pager_prev_month`=True | PASS |
| месяц без работ | пустое состояние | открыть декабрь | объяснение и ссылка на календарь OSU | `empty_month_honest`=True | PASS |
| календарь | фильтр региона | Западный Орегон → «Показать» | работ меньше, чем без фильтра | `filter_region_reduces`=True | PASS |
| календарь | «Сбросить» | нажать | все работы | `filter_reset_restores_all`=True | PASS |
| календарь | пустое сочетание | Великобритания × подготовка к зиме | сообщение и 2 выхода | `filter_empty_state_with_exits`=True | PASS |
| календарь | история | назад / вперёд | возврат к фильтрам | `history_back_returns`=True, `history_forward_returns`=True | PASS |
| культура | ячейка таблицы | клик по «●» | открыта работа | `crop_cell_opens_work`=True | PASS |
| работа | сроки по регионам | открыть | у каждой строки срока — регион | `timing_rows_with_region`=True | PASS |
| работа | оглавление, [n] | клик | переход к шагам и к источнику | `toc_jumps_to_steps`=True, `ref_jumps_to_source`=True | PASS |
| работа | чек-лист | отметить, перезагрузить; снять | отметка сохранилась; снята | `checklist_persists_after_reload`=True, `checklist_reset`=True | PASS |
| работа | «Печать» | нажать; режим print | print вызван 1 раз; без навигации, сроки видны | `print_button_calls_print`=True, `print_hides_navigation`=True | PASS |
| регион | карточка | клик вне заголовка | открыта работа | `whole_card_clickable`=True | PASS |
| поиск | поле | «чеснок» + Enter; «Очистить»; «октябрь»; «квантовый» | результаты; пусто; поиск по месяцу; «Ничего не нашлось» | `search_keyboard_results`=1, `search_clear`=True, `search_by_month`=10, `search_no_results_message`=True | PASS |
| 404 | тело | — | поиск и ссылка на главную | `404_has_search_and_home`=True | PASS |
| без JS | работа, календарь | открыть; GET-фильтр | шаги видны, печать скрыта; фильтр работает | `nojs_work_steps`=5, `nojs_print_hidden`=True, `nojs_filter_works`=True | PASS |
| 58 URL × 320/390/768/1440 | вёрстка | скролл, подсказки, `href="#"`, зоны <24 px, вложенные ссылки, консоль | нет | 0 (`docs/verification-viewports.json`) | PASS |
| 46 страниц×ширин | доступность | axe-core 4.13.0 | 0 нарушений | 0 | PASS |
| — | формы с обязательными полями, пагинация, сохранённое | — | в варианте A нет | неприменимо | NOT_RUN |
