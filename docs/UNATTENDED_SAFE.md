# UNATTENDED_SAFE

Владелец заходит редко. Обычные разрешённые действия не должны останавливаться на
`Allow Bash?`. Это **не** разрешение на `bypassPermissions` или root.

## Три слоя

1. **Permission rules** — `.claude/settings.json` (интерактивно),
   `.claude/settings.unattended.json` (планировщик, `ask` пуст: prompt показать некому,
   поэтому неразрешённое отклоняется, а не подвисает).
2. **Sandbox** — авторазрешение для sandboxed-команд, если доступен в установленной версии.
3. **PreToolUse hook** — `.claude/hooks/pretooluse_guard.py`. Обязателен и fail-closed:
   любая ошибка разбора, неизвестный инструмент или неразобранная конструкция → deny.

Плюс независимый четвёртый слой на уровне бизнес-логики: `guardrails.authorize_mutation`
и `inventory/authorization/*.yaml`. Разрешение инструмента не заменяет manifest,
manifest не разрешает обойти hook.

## Что движок ловит

Разбор команды идёт по сегментам (`;`, `&&`, `||`, `|`), с рекурсией в подстановки
`$(...)`/backticks, `sh -c`, `xargs`, `find -exec`, `timeout`/`nohup`; снимаются
префиксы `env` и `VAR=value`; дополнительно проверяется разкавыченная форма
(`e''cho` → `echo`). Пути нормализуются, `..` и `~` разворачиваются.

Всегда deny: рекурсивное удаление вне disposable-путей, удаление сайта/домена/бэкапа,
`DROP`/`TRUNCATE`/деструктивные миграции, force push и переписывание истории,
чтение/печать/копирование секретов (включая `os.environ['*_TOKEN']` и `process.env.*`),
`sudo`/root/SSH-демон/firewall/системные пакеты, отключение hooks/tests/sandbox,
DNS вне утверждённой зоны, новые платные сервисы, production без manifest,
`curl | sh` и обфускация.

## Проверка

```bash
python3 -m seo_operator.cli permissions test   # 72 кейса корпуса
python3 -m pytest tests/test_permissions.py -q # + попытки обхода и сам hook
claude doctor                                  # выполняет владелец
/status                                        # активные sources в интерактивной сессии
```

Разрешённые команды проходят без prompt; запрещённые получают явный deny с названием
правила, а не зависают. Если sandbox или hook enforcement недоступны — unattended mode
не запускается до восстановления защитного слоя.

## При блокировке

`BLOCKED_AUTHORIZATION` записывается, независимые задачи продолжаются, вопрос попадает
в один агрегированный отчёт владельцу. Один и тот же неизменившийся блокер повторно
не запрашивается (`Store.record_blocker`).
