#!/usr/bin/env bash
# DNS — Tier 3. Обёртка существует только чтобы явно и одинаково отказывать
# без отдельной авторизации владельца на конкретную zone+record+action.
set -euo pipefail
echo "BLOCKED_AUTHORIZATION: DNS-операции требуют отдельной явной авторизации владельца (Tier 3, AUTOMATION_POLICY.yaml)." >&2
exit 3
