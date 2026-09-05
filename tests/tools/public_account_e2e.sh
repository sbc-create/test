#!/usr/bin/env bash
# Публичный контур учётной записи: прогон по каждому движку с чистого состояния.
#
# Состояние сбрасывается между движками: адреса генерируются с меткой движка,
# но каталог писем общий, и остатки прошлого прогона мешали бы читать ссылку.
#
# Сервер поднимается ТОЛЬКО через with_test_server.sh: он выбирает свободный
# порт, запоминает PID собственного дочернего процесса, сверяет cmdline перед
# остановкой и проверяет боевую службу после уборки. Прежний `pkill -f "port
# ${PORT}"` совпадал бы с любым чужим процессом, в командной строке которого
# есть тот же номер.
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим
# именем, а пытается выполнить строку как команду.
set -Eeuo pipefail
ROOT="${1:?нужен корень рабочего каталога}"
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0

for engine in chromium firefox; do
  SINK="$(mktemp -d "/tmp/mailsink-${engine}-XXXXXX")"
  rm -rf "${ROOT}/var/state/accounts"
  echo "### движок ${engine}"
  ROOT="$ROOT" \
  SERVER_ENV="SITE_ENGINE_API_ENABLED=1 SITE_ENGINE_ENVIRONMENT=test SITE_ENGINE_CONTROL_WRITES=1 SITE_ENGINE_ACCOUNTS_SITE=lords-01 SITE_ENGINE_ACCOUNTS_ALLOW_CAPTURE_MAILER=1 SITE_ENGINE_MAIL_CAPTURE_DIR=${SINK} SITE_ENGINE_CONTROL_TOKENS=boot=read" \
  bash "${SELF}/with_test_server.sh" \
    bash -c "node '${ROOT}/tests/tools/public_account_e2e.js' \"\$TEST_SERVER_BASE\" '${SINK}' '${engine}'" \
    || FAILED=$((FAILED + 1))
  rm -rf "$SINK"
done

echo "движков с провалами: ${FAILED}"
exit "$FAILED"
