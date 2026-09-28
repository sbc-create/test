#!/usr/bin/env bash
# Наблюдение за пилотом флота: снимок каждую минуту.
#
# Замеряется то, по чему принимают решение о раскатке: готовность, задержка,
# память, перезапуски, ответ витрины и ответ админки витрины. Пилот, о котором
# известно только «поднялся», ничего не доказывает.
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим
# именем, а пытается выполнить строку как команду.
set -Eeuo pipefail
BASE="${1:?нужен адрес пилота}"
SITE="${2:?нужна витрина}"
MINUTES="${3:-30}"
PIDFILE="${4:-}"
OUT="${5:-/tmp/fleet-pilot-watch.log}"
PROD_UNIT="site-factory-control-api.service"

echo "начало $(date -u +%H:%M:%S) база=$BASE витрина=$SITE минут=$MINUTES" | tee "$OUT"
for i in $(seq 1 "$MINUTES"); do
  ts=$(date -u +%H:%M:%S)
  ready=$(curl -s -o /dev/null -w '%{http_code}:%{time_total}' --max-time 5 "$BASE/api/v1/ready" || echo "000:0")
  admin=$(curl -s -o /dev/null -w '%{http_code}:%{time_total}' --max-time 5 "$BASE/s/$SITE/admin" || echo "000:0")
  health=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$BASE/api/v1/health" || echo "000")
  rss="n/a"
  if [ -n "$PIDFILE" ] && [ -r "$PIDFILE" ]; then
    pid=$(cat "$PIDFILE" 2>/dev/null || echo "")
    if [ -n "$pid" ] && [ -r "/proc/$pid/status" ]; then
      rss=$(awk '/VmRSS/{print $2}' "/proc/$pid/status")
    fi
  fi
  prod=$(systemctl is-active "$PROD_UNIT" 2>/dev/null || echo "unknown")
  restarts=$(systemctl show "$PROD_UNIT" -p NRestarts --value 2>/dev/null || echo "?")
  echo "$ts ready=$ready admin=$admin health=$health rss_kb=$rss prod=$prod restarts=$restarts" | tee -a "$OUT"
  sleep 60
done
echo "конец $(date -u +%H:%M:%S)" | tee -a "$OUT"
