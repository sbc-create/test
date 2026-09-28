#!/usr/bin/env bash
# Мастер заведения витрины по каждому движку.
#
# Сервер поднимается только через with_test_server.sh.
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим
# именем, а пытается выполнить строку как команду.
set -Eeuo pipefail
ROOT="${1:?нужен корень рабочего каталога}"
TOKEN="boot"
TOKEN_RO="ro"
# Предел частоты считается на действующее лицо, а состояние счётчика лежит в
# каталоге стенда и переживает перезапуск сервера. Один токен на оба движка
# означал бы, что второй прогон начинается с уже израсходованным разрешением —
# и падал бы не из-за продукта.
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0

for engine in chromium firefox; do
  echo "### движок ${engine}"
  ROOT="$ROOT" \
  SERVER_ENV="SITE_ENGINE_API_ENABLED=1 SITE_ENGINE_ENVIRONMENT=test SITE_ENGINE_ADMIN=1 SITE_ENGINE_CONTROL_WRITES=1 SITE_ENGINE_CONTROL_TOKENS=${TOKEN}-${engine}=read,operators:write,review:write,audit:read,jobs:write,config:write,cache:write,sites:create|${TOKEN_RO}-${engine}=read,audit:read" \
  bash "${SELF}/with_test_server.sh" \
    bash -c "node '${ROOT}/tests/tools/new_site_e2e.js' \"\$TEST_SERVER_BASE\" '${TOKEN}-${engine}' '${TOKEN_RO}-${engine}' '${engine}'" \
    || FAILED=$((FAILED + 1))
done

echo "движков с провалами: ${FAILED}"
exit "$FAILED"
