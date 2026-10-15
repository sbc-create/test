#!/usr/bin/env bash
# Сколько витрин узел держит ОДНОВРЕМЕННО: измерение, а не оценка.
#
# Зачем отдельно от `k2-measure-frontend.sh`. Тот измеряет одну витрину: RSS
# после прогрева. Сумма восьми таких чисел — не ответ: часть памяти общая
# (страницы интерпретатора, кеш файлов), а часть, наоборот, появляется только
# под одновременной нагрузкой. Ответ на «сколько витрин влезет» даёт только
# одновременный запуск, и у узла нет swap — превышение не замедляет, а убивает
# процесс.
#
# Что делается: N витрин поднимаются ПО ОЧЕРЕДИ (каждая дожидается готовности),
# после каждой печатается доступная память, затем все гасятся. Пускатель витрин
# не используется и не меняется: проверка плеера остаётся на месте, здесь —
# измерение (см. k2-measure-frontend.sh, `player_check=skipped-by-design`).
#
# Имена переменных только ASCII.
#
# Запуск на узле:  k2-measure-concurrent.sh <site_id> [site_id ...]
set -uo pipefail

base_port=19200
stand_root="$HOME/measure-concurrent"
rm -rf "$stand_root"
mkdir -p "$stand_root"

pids=""
ports=""
started=0
port="$base_port"

echo "mem_available_before_mib=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)"

for site in "$@"; do
  stand="$stand_root/$site"
  bundle="$HOME/stage/bundles/$site.bundle"
  data_src="$HOME/stage/data/$site"
  if [ ! -f "$bundle" ] || [ ! -d "$data_src" ]; then
    echo "$site: нет бандла или данных — пропуск"
    port=$((port + 1))
    continue
  fi
  mkdir -p "$stand"
  git clone --quiet "$bundle" "$stand/src" || { echo "$site: клон не удался"; continue; }
  cp -a "$data_src" "$stand/data"
  # Обёртка берётся у соседнего измерителя — одного на оба сценария: две копии
  # разошлись бы на первой же правке пускателя.
  if [ -f "$HOME/measure/$site/measure.py" ]; then
    cp "$HOME/measure/$site/measure.py" "$stand/measure.py"
  else
    echo "$site: нет $HOME/measure/$site/measure.py — сперва k2-measure-frontend.sh"
    continue
  fi

  nohup python3 "$stand/measure.py" "$stand/src" "$port" "$stand/data" \
      >"$stand/run.log" 2>&1 &
  pid=$!
  ready=0
  for _ in $(seq 1 120); do
    if curl -fsS --max-time 3 "127.0.0.1:$port/healthz" >/dev/null 2>&1; then ready=1; break; fi
    sleep 1
  done
  if [ "$ready" = 0 ]; then
    echo "$site: не ответил на healthz за 120 с"
    tail -4 "$stand/run.log" | sed 's/^/log| /'
    kill "$pid" 2>/dev/null
    port=$((port + 1))
    continue
  fi
  started=$((started + 1))
  pids="$pids $pid"
  ports="$ports $port"
  rss=0
  for p in $(pgrep -f "measure.py $stand/src $port") $(pgrep -f "lords-frontend.py --port $port"); do
    k=$(awk '/^VmRSS:/{print $2}' "/proc/$p/status" 2>/dev/null)
    [ -n "$k" ] && rss=$((rss + k))
  done
  echo "up=$started site=$site port=$port rss_mib=$((rss / 1024)) mem_available_mib=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo) load=$(cut -d' ' -f1 /proc/loadavg)"
  port=$((port + 1))
done

# Под нагрузкой: по одному запросу к каталогу каждой поднятой витрины.
for p in $ports; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "127.0.0.1:$p/catalog/")
  echo "under_load port=$p catalog_code=$code"
done
echo "mem_available_under_load_mib=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)"
echo "load_after=$(cut -d' ' -f1-3 /proc/loadavg)"

for pid in $pids; do kill "$pid" 2>/dev/null; done
for p in $ports; do pkill -f "lords-frontend.py --port $p" 2>/dev/null; done
sleep 3
echo "still_running=$(pgrep -cf 'measure.py' || true)"
echo "mem_available_after_mib=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)"
echo "started=$started"
