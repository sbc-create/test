# Нормативные требования мастер-промпта (экстракт с идентификаторами)

Источник: SRC-USER-MASTERPROMPT («Фабрика сайтов на DLE: мастер-промпт для Claude Code v1.1»,
21.08.2026). Это **производный экстракт**, а не копия: каждому требованию присвоен ID,
по которому `tests/test_traceability.py` проверяет наличие связанного теста. Оригинал
остаётся сообщением пользователя; при необходимости положите его дословно рядом.

| ID | Требование | Раздел | Тест |
|----|------------|--------|------|
| REQ-MODE-A | Режим A: инвентаризация read-only, официальные источники, knowledge pack, freeze с контрольными суммами | §1 | `tests/unit/test_knowledge_freeze.py` |
| REQ-MODE-B | Режим B: работа только на замороженной базе, пакете и разрешённых endpoint; пустое поле ≠ умолчание | §1 | `tests/unit/test_validation.py` |
| REQ-DLE-VERSION | Базовая версия — DLE 20.0; автопереход запрещён | §3.1 | `tests/unit/test_schemas.py` |
| REQ-DLE-DIST | Только официальный переданный дистрибутив; SHA-256 фиксируется; архив не в git | §3.2–3.3 | `tests/unit/test_repo_hygiene.py` |
| REQ-DLE-LICENSE | Одна лицензия = один домен второго уровня и его поддомены; иначе `BLOCKED_LICENSE` | §3.4 | `tests/unit/test_licensing.py` |
| REQ-DLE-CORE | Ядро DLE не модифицируется; расширения — через plugin/VFS и шаблоны | §3.5 | `tests/unit/test_repo_hygiene.py` |
| REQ-DLE-ISOLATION | Отдельные БД и DB user на сайт | §3.6 | `tests/unit/test_schemas.py` |
| REQ-DLE-PATHS | Изменяемые пути берутся из официальной документации, не угадываются | §3.8 | `tests/unit/test_blueprint_profile.py` |
| REQ-DLE-PERMS | world-writable в production запрещены | §3.9 | `tests/unit/test_repo_hygiene.py` |
| REQ-BACKUP | Backup перед мутацией; восстановление проверяется, а не декларируется | §3.10, §8.8 | `tests/integration/test_backup_restore.py` |
| REQ-IDEMPOTENT | Повторный запуск не создаёт дубль сайта, БД, cron, сертификата, релиза | §3.11 | `tests/integration/test_idempotency.py` |
| REQ-INSTALLER | Installer удаляется/блокируется после установки | §3.12 | `tests/unit/test_repo_hygiene.py` |
| REQ-CRON | Cron только из декларативного manifest с lock, timeout, логом | §3.13 | `tests/unit/test_blueprint_profile.py` |
| REQ-CLAUDE-CONFIG | Короткий CLAUDE.md, scoped rules, skills, agents, hooks; без bypassPermissions | §5 | `tests/unit/test_claude_config.py` |
| REQ-GUARD | Детерминированные запреты: произвольный SSH, деструктив, секреты, firewall/DNS | §5.4 | `tests/unit/test_guard_rules.py` |
| REQ-WRAPPER | Мутации только через проверенный wrapper `factory deploy` | §5.5 | `tests/unit/test_guard_rules.py` |
| REQ-AUDIT | Журнал каждой мутации: job, site, commit, actor, target, время, exit code, redacted output | §5.6 | `tests/unit/test_audit.py` |
| REQ-PACKAGE | Единственный вход — versioned site package со строгой схемой | §6 | `tests/unit/test_schemas.py` |
| REQ-SECRETS | Секреты только через `secret_ref`; не в git, лог, отчёт, скриншот, fixture | §6 | `tests/unit/test_redaction.py` |
| REQ-STATES | Точные статусы конвейера и отказов; без общего failed | §7 | `tests/unit/test_state_machine.py` |
| REQ-LOCK | Lock на site+environment исключает параллельное изменение | §7 | `tests/unit/test_locks.py` |
| REQ-RETRY | Retry только для временных ошибок; backoff, jitter, конечный лимит; конфигурация не ретраится | §7 | `tests/unit/test_retry.py` |
| REQ-QUEUE | Один job семантически один раз даже после restart; quarantine после исчерпания | §7 | `tests/unit/test_queue.py` |
| REQ-DRYRUN | `plan` и `--dry-run` не меняют инфраструктуру | §7 | `tests/integration/test_dry_run.py` |
| REQ-AUTH | `production_authorized=false` → ноль мутаций; staging не открывает production | §7 | `tests/unit/test_authorization.py` |
| REQ-SSH | Least-privilege, host key pinning, узкий sudo-allowlist, scoped DNS-токены | §8 | `tests/unit/test_inventory_security.py` |
| REQ-ATOMIC | Атомарные релизы; переключение после health; предыдущий релиз сохраняется | §8.7 | `tests/integration/test_rollback.py` |
| REQ-EXPOSURE | Закрыты installer, конфиги, бэкапы, `.env`, git-метаданные, debug, листинг каталогов | §8.10 | `tests/integration/test_security_smoke.py` |
| REQ-ENVSEP | Mock-интеграции технически невозможны в production | §8.11 | `tests/unit/test_vk_ads_gating.py` |
| REQ-CONTENT | Контент только из пакета; нет alt — материал не публикуется | §9 | `tests/unit/test_content_rules.py` |
| REQ-VK-RIGHTS | VK: только переданные ID из разрешённого каталога с rights manifest | §9 | `tests/unit/test_validation.py` |
| REQ-VK-UNAVAILABLE | Недоступное видео → контролируемое состояние, подмена запрещена | §9 | `tests/unit/test_content_rules.py` |
| REQ-ADS | Реклама только по переданному contract; SDK-методы не выдумываются | §9 | `tests/unit/test_vk_ads_gating.py` |
| REQ-A11Y | Клавиатура, focus, labels, контраст, WCAG 2.2 AA; брейкпоинты 360–1440 | §9 | `tests/e2e/accessibility.spec.js` |
| REQ-SEO-MATRIX | Матрица индексируемости строится до шаблонов и покрывает все типы страниц | §9A | `tests/unit/test_seo_matrix.py` |
| REQ-SEO-URL | Единая политика URL, 301 без цепочек, абсолютный self-canonical | §9A | `tests/unit/test_url_policy.py` |
| REQ-SEO-PAGINATION | Серверная пагинация ссылками, self-canonical, page 1 один URL, out-of-range 404 | §9A | `tests/integration/test_pagination.py` |
| REQ-SEO-FACETS | Индексируемые фасеты только из allowlist; параметры нормализуются | §9A | `tests/unit/test_validation.py` |
| REQ-SEO-META | Уникальные title/H1/description; крошки совпадают с BreadcrumbList | §9A | `tests/unit/test_seo_lint.py` |
| REQ-SEO-SITEMAP | Sitemap только canonical+indexable+200; staging закрыт авторизацией и noindex | §9A | `tests/integration/test_security_smoke.py` |
| REQ-SEO-SD | JSON-LD только по фактам; VideoObject только при видимом доступном видео | §9A | `tests/unit/test_seo_lint.py` |
| REQ-SEO-QUALITY | Нет scaled content abuse, пустых оболочек, мимикрии | §9A | `tests/unit/test_content_rules.py` |
| REQ-SEO-LINKS | Нет orphan-страниц; ссылки crawlable; mobile = desktop по контенту | §9A | `tests/integration/test_crawl.py` |
| REQ-SEO-BLOCK | `BLOCKED_SEO` при критических нарушениях | §9A | `tests/unit/test_seo_lint.py` |
| REQ-QA-LEVELS | Schema, unit, static, dry-run, integration, идемпотентность, restore, E2E, a11y, visual, SEO, security, performance, smoke | §10 | `tests/run-all.sh` |
| REQ-DOD | Запрет `DONE` при провале критических проверок и при отчёте о незапущенной проверке | §10 | `tests/unit/test_job_result.py` |
| REQ-INPUT-REQUEST | Один пакет недостающих данных вместо череды вопросов | §13 | `tests/unit/test_input_request.py` |
| REQ-CDNVH | CDN Video Hub не интегрируется; создана extension point | §11 | `tests/unit/test_repo_hygiene.py` |
