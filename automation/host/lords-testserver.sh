#!/usr/bin/env bash
# Тестовый экземпляр витрины: с ограничением памяти, сроком жизни и уборкой.
#
# Зачем отдельный запуск. Прогон визуального ремонта 2026-09-20 поднял четыре
# витрины на портах 19132-19135 и оборвался. Процессы пережили обрыв, прожили
# сутки и держали память: никто их не убирал, потому что убирать было некому —
# запуск шёл голой командой без ловушки, без срока и без предела.
#
# Здесь закрыты все три дыры:
#
#   * ловушка на EXIT/INT/TERM останавливает потомка при любом выходе, включая
#     обрыв терминала и снятие агента;
#   * `timeout` задаёт предельный срок жизни: переживший его процесс умирает
#     сам, даже если ловушка не отработала (например, kill -9 родителя);
#   * `ulimit -v` ограничивает память ДО запуска, поэтому утечка каталога
#     падает на себе, а не забирает хост.
#
# Порт обязан лежать в тестовом диапазоне: без этого опечатка в одну цифру
# поднимает второй процесс на боевом порту витрины.
#
#     lords-testserver.sh --port 19132 -- [аргументы витрины]
#     lords-testserver.sh --list                # какие тестовые ещё живы
#     lords-testserver.sh --stop-stale          # остановить пережившие прогон
set -euo pipefail

PORT_MIN=19000
PORT_MAX=19999
DEFAULT_TIMEOUT=900        # 15 минут: дольше не живёт ни одна проверка
DEFAULT_MEMORY_KB=1200000  # ~1.2 ГБ, как и предел сборки шаблона
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="$ROOT/automation/host/lords-frontend.py"
PIDDIR="${TMPDIR:-/tmp}/lords-testserver"

port=""
ports=""
life="$DEFAULT_TIMEOUT"
memory="$DEFAULT_MEMORY_KB"
action="run"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --port) port="$2"; shift 2 ;;
    --timeout) life="$2"; shift 2 ;;
    --memory-kb) memory="$2"; shift 2 ;;
    --list) action="list"; shift ;;
    --stop-stale) action="stop-stale"; shift ;;
    --ports) ports="$2"; shift 2 ;;
    --) shift; break ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 64 ;;
  esac
done

# Живые тестовые процессы: только свои, только в тестовом диапазоне портов.
# Чужие процессы и боевые порты этот сценарий не трогает ни при каких условиях.
list_test_servers() {
  local pid cmd owner
  for pid in $(ls /proc 2>/dev/null | grep -E '^[0-9]+$'); do
    [ -r "/proc/$pid/cmdline" ] || continue
    cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
    case "$cmd" in
      *lords-frontend.py*--port\ 19[0-9][0-9][0-9]*)
        owner="$(stat -c %U "/proc/$pid" 2>/dev/null || echo '?')"
        if [ "$owner" = "$(id -un)" ]; then
          echo "$pid|$owner|$cmd"
        fi
        ;;
    esac
  done
}

case "$action" in
  list)
    list_test_servers
    exit 0
    ;;
  stop-stale)
    # Порты называются явно. Остановить «всё тестовое» нельзя: в диапазоне
    # живут процессы соседних заданий, и снимать чужую работу заодно со своей
    # этот сценарий не должен.
    [ -n "$ports" ] || { echo "нужен --ports 19132,19133 — список остановки называется явно" >&2; exit 64; }
    stopped=0
    while IFS='|' read -r pid owner cmd; do
      [ -n "${pid:-}" ] || continue
      pid_port="$(printf '%s' "$cmd" | sed -n 's/.*--port \([0-9]\{1,\}\).*/\1/p')"
      case ",$ports," in
        *",$pid_port,"*) : ;;
        *) echo "пропускаю pid=$pid порт=$pid_port: не в списке остановки"; continue ;;
      esac
      echo "останавливаю pid=$pid владелец=$owner команда=$cmd"
      kill -TERM "$pid" 2>/dev/null || true
      for _ in 1 2 3 4 5; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
      done
      if kill -0 "$pid" 2>/dev/null; then
        kill -KILL "$pid" 2>/dev/null || true
      fi
      stopped=$((stopped + 1))
    done <<< "$(list_test_servers)"
    echo "остановлено: $stopped"
    exit 0
    ;;
esac

[ -n "$port" ] || { echo "нужен --port" >&2; exit 64; }
case "$port" in ''|*[!0-9]*) echo "порт не число: $port" >&2; exit 64 ;; esac
if [ "$port" -lt "$PORT_MIN" ] || [ "$port" -gt "$PORT_MAX" ]; then
  echo "порт $port вне тестового диапазона $PORT_MIN-$PORT_MAX" >&2
  exit 64
fi
[ -f "$FRONTEND" ] || { echo "нет витрины: $FRONTEND" >&2; exit 66; }

mkdir -p "$PIDDIR"
pidfile="$PIDDIR/$port.pid"
child=""

cleanup() {
  local code=$?
  if [ -n "$child" ] && kill -0 "$child" 2>/dev/null; then
    kill -TERM "$child" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "$child" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$child" 2>/dev/null; then
      kill -KILL "$child" 2>/dev/null || true
    fi
  fi
  rm -f "$pidfile"
  exit "$code"
}
trap cleanup EXIT INT TERM

# Предел памяти ставится в подоболочке: ulimit необратим, и применять его к
# самому харнессу значило бы ограничить заодно и уборку.
(
  ulimit -v "$memory"
  exec timeout --signal=TERM --kill-after=10s "$life" \
    python3 "$FRONTEND" --host 127.0.0.1 --port "$port" "$@"
) &
child=$!
echo "$child" > "$pidfile"
echo "тестовая витрина: pid=$child порт=$port срок=${life}s память=${memory}кб"
wait "$child"
