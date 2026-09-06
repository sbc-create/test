#!/usr/bin/env bash
# Приёмка контура сайта по каждому движку.
#
# Сервер поднимается только через with_test_server.sh: свободный порт, PID
# собственного дочернего процесса, сверка cmdline, проверка боевой службы после.
#
# Свой токен на движок: предел частоты считается на действующее лицо, а его
# состояние переживает перезапуск сервера.
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим
# именем, а пытается выполнить строку как команду.
set -Eeuo pipefail
ROOT="${1:?нужен корень стенда}"
SITE="${2:?нужна витрина}"
NEIGHBOUR="${3:?нужна соседняя витрина}"
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0

for engine in chromium firefox; do
  echo "### движок ${engine}"
  ROOT="$ROOT" \
  SERVER_ENV="SITE_ENGINE_API_ENABLED=1 SITE_ENGINE_ENVIRONMENT=test SITE_ENGINE_ADMIN=1 SITE_ENGINE_CONTROL_WRITES=1 SITE_ENGINE_CATALOG_DIR=var/lords/lords/catalog-cache SITE_ENGINE_CONTROL_TOKENS=fleet-${engine}=read,operators:write,review:write,audit:read,jobs:write,config:write,cache:write" \
  bash "${SELF}/with_test_server.sh" \
    bash -c "node '${SELF}/site_admin_fleet_e2e.js' \"\$TEST_SERVER_BASE\" '${SITE}' '${NEIGHBOUR}' '${engine}'" \
    || FAILED=$((FAILED + 1))
done

echo "движков с провалами: ${FAILED}"
exit "$FAILED"
