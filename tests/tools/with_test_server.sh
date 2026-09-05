#!/usr/bin/env bash
# Поднять тестовый сервер, выполнить команду, гарантированно убрать за собой.
#
# Осторожность здесь не теоретическая. В прошлом проходе команда
# `pkill -f "site_engine.api.server"` совпала с боевой службой
# site-factory-control-api.service и остановила её примерно на две минуты:
# имя модуля у тестового и боевого процессов одно, отличались только порт и
# рабочий каталог, и ни то ни другое в шаблон не входило.
#
# Отсюда правила, которым подчинён весь сценарий:
#   * порт выбирается свободный и проверяется на владельца ДО запуска;
#   * запоминается PID именно порождённого процесса;
#   * перед остановкой сверяется cmdline: тот ли это процесс;
#   * останавливается только он, сигналом TERM, и только по PID;
#   * pkill, killall и убийство по шаблону не используются нигде;
#   * после уборки проверяется, что боевая служба цела.
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим
# именем, а пытается выполнить строку как команду.
set -Eeuo pipefail

ROOT="${ROOT:?нужен ROOT — корень рабочего каталога}"
PY="${PYTHON:-/srv/site-factory/repo/.venv/bin/python}"
PORT_FROM="${PORT_FROM:-18800}"
PORT_TO="${PORT_TO:-18899}"
PROD_UNIT="${PROD_UNIT:-site-factory-control-api.service}"
PROD_READY="${PROD_READY:-http://127.0.0.1:8790/api/v1/ready}"
SERVER_PID=""
CHOSEN_PORT=""

port_free() {
  local p="$1"
  # Занятость проверяется двумя способами: ss показывает слушающие сокеты,
  # curl — того, кто уже отвечает. Одного признака мало: сокет мог быть
  # открыт другим пространством имён.
  if ss -lnt 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${p}\$"; then
    return 1
  fi
  if curl -s -o /dev/null --max-time 1 "http://127.0.0.1:${p}/" 2>/dev/null; then
    return 1
  fi
  return 0
}

pick_port() {
  local p
  for ((p = PORT_FROM; p <= PORT_TO; p++)); do
    if port_free "$p"; then
      CHOSEN_PORT="$p"
      return 0
    fi
  done
  echo "нет свободного порта в ${PORT_FROM}-${PORT_TO}" >&2
  return 1
}

cleanup() {
  local code=$?
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    # Сверка перед остановкой: PID мог быть переиспользован системой.
    local cmd
    cmd="$(tr '\0' ' ' < "/proc/${SERVER_PID}/cmdline" 2>/dev/null || true)"
    if [[ "$cmd" == *"factory.site_engine.api.server"* && "$cmd" == *"--port ${CHOSEN_PORT}"* ]]; then
      kill -TERM "$SERVER_PID" 2>/dev/null || true
      for _ in $(seq 1 20); do
        kill -0 "$SERVER_PID" 2>/dev/null || break
        sleep 0.5
      done
    else
      echo "ВНИМАНИЕ: PID ${SERVER_PID} больше не наш процесс — не трогаю" >&2
    fi
  fi
  # Боевая служба обязана быть цела. Это и есть проверка, которой не хватало.
  local state
  state="$(systemctl is-active "$PROD_UNIT" 2>/dev/null || true)"
  if [ "$state" != "active" ]; then
    echo "ОТКАЗ: ${PROD_UNIT} в состоянии ${state} после уборки" >&2
    code=1
  elif ! curl -sf -o /dev/null --max-time 5 "$PROD_READY"; then
    echo "ОТКАЗ: ${PROD_READY} не отвечает после уборки" >&2
    code=1
  fi
  exit "$code"
}
trap cleanup EXIT INT TERM

prod_before="$(systemctl show "$PROD_UNIT" -p MainPID --value 2>/dev/null || echo '')"
pick_port

(
  cd "$ROOT"
  # exec обязателен: без него $! — это PID подоболочки, а не питона, и сверка
  # cmdline перед остановкой не находит наш процесс. Тогда уборка честно
  # отказывается его трогать, и тестовый сервер остаётся жить.
  # shellcheck disable=SC2086
  exec env ${SERVER_ENV:-} SITE_ENGINE_HTTP=1 \
      "$PY" -m factory.site_engine.api.server --root . \
      --host 127.0.0.1 --port "$CHOSEN_PORT" > "/tmp/test-server-${CHOSEN_PORT}.log" 2>&1
) &
SERVER_PID=$!

for _ in $(seq 1 30); do
  if curl -sf -o /dev/null --max-time 2 "http://127.0.0.1:${CHOSEN_PORT}/api/v1/health"; then
    break
  fi
  sleep 1
done

prod_after="$(systemctl show "$PROD_UNIT" -p MainPID --value 2>/dev/null || echo '')"
if [ "$prod_before" != "$prod_after" ]; then
  echo "ОТКАЗ: PID боевой службы изменился при запуске тестовой" >&2
  exit 1
fi

export TEST_SERVER_BASE="http://127.0.0.1:${CHOSEN_PORT}"
export TEST_SERVER_PORT="$CHOSEN_PORT"
export TEST_SERVER_PID="$SERVER_PID"
echo "тестовый сервер: ${TEST_SERVER_BASE} (PID ${SERVER_PID})"

"$@"
