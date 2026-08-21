# Архитектура фабрики

## Карта репозитория

| Каталог | Назначение |
|---------|------------|
| `CLAUDE.md`, `.claude/` | постоянные правила, scoped rules, skills, reviewer-agents, hooks, permissions |
| `knowledge/` | замороженная база знаний: источники, факты, решения, неизвестное, SEO-матрица |
| `schemas/` | `site-package.schema.json` (единственный вход), `job-result.schema.json` |
| `inventory/` | разрешённые цели, SSH-хосты, DNS-зоны, лицензии DLE, дистрибутивы |
| `blueprints/dle20/` | профиль путей, cron-manifest, конфигурация веб-сервера (без архива DLE) |
| `themes/`, `plugins/` | одобренные оригинальные шаблоны и расширения |
| `sites/` | site packages, по каталогу на `site_id` |
| `queue/` | `inbox → processing → done \| failed \| quarantine` |
| `automation/` | Ansible-слой развёртывания и роутер одноразового стенда |
| `factory/` | контроллер: валидация, сборка, рендер, цели, SEO, состояние, очередь, CLI |
| `tests/` | unit, integration, e2e, traceability, полный прогон |
| `docs/`, `adr/` | эксплуатация и архитектурные решения |
| `artifacts/` | отчёты, скриншоты, результаты заданий (без секретов) |
| `var/` | состояние выполнения: сборки, цели, бэкапы, блокировки, аудит (вне git) |

## Поток одного задания

```
sites/<id>/package.yaml
   │
   ├─ validate ──► BLOCKED_INPUT | BLOCKED_LICENSE | BLOCKED_RIGHTS
   │                BLOCKED_SECRET | BLOCKED_ACCESS | BLOCKED_SEO
   ├─ build    ──► var/build/<id>/<build_id>/{public,routes.json,build-manifest.json}
   ├─ deploy   ──► backup → upload → health → switch current → health → prune
   ├─ verify   ──► seo-lint, seo-crawl, seo-render, security-smoke,
   │               acceptance-routes, performance-budget
   └─ result   ──► artifacts/jobs/<id>/<job_id>.json (валидируется схемой)
```

Состояния: `RECEIVED → VALIDATING → READY → BUILDING → BUILT → STAGING_DEPLOY →
STAGING_QA → AUTHORIZATION_CHECK → PRODUCTION_DEPLOY → PRODUCTION_SMOKE → MONITORING → DONE`.

Переходы описаны в `factory/state.py::TRANSITIONS` и проверяются тестом: из `STAGING_QA`
нельзя попасть в `PRODUCTION_DEPLOY`, минуя `AUTHORIZATION_CHECK`.

## Ключевые инварианты

1. **Мутация только через wrapper.** Прямой `ssh/scp/rsync/ansible` блокируется
   PreToolUse-хуком (exit 0 + `permissionDecision: deny`) и deny-правилами.
2. **Контентная адресация.** `build_id` меняется при изменении пакета, контента, темы,
   версии матрицы или исходников фабрики.
3. **Ровно один раз.** Повторный запуск завершённого `job_id` возвращает сохранённый
   результат, а не выполняет работу заново.
4. **Блокировка.** `flock` на `site+environment`; снимается ядром при падении процесса.
5. **Проверка = команда + exit code + артефакт.** Схема результата задания не примет
   проверку без всех трёх полей.
6. **Пропуск ≠ успех.** Невыполненная проверка отмечается `passed: false` с
   `severity: major` и обязательной заметкой «приёмка неполная».

## Что осознанно не сделано

- **DLE не устанавливается**: дистрибутив и профиль путей не переданы, а угадывать
  структуру каталогов запрещено (§3.8). Гейт: `BLOCKED_INPUT`.
- **CDN Video Hub не интегрирован**: только extension point (`plugins/cdnvideohub/`).
- **Кросс-браузерный дым только на Chromium**: firefox и webkit в образе отсутствуют,
  и это помечено `SKIPPED`, а не выдано за пройденную проверку.
