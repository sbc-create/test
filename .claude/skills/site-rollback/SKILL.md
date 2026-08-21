---
name: site-rollback
description: Откатить сайт на предыдущий рабочий релиз. Использовать при провале production smoke, деградации мониторинга или по решению оператора.
allowed-tools: Read, Grep, Glob, Bash(python3 -m factory rollback *), Bash(python3 -m factory verify *), Bash(python3 -m factory status *)
---

# site-rollback

1. Зафиксируй причину и текущее состояние: `python3 -m factory status --site <id> --json`.
2. `python3 -m factory rollback --site <id> --environment <env>`:
   переключает симлинк `current` на предыдущий проверенный релиз атомарно.
3. Данные: откат кода **не** откатывает БД автоматически. Если релиз содержал миграцию,
   восстановление БД выполняется из backup этого релиза и подтверждается сравнением.
4. После отката обязателен `verify` — иначе состояние остаётся недоказанным.
5. Итог фиксируется статусом `ROLLED_BACK` и `incident-report`.
