#!/usr/bin/env bash
# Прогон приёмки настроек по каждому движку.
#
# Сервер поднимается через with_test_server.sh: свободный порт, PID
# собственного дочернего процесса, сверка cmdline перед остановкой, проверка
# боевой службы после уборки. Никаких pkill и остановок юнитов.
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим
# именем, а пытается выполнить строку как команду.
set -Eeuo pipefail
ROOT="${1:?нужен корень рабочего каталога}"
SITE="${2:-lords-01}"
TOKEN="boot"
TOKEN_RO="ro"
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0

for engine in chromium firefox; do
  echo "### движок ${engine}"
  ROOT="$ROOT" \
  SERVER_ENV="SITE_ENGINE_API_ENABLED=1 SITE_ENGINE_ENVIRONMENT=test SITE_ENGINE_ADMIN=1 SITE_ENGINE_CONTROL_WRITES=1 SITE_ENGINE_CONTROL_TOKENS=${TOKEN}=read,operators:write,review:write,audit:read,jobs:write,config:write,cache:write|${TOKEN_RO}=read,audit:read" \
  bash "${SELF}/with_test_server.sh" \
    bash -c "SETTINGS_SITE='${SITE}' SETTINGS_SECRET=\"\${SETTINGS_SECRET:-}\" node '${ROOT}/tests/tools/admin_settings_e2e.js' \"\$TEST_SERVER_BASE\" '${TOKEN}' '${TOKEN_RO}' '${engine}'" \
    || FAILED=$((FAILED + 1))
done

echo "движков с провалами: ${FAILED}"
exit "$FAILED"
