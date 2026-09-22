# Чеклист приёмки владельцем — COMMUNITY-COMMENTS-PLATFORM-01

Статус стадии: `READY_FOR_LOCAL_REVIEW`. Ничего не выложено, ничего не
включено, production-миграций не было.

Ниже разделено то, что смешивать нельзя: сделанное, проверенное,
подготовленное и требующее вашего решения.

## Реализовано и проверено исполнением

| Требование | Где | Чем подтверждено |
| --- | --- | --- |
| Единое ядро, без копий в шаблонах | `factory/comments_platform/` | `test_site_registry_config.py::TestNoWidgetSourceInTenantTemplates` |
| Арендатор выводится сервером, не принимается от клиента | `tenancy.py` | `test_tenancy.py`, `test_api.py::TestScopeCannotBeSupplied` |
| Ключ обсуждения — контент, не URL | `tenancy.ResourceRef` | `test_service.py::test_thread_is_keyed_by_content_not_by_slug` |
| Изоляция арендаторов на всех операциях | схема + `store.py` | `test_tenant_isolation.py`, 182 теста, все упорядоченные пары |
| Изоляция ниже API: очередь, аудит, экспорт, воркер, лимиты | `store.py` | `test_tenant_isolation.py::TestQueuesAndBackgroundWork` |
| Кросс-арендаторский доступ отвечает 404, не 403 | `errors.CrossTenantDenied` | `test_rbac_matrix.py::TestScopeBeatsPermission` |
| Публичное чтение, курсорная пагинация, три сортировки | `service.py`, `store.py` | `test_service.py`, `test_api.py` |
| Создание, ответ, правка, удаление своего, ревизии | `service.py` | `test_service.py::TestEditAndDelete` |
| Идемпотентность: повтор не создаёт дубль | `store.idempotent_replay` | `test_service.py::TestIdempotency` |
| Реакции: одна на человека, изменение не добавляет | `store.set_reaction` | `test_service.py::TestReactions` |
| Жалобы: повтор неотличим от первой, бригады не прячут | `service.report_comment` | `test_service.py::TestReports` |
| Машина состояний, автоматика не удаляет, правка — в модерацию | `states.py` | `test_states.py` |
| Обязательная причина ручного действия | `audit.record` | `test_audit.py`, `test_service.py` |
| Fail-closed при отказе античита | `states.initial_state` | `test_service.py::TestRiskAndFailClosed` |
| Kill switch, без перезапуска | `flags.KillSwitch` | `test_flags.py`, `test_resilience.py` |
| RBAC, запрет по умолчанию, семь ролей | `rbac.py` | `test_rbac_matrix.py` |
| tenant_admin не получает production deploy | `rbac.GRANTS` | `test_rbac_matrix.py::TestRoleSeparation` |
| Никто не повышает себе роль | `rbac.authorize_role_grant` | `test_rbac_matrix.py::TestSelfElevation` |
| Автор изменения не одобряет свой выкат | `authorize_production_approval` | `test_rbac_matrix.py::TestFourEyes` |
| Служебный токен: область, audience, действия, TTL 900 с | `issue_service_principal` | `test_rbac_matrix.py::TestServiceTokens` |
| Обратимая миграция, составные внешние ключи | `migrations/0007` | `test_migration.py` |
| Версионированный API и OpenAPI, сверенный с реализацией | `api.py` | `test_api.py::TestOpenApiMatchesTheImplementation` |
| CORS точным списком, без wildcard и эха | `api._cors_headers` | `test_api.py::TestCors` |
| CSRF на небезопасных методах при куки | `api._check_csrf` | `test_api.py::TestCsrf` |
| Ошибки без внутренних деталей, с request id | `api.handle` | `test_api.py::TestErrorsAreSafe` |
| XSS: 42 payload, проверка парсером | `sanitize.py` | `test_sanitize_xss.py` |
| Виджет: mount/destroy идемпотентны, несколько экземпляров | `comments-widget.js` | `widget.spec.js::lifecycle` |
| Отказ API не ломает страницу | там же | `widget.spec.js` |
| Текст сохраняется после ошибки отправки | там же | `widget.spec.js::composing` |
| Ширины 320–1920 без переполнения, touch 44 px | `comments-widget.css` | `widget.spec.js::responsive matrix` |
| axe WCAG 2.2 AA на 320/768/1440 | там же | `widget.spec.js::accessibility` |
| Клавиатура, видимый фокус, live-region, reduced motion | там же | `widget.spec.js::accessibility` |
| Внешние ссылки с `rel="ugc nofollow"` | `sanitize.LINK_REL` | `test_sanitize_xss.py`, `widget.spec.js` |
| SSR только опубликованного, без клоакинга | `ssr.py` | `test_ssr_seo.py` |
| Модуль не меняет SEO-поверхность сайта | `ssr.py` | `test_ssr_seo.py::TestSeoSurfaceIsNotTouched` |
| Аудит append-only, без текста комментариев | `audit.py` | `test_audit.py` |
| Метрики по арендатору/сайту/версии, без содержимого | `metrics.py` | `test_metrics.py` |
| Несвязанность личностей между сайтами | `identity.py` | `test_identity.py::TestNonCorrelation` |
| Backup/restore на файловой БД | — | `test_resilience.py::TestBackupAndRestore` |
| Репетиция откaта схемы | — | `test_resilience.py::TestMigrationRollbackRehearsal` |
| Внедрение отказа: транзакция не оставляет следов | — | `test_resilience.py::TestFailureInjection` |

## Подготовлено, но не запущено

* Миграция `0007` — применяется только к изолированной тестовой базе.
* Выгрузка, анонимизация и удаление по субъекту — реализованы и проверены на
  тестовой базе, на production не запускались.
* Привязка девяти сайтов в `config/comments-platform/sites.json` — все ворота
  нули.
* Systemd-юнита нет, службы нет, портов не слушается.

## Не выложено

Ничего. `PRODUCTION_MUTATIONS=0`, `DEPLOY_PERFORMED=0`,
`RESTART_PERFORMED=0`, `DNS_MUTATIONS=0`, `TLS_MUTATIONS=0`,
`INDEXABILITY_MUTATIONS=0`, `RATINGS_MUTATIONS=0`, `SEO_MUTATIONS=0`,
`TEMPLATE_MUTATIONS=0`.

## Требует вашего решения

1. **Начинать ли стадию 1** — staging, один сайт, только чтение. Это требует
   поднять потолок `CEILING_READ_ENABLED` в исходном коде: конфигом не
   включается, и это сделано намеренно.

2. **Что делать с прежним контуром** `factory/community/comments/` и веткой
   `cursor/community-comments-01`. Он нетронут и не подключён. В репозитории
   сейчас два набора кода комментариев, и это названо в ADR-001, а не
   оставлено на потом. Решение — ваше.

3. **Нужен ли путь Qwen.** Модерация MVP детерминирована и работает без
   внешней модели. Прежняя стадия стояла на `BLOCKED_QWEN_RUNTIME_CONFIG`;
   если внешняя модель нужна как дополнение, это отдельная задача, и MVP от
   неё больше не зависит.

4. **Режим SEO для каждого сайта.** По умолчанию `user_initiated`. В этом
   режиме небольшой сдвиг раскладки неизбежен: высота ветки неизвестна до
   запроса. Измеренный вклад — 0.097 при пороге 0.1 и 0.0 без виджета.
   Сайту, которому нужен нулевой сдвиг, нужен режим `ssr_*`, а он включается
   только вместе с публикацией.

5. **Значение `--cp-reserve` по сайту**, если 320 px по умолчанию не подходит
   под типичную длину ветки.

## Что проверить своими руками

```bash
cd /home/claude/wt-community-comments-platform-01
python3 -m pytest tests/unit/comments_platform/ -q
npx playwright test --config=playwright.comments.config.js
python3 scripts/comments_platform_evidence.py --check
python3 scripts/comments_platform_artifact.py --check
```

Отчёт называет команду, фактический код возврата и путь к артефакту. Если
какая-то строка выше не воспроизводится — это дефект отчёта, а не стилистика.
