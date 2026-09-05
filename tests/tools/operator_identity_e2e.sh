#!/usr/bin/env bash
# Прогон операторского E2E по каждому движку с чистого состояния.
#
# Состояние сбрасывается между движками намеренно: первый прогон заводит
# администратора и тем закрывает окно начальной настройки. Второй движок в том
# же состоянии войти токеном уже не сможет — и это правильное поведение.
#
# Сервер поднимается ТОЛЬКО через with_test_server.sh. Раньше здесь стояло
# `pkill -f "port ${PORT}"`: шаблон совпадал бы с любым процессом, у которого в
# командной строке есть тот же номер порта, включая чужой. Инцидент 004
# случился ровно от такой команды.
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим
# именем, а пытается выполнить строку как команду.
set -Eeuo pipefail
ROOT="${1:?нужен корень рабочего каталога}"
TOKEN="${2:-boot}"
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0

for engine in chromium firefox; do
  rm -rf "${ROOT}/var/state/operators"
  echo "### движок ${engine}"
  ROOT="$ROOT" \
  SERVER_ENV="SITE_ENGINE_API_ENABLED=1 SITE_ENGINE_ENVIRONMENT=test SITE_ENGINE_ADMIN=1 SITE_ENGINE_CONTROL_WRITES=1 SITE_ENGINE_CONTROL_TOKENS=${TOKEN}=read,operators:write,review:write,audit:read,jobs:write,config:write,cache:write" \
  bash "${SELF}/with_test_server.sh" \
    bash -c "node '${ROOT}/tests/tools/operator_identity_e2e.js' \"\$TEST_SERVER_BASE\" '${TOKEN}' '${engine}'" \
    || FAILED=$((FAILED + 1))
done

echo "движков с провалами: ${FAILED}"
exit "$FAILED"
