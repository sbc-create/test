# DLE Site Factory — постоянные правила

Фабрика повторяемого создания сайтов на DataLife Engine 20.0.
Эксплуатационная документация — по-русски; код, схемы, статусы, команды — по-английски.

## Источники истины (порядок разрешения конфликтов)

1. manifest и файлы конкретного сайта (`sites/<site_id>/`)
2. решения проекта (`knowledge/DECISIONS.md`, `adr/`)
3. замороженная официальная документация (`knowledge/`, freeze — `KNOWLEDGE_FREEZE.yaml`)
4. код и автотесты фабрики
5. сторонние паттерны — необязательная идея, не основание

Конфликт не разрешается молча: запиши его, влияние и безопасное решение в `knowledge/DECISIONS.md`.
Production блокируется, только если конфликт затрагивает лицензию, права на контент,
безопасность, данные, домен, необратимую операцию или результат публикации.

## Режим работы

Фабрика работает в CLOSED_WORLD после `knowledge/KNOWLEDGE_FREEZE.yaml`. Запрещено:
искать контент в интернете, скрапить сайты, придумывать названия, тексты, метаданные,
ID, домены, ключи, изображения, контакты и настройки интеграций, расширять список
SSH-хостов/DNS-зон/доменов по своей инициативе. **Пустое поле — не разрешение
подставить значение по умолчанию, а `BLOCKED_INPUT`.**

## Жёсткие запреты (продублированы hook'ом и deny-правилами)

- Никакого произвольного `ssh`/`scp`/`rsync` в цели. Только `python3 -m factory deploy`.
- Никаких `rm -rf` по широким путям, `mkfs`, `dd` на устройства, `DROP DATABASE`,
  `git push --force`, `git reset --hard`, `git clean -fdx`, неконтролируемого `sudo`,
  изменения firewall и DNS вне manifest.
- Секреты только через `secret_ref`. Значение секрета не попадает в git, лог, отчёт,
  скриншот, fixture и prompt. Файлы `.env`, ключи и `secrets/` не читаются.
- Лицензионный архив DLE не коммитится. Сторонние/nulled-сборки не скачиваются.
- `bypassPermissions` не используется.

## Команды

```bash
python3 -m factory validate  --site <site_id>          # схема + семантика пакета
python3 -m factory plan      --site <site_id>          # план без единой мутации
python3 -m factory build     --site <site_id>          # детерминированная сборка
python3 -m factory deploy    --site <site_id> --environment staging|production
python3 -m factory verify    --site <site_id>          # QA + SEO + security gates
python3 -m factory rollback  --site <site_id> --environment <env>
python3 -m factory status | resume | report | queue …
python3 -m factory seo-plan | seo-lint | seo-crawl | seo-render | seo-report --site <site_id>
bash tests/run-all.sh                                  # полный прогон с чистого состояния
```

## Архитектурная карта

- `factory/` — controller, state machine, locks, retry, redaction, audit, SEO, адаптеры целей
- `schemas/` — `site-package.schema.json` (единственный вход), `job-result.schema.json`
- `knowledge/` — замороженная база знаний; менять только через skill `/research-freeze`
- `inventory/` — разрешённые SSH-хосты, DNS-зоны, лицензии, дистрибутивы, targets
- `blueprints/dle20/` — воспроизводимый blueprint (без лицензионного архива)
- `themes/`, `plugins/` — одобренные оригинальные шаблоны и расширения
- `sites/`, `queue/` — пакеты сайтов и очередь заданий
- `automation/ansible/` — декларативный SSH deployment слой
- `tests/`, `docs/`, `artifacts/`, `adr/`

## Конвейер и статусы

`RECEIVED → VALIDATING → READY → BUILDING → BUILT → STAGING_DEPLOY → STAGING_QA →
AUTHORIZATION_CHECK → PRODUCTION_DEPLOY → PRODUCTION_SMOKE → MONITORING → DONE`

Ошибки — только точными статусами: `BLOCKED_INPUT | BLOCKED_LICENSE | BLOCKED_RIGHTS |
BLOCKED_SECRET | BLOCKED_ACCESS | BLOCKED_AUTHORIZATION | BLOCKED_SEO | QA_FAILED |
DEPLOY_FAILED | ROLLED_BACK | QUARANTINED`.

Успешный staging **не** является разрешением на production. Production требует
`production_authorized: true` в manifest и подходящей лицензии DLE.

## Definition of Done

Нельзя ставить `DONE`, если: провален критический тест; не подтверждена лицензия DLE;
не подтверждены права/происхождение контента; в production попали test/demo данные;
нет бэкапа или не проверен rollback; canonical/TLS/домен указывают не на тот сайт;
обнаружена cross-site утечка; production не авторизован в manifest; отчёт утверждает
проверку, которая фактически не запускалась.

Отчёт содержит команду, фактический exit code и путь к артефакту. Формулировки
«проверено» без запуска — ошибка отчёта, а не стилистика.

## Детальные правила

`.claude/rules/` (подгружаются по путям): `dle-php.md`, `frontend.md`, `content.md`,
`security.md`, `tests.md`, `infrastructure.md`, `deployment.md`, `seo.md`.
Повторяемые процессы — skills: `/research-freeze`, `/site-intake`, `/site-build`,
`/site-qa`, `/site-deploy`, `/site-rollback`, `/site-update`, `/incident-report`.
