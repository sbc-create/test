---
paths:
  - "factory/**"
  - "automation/**"
  - ".claude/hooks/**"
  - "inventory/**"
---

# Безопасность

- Секреты только через `secret_ref`. Значение секрета не попадает в git, лог, отчёт,
  скриншот, fixture и prompt. Любой вывод перед записью проходит `factory.redaction`.
- Прямой `ssh`/`scp`/`rsync`/`ansible` из агента запрещён — только `factory deploy`.
- Deploy-пользователь least-privilege, не root. `sudo` — только точные wrapper-команды
  из `inventory/ssh-hosts.yaml: sudo_allowlist`.
- Host key pinning обязателен; strict host key checking не отключается.
- DNS-токены ограничены нужными зонами и операциями.
- Production, staging и test secrets разделены. Mock-интеграции технически невозможны
  в production (проверяется валидатором и тестом).
- Публично недоступны: конфиги, бэкапы, installer, служебные manifest, `.env`,
  git-метаданные, debug endpoints, логи, directory listing.
- Каждая команда, меняющая production, журналируется: job ID, site ID, commit, actor,
  target, время, exit code, redacted output.
