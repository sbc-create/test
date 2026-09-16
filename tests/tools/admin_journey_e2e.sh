#!/usr/bin/env bash
# Полный редакционный путь по каждому движку.
#
# Сервер поднимается только через with_test_server.sh: свободный порт, PID
# собственного дочернего процесса, сверка cmdline, проверка боевой службы.
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим
# именем, а пытается выполнить строку как команду.
set -Eeuo pipefail
ROOT="${1:?нужен корень рабочего каталога}"
COORD="${2:-/srv/site-factory/coordination/v1}"
TOKEN="boot"
TOKEN_RO="ro"
# Свой токен на движок. Предел частоты считается на действующее лицо, а его
# состояние лежит в каталоге стенда и переживает перезапуск сервера: один токен
# на оба прогона означал бы, что второй начинается с уже израсходованным
# разрешением и падает не из-за продукта.
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0

for engine in chromium firefox; do
  echo "### движок ${engine}"
  ROOT="$ROOT" \
  SERVER_ENV="SITE_ENGINE_API_ENABLED=1 SITE_ENGINE_ENVIRONMENT=test SITE_ENGINE_ADMIN=1 SITE_ENGINE_CONTROL_WRITES=1 SITE_ENGINE_COORDINATION_DIR=${COORD} SITE_ENGINE_CATALOG_DIR=var/lords/lords/catalog-cache SITE_ENGINE_CONTROL_TOKENS=${TOKEN}-${engine}=read,operators:write,review:write,audit:read,jobs:write,config:write,cache:write|${TOKEN_RO}-${engine}=read,audit:read" \
  bash "${SELF}/with_test_server.sh" \
    bash -c "node '${ROOT}/tests/tools/admin_journey_e2e.js' \"\$TEST_SERVER_BASE\" '${TOKEN}-${engine}' '${TOKEN_RO}-${engine}' '${engine}'" \
    || FAILED=$((FAILED + 1))
done

echo "движков с провалами: ${FAILED}"
exit "$FAILED"
