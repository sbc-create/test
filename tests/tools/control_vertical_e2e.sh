#!/usr/bin/env bash
# Браузерная приёмка центра управления по каждому движку.
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим именем.
set -Eeuo pipefail
ROOT="${1:?нужен корень стенда}"
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0

for engine in chromium firefox; do
  ROOT="$ROOT" \
  SERVER_ENV="SITE_ENGINE_API_ENABLED=1 SITE_ENGINE_ENVIRONMENT=test SITE_ENGINE_ADMIN=1 SITE_ENGINE_CONTROL_WRITES=1 SITE_ENGINE_FLEET_ACCOUNTS=1 SITE_ENGINE_CONTROL_TOKENS=cc-${engine}=read,operators:write,review:write,audit:read,jobs:write,config:write" \
  bash "${SELF}/with_test_server.sh" \
    bash -c "node '${ROOT}/tests/tools/control_vertical_e2e.js' \"\$TEST_SERVER_BASE\" '${engine}'" \
    || FAILED=$((FAILED + 1))
done
echo "движков с провалами: ${FAILED}"
exit $(( FAILED > 0 ))
