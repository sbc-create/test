---
paths:
  - "factory/targets/**"
  - "factory/state.py"
  - "factory/queue.py"
  - "automation/**"
---

# Деплой и конвейер

- Состояния: `RECEIVED → VALIDATING → READY → BUILDING → BUILT → STAGING_DEPLOY →
  STAGING_QA → AUTHORIZATION_CHECK → PRODUCTION_DEPLOY → PRODUCTION_SMOKE → MONITORING → DONE`.
- Ошибка — всегда точный статус из перечня, не общий `failed`.
- Один job обрабатывается ровно один раз семантически даже после restart. Lock на
  `site+environment` исключает параллельное изменение.
- Каждый шаг идемпотентен и имеет timeout. Retry только для явно временных ошибок:
  exponential backoff + jitter + конечный лимит. Ошибки конфигурации, лицензии, прав и
  авторизации не ретраятся.
- После исчерпания retry — quarantine с root cause и следующими действиями.
- `plan` и `--dry-run` не меняют инфраструктуру ни при каких условиях.
- `production_authorized: false` → `BLOCKED_AUTHORIZATION`, ноль мутаций.
- Успешный staging не является разрешением на production.
- Сбой модели, лимит API или недоступность переводят job в retry-состояние и никогда
  не вызывают повторную публикацию уже применённого релиза.
