---
name: site-deploy
description: Выкатить сайт на staging или production через проверенный wrapper. Использовать только после зелёного QA; production дополнительно требует авторизации в manifest.
allowed-tools: Read, Grep, Glob, Bash(python3 -m factory deploy *), Bash(python3 -m factory verify *), Bash(python3 -m factory status *)
---

# site-deploy

Прямой `ssh`/`scp`/`rsync`/`ansible` запрещён и блокируется хуком. Единственный путь —
`python3 -m factory deploy`.

Перед запуском проверь и назови вслух:
1. `environment` пакета и совпадение с флагом `--environment`.
2. `production_authorized` — для production обязано быть `true`, иначе
   `BLOCKED_AUTHORIZATION` и ноль мутаций.
3. Лицензия DLE покрывает домен второго уровня (`BLOCKED_LICENSE` иначе).
4. Цель есть в `inventory/targets.yaml`, host key запинен.
5. Backup БД и mutable data выполнен, restore проверялся.
6. Staging QA зелёный. **Успешный staging не является разрешением на production.**

Порядок: `deploy --dry-run` → `deploy` → `verify` (production smoke) → повторный smoke
после короткого наблюдения. DNS cutover — отдельный шаг после health check origin и TLS.

Любая мутация журналируется в `var/audit/audit.jsonl` с redacted output.
