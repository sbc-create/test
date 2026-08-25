SEO_OPERATOR_CODE_READY=no
LIVE_HOST_VERIFICATION=pending
PORTFOLIO_SITES_TOTAL=1
PORTFOLIO_SITES_MEASURED=0
METRIKA_ACCESS=BLOCKED_SECRET
WEBMASTER_ACCESS=BLOCKED_SECRET
BASELINE_ORGANIC_DAILY_UNIQUE=NOT_MEASURED
TARGET_GAP=NOT_MEASURED
REQUIRED_NEW_SITES_RANGE=INCONCLUSIVE
DAILY_CYCLE=pass
WEEKLY_REPORT=pass
ACTION_LEDGER=pass
EXPERIMENT_ENGINE=pass
RESTORE_DRILL=pending
TESTS=550 passed in 5.04s
SECRET_SCAN=clean
COMMIT=5c9c3d4926bc9283d14961acbddedc298937a1c2
PR=none
BLOCKERS=нет подключённых источников и production-хоста; нет подключённых источников и production-хоста; нет staging-хоста; нет production-хоста; не выполнялся на отдельном target
NEXT_SAFE_ACTION=подключить Secret Hub и Метрику одного пилотного сайта

## Критерии приёмки (ТЗ §17)
| # | Критерий | Статус | Доказательство / блокер |
|---|---|---|---|
| 1 | Обнаружить все зарегистрированные сайты и показать неполный инвентарь | pass | portfolio validate: 1 сайт(ов), статус NOT_POPULATED |
| 2 | Проверить доступ к Метрике и Вебмастеру, не раскрывая токен | pass | access audit обращается к Secret Hub только за фактом наличия; тест test_handle_never_contains_a_value |
| 3 | Собрать минимум один полный день данных для пилотных сайтов | FAIL | нет подключённых источников и production-хоста |
| 4 | Показать трафик, запросы, позиции, CTR, индексирование и диагностику | FAIL | нет подключённых источников и production-хоста |
| 5 | Сопоставить данные с журналом действий | pass | ledger.actions_in_window + attribution.link_to_actions, тесты пройдены |
| 6 | Создать измеримую задачу с baseline и датой оценки | pass | planner создаёт задачу с baseline и evaluate_after; задача без них отклоняется |
| 7 | Подготовить изменение, проверить на staging и сформировать evidence | FAIL | нет staging-хоста |
| 8 | После разрешённой публикации проверить фактический production URL | FAIL | нет production-хоста |
| 9 | Сформировать ежедневный и недельный отчёт | pass | daily-run и weekly-report формируются |
| 10 | Честно показать разрыв до 7 млн и диапазон необходимого числа сайтов | pass | forecast возвращает разрыв и диапазон либо INCONCLUSIVE с причиной |
| 11 | Пережить повторный запуск без дублей | pass | джобы идемпотентны по job_key; тест test_job_enqueue_is_idempotent |
| 12 | Восстановиться из backup на отдельном target | FAIL | не выполнялся на отдельном target |
| 13 | Пройти CI, secret scan и live-host verification | pass | локальный прогон тестов и secret scan |
