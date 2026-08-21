# Безопасность

## Границы доверия

| Кто | Что может |
|-----|-----------|
| Claude / агент | читать репозиторий, запускать команды `factory`, тесты, статический анализ |
| `factory deploy` | менять цель из inventory после проверки manifest, лицензии, авторизации, backup |
| Ansible-слой | выполнять только описанные playbook'и от least-privilege пользователя |
| Оператор | подтверждать production флагом `--allow-production`, управлять секретами |

Прямой `ssh/scp/rsync/ansible-playbook`, `sudo`, деструктивный git, `rm -rf` по широким
путям, `mkfs`, `dd`, `DROP DATABASE`, изменение firewall и DNS вне manifest запрещены
двумя независимыми механизмами: deny-правилами `.claude/settings.json` и PreToolUse-хуком
`.claude/hooks/guard_bash.py`. Хук сильнее: exit 2 останавливает вызов до оценки
permission-правил.

## Секреты

- Только `secret_ref`; значения — в переменных окружения или secret-хранилище.
- `factory.redaction` применяется к логам, отчётам, аудиту и артефактам.
- PostToolUse-хук сканирует записанные файлы на приватные ключи и токены.
- `.gitignore` закрывает `.env`, `secrets/`, `*.pem`, `*.key`, `var/`, дистрибутивы DLE.
- Тест `test_repo_hygiene.py` следит, чтобы ничего из этого не попало в индекс git.

## Unattended-запуски

Для автоматических прогонов используется отдельный файл настроек:

```bash
claude -p "…" --bare \
  --settings .claude/settings.unattended.json \
  --allowedTools "Bash(python3 -m factory validate *),Bash(python3 -m factory build *)" \
  --output-format json
```

Он включает sandbox с `failIfUnavailable: true` и `allowUnsandboxedCommands: false`,
закрывает `~/.ssh` и `~/.aws`, оставляет пустой список сетевых доменов. В проектный
`settings.json` это не вносится намеренно: на машине без bubblewrap такой флаг остановит
запуск (в текущем контейнере `bwrap` отсутствует — проверено).

`--bare` обязателен для CI: иначе `claude -p` исполнит hooks и `.mcp.json` из рабочего
каталога без диалога доверия, а произвольному site package такого доверия нет.

## Публичная поверхность сайта

Роутер и шаблон nginx закрывают `.env`, `.git`, `routes.json`, `build-manifest.json`,
`shared/`, бэкапы, установщик, служебные пути; отключают листинг каталогов; ставят
`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP и убирают
`X-Powered-By`. Staging дополнительно закрыт Basic-авторизацией и `X-Robots-Tag: noindex`
— один robots.txt защитой не считается. Проверяется `tests/integration/test_security_smoke.py`.

CSP намеренно строгая (`script-src 'self'`, `style-src 'self'`). Из-за неё пришлось
убрать инлайновые `style` из шаблонов и внедрять axe-core init-скриптом, а не
`addScriptTag`: ослаблять политику ради тестов нельзя — проверяется та же политика,
что уедет в production.
