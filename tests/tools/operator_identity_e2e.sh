#!/usr/bin/env bash
# Прогон операторского E2E по каждому движку с чистого состояния.
#
# Состояние сбрасывается между движками намеренно: первый прогон заводит
# администратора и тем закрывает окно начальной настройки. Второй движок в том
# же состоянии войти токеном уже не сможет — и это правильное поведение.
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим
# именем, а пытается выполнить строку как команду.
set -Eeuo pipefail
ROOT="${1:?нужен корень рабочего каталога}"
PORT="${2:-8899}"
TOKEN="${3:-boot}"
PY="${PYTHON:-/srv/site-factory/repo/.venv/bin/python}"
FAILED=0

for engine in chromium firefox; do
  pkill -f "port ${PORT}" 2>/dev/null || true
  sleep 2
  rm -rf "${ROOT}/var/state/operators"
  ( cd "$ROOT" && SITE_ENGINE_HTTP=1 SITE_ENGINE_API_ENABLED=1 \
      SITE_ENGINE_ENVIRONMENT=test SITE_ENGINE_ADMIN=1 SITE_ENGINE_CONTROL_WRITES=1 \
      SITE_ENGINE_CONTROL_TOKENS="${TOKEN}=read,operators:write,review:write,audit:read,jobs:write,config:write,cache:write" \
      setsid nohup "$PY" -m factory.site_engine.api.server --root . \
      --host 127.0.0.1 --port "$PORT" > "/tmp/admin-${PORT}.log" 2>&1 < /dev/null & )
  for _ in $(seq 1 25); do
    if curl -sf -o /dev/null --max-time 3 "http://127.0.0.1:${PORT}/admin"; then break; fi
    sleep 1
  done
  echo "### движок ${engine}"
  node "${ROOT}/tests/tools/operator_identity_e2e.js" \
    "http://127.0.0.1:${PORT}" "$TOKEN" "$engine" || FAILED=$((FAILED + 1))
done

pkill -f "port ${PORT}" 2>/dev/null || true
echo "движков с провалами: ${FAILED}"
exit "$FAILED"
