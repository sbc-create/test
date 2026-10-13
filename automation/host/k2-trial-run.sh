#!/usr/bin/env bash
# Пробный прогон ячейки на новом узле БЕЗ root: клон из бандла, запуск на
# высоком порту в домашнем каталоге, прогрев, измерение памяти, остановка.
#
# Зачем именно так. Окончательное число витрин на узле решается измерением, а
# не оценкой, и измерить надо ДО того, как владелец создаст учётные записи и
# включит службы: иначе первая же витрина может съесть больше, чем планировали
# на восемь. Ничего привилегированного не требуется — всё в /home/k2deploy.
#
# Имена переменных ЛАТИНИЦЕЙ намеренно: кириллица в именах переменных оболочки
# падает в работе, а `bash -n` её пропускает. Проверено на этом же сценарии —
# первая редакция ответила «порт=19125: command not found».
#
# Запуск:  k2-trial-run.sh <site_id> <порт> [секунд прогрева]
#
# Печатает строки «ключ=значение»: результат читается и машиной, и человеком.
set -uo pipefail

site="${1:?нужен site_id}"
port="${2:?нужен порт}"
warm="${3:-20}"
stand="$HOME/trial/$site"
data_src="$HOME/stage/data/$site"
bundle="$HOME/stage/bundles/$site.bundle"
log="$stand/run.log"

now_utc() { date -u +%Y-%m-%dT%H%MZ; }

[ -f "$bundle" ] || { echo "error=нет бандла $bundle"; exit 2; }
[ -d "$data_src" ] || { echo "error=нет данных $data_src"; exit 2; }

rm -rf "$stand"
mkdir -p "$stand"
echo "started_at=$(now_utc)"
echo "site=$site"
echo "port=$port"

# 1. Код из бандла: он самодостаточен, сеть не нужна.
if ! git clone --quiet "$bundle" "$stand/src" 2>"$stand/clone.log"; then
  echo "error=клон бандла не удался"
  sed 's/^/log| /' "$stand/clone.log" | tail -3
  exit 1
fi
echo "branch=$(git -C "$stand/src" rev-parse --abbrev-ref HEAD)"
echo "head=$(git -C "$stand/src" rev-parse --short=12 HEAD)"
echo "files=$(git -C "$stand/src" ls-files | wc -l)"

# 2. Данные — КОПИЕЙ: пробный прогон не вправе менять доставленный набор.
cp -a "$data_src" "$stand/data"
cd "$stand/src" || exit 1
nohup python3 run.py --port "$port" --data-dir "$stand/data" >"$log" 2>&1 &
app_pid=$!
echo "pid=$app_pid"

# 3. Готовность: ждём healthz не дольше 120 секунд.
ready=0
for _ in $(seq 1 120); do
  if curl -fsS --max-time 3 "127.0.0.1:$port/healthz" >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
echo "ready=$ready"
if [ "$ready" = 0 ]; then
  echo "error=витрина не ответила на healthz за 120 с"
  tail -8 "$log" | sed 's/^/log| /'
  kill "$app_pid" 2>/dev/null
  exit 1
fi

# 4. Прогрев: основные поверхности, как у посетителя.
for route in "/" "/catalog/" "/search/?q=%D0%B2%D0%B5%D1%82%D0%B5%D1%80" "/collections/" "/healthz"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "127.0.0.1:$port$route")
  secs=$(curl -s -o /dev/null -w '%{time_total}' --max-time 25 "127.0.0.1:$port$route")
  bytes=$(curl -s -o /dev/null -w '%{size_download}' --max-time 25 "127.0.0.1:$port$route")
  echo "route $route code=$code time=$secs bytes=$bytes"
done

# Карточка произведения: идентификатор берётся ИЗ КАТАЛОГА, не придумывается.
title=$(python3 - "$stand/data/$site-catalog.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
first = (data.get("items") or [{}])[0]
print(first.get("slug") or first.get("id") or "")
PY
)
echo "title_probe=$title"
if [ -n "$title" ]; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "127.0.0.1:$port/title/$title/")
  bytes=$(curl -s -o /dev/null -w '%{size_download}' --max-time 25 "127.0.0.1:$port/title/$title/")
  echo "route /title/<первый>/ code=$code bytes=$bytes"
fi

sleep "$warm"

# 5. Память после прогрева — по всему дереву процессов витрины.
rss=0
for p in $(pgrep -f "run.py --port $port") $(pgrep -f "lords-frontend.py --port $port") "$app_pid"; do
  if [ -r "/proc/$p/status" ]; then
    k=$(awk '/^VmRSS:/{print $2}' "/proc/$p/status" 2>/dev/null)
    [ -n "$k" ] && rss=$((rss + k))
  fi
done
echo "rss_mib=$((rss / 1024))"
echo "mem_available_mib=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)"
echo "load=$(cut -d' ' -f1-3 /proc/loadavg)"

# 6. Индексационные заголовки приложения: витрина обязана оставаться закрытой.
robots=$(curl -s -D - -o /dev/null --max-time 10 "127.0.0.1:$port/" | grep -i "x-robots-tag" | tr -d '\r')
echo "x_robots_from_app=${robots:-нет заголовка от приложения}"

# 7. Остановка. Код стенда остаётся для разбора, данные — в stage.
kill "$app_pid" 2>/dev/null
pkill -f "lords-frontend.py --port $port" 2>/dev/null
pkill -f "run.py --port $port" 2>/dev/null
sleep 2
echo "still_running=$(pgrep -cf "port $port")"
echo "finished_at=$(now_utc)"
