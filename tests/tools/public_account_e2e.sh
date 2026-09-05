#!/usr/bin/env bash
# Публичный контур учётной записи: прогон по каждому движку с чистого состояния.
#
# Состояние сбрасывается между движками: адреса генерируются с меткой движка,
# но каталог писем общий, и остатки прошлого прогона мешали бы читать ссылку.
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим
# именем, а пытается выполнить строку как команду.
set -Eeuo pipefail
ROOT="${1:?нужен корень рабочего каталога}"
PORT="${2:-8899}"
PY="${PYTHON:-/srv/site-factory/repo/.venv/bin/python}"
SINK="/tmp/mailsink-${PORT}"
FAILED=0

for engine in chromium firefox; do
  pkill -f "port ${PORT}" 2>/dev/null || true
  sleep 2
  rm -rf "${ROOT}/var/state/accounts" "$SINK"
  mkdir -p "$SINK"
  ( cd "$ROOT" && SITE_ENGINE_HTTP=1 SITE_ENGINE_API_ENABLED=1 \
      SITE_ENGINE_ENVIRONMENT=test SITE_ENGINE_CONTROL_WRITES=1 \
      SITE_ENGINE_ACCOUNTS_SITE=lords-01 \
      SITE_ENGINE_ACCOUNTS_ALLOW_CAPTURE_MAILER=1 \
      SITE_ENGINE_MAIL_CAPTURE_DIR="$SINK" \
      SITE_ENGINE_CONTROL_TOKENS="boot=read" \
      setsid nohup "$PY" -m factory.site_engine.api.server --root . \
      --host 127.0.0.1 --port "$PORT" > "/tmp/acc-${PORT}.log" 2>&1 < /dev/null & )
  for _ in $(seq 1 25); do
    if curl -sf -o /dev/null --max-time 3 "http://127.0.0.1:${PORT}/account/register"; then
      break
    fi
    sleep 1
  done
  echo "### движок ${engine}"
  node "${ROOT}/tests/tools/public_account_e2e.js" \
    "http://127.0.0.1:${PORT}" "$SINK" "$engine" || FAILED=$((FAILED + 1))
done

pkill -f "port ${PORT}" 2>/dev/null || true
rm -rf "$SINK"
echo "движков с провалами: ${FAILED}"
exit "$FAILED"
