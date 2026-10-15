#!/usr/bin/env bash
# Измерить витрину на узле БЕЗ её запуска: память, отклик, поверхности.
#
# Чем это НЕ является
# -------------------
#
# Это не запуск витрины. Витрина запускается своим пускателем `run.py`, и он
# отказывает, пока нет `config/player.json` с назначенным publisher_id:
#
#     запуск lordfilm.group остановлен до первого запроса:
#       — нет …/config/player.json: плеер без publisher_id не заработает
#
# Этот отказ — замысел (fail-closed), и он НЕ отключается: ни флагом, ни
# правкой пускателя, ни подставленным номером. Пускатель здесь не меняется
# вовсе.
#
# Что здесь делается
# ------------------
#
# Берётся ТОТ ЖЕ код построения окружения, что у пускателя (его функции
# импортируются из `run.py`, а не переписываются), выполняются его же проверки
# чужих путей и данных — и запускается точка входа для ИЗМЕРЕНИЯ. Проверка
# плеера при этом не выполняется, и отчёт говорит об этом прямо строкой
# `player_check=skipped-by-design`.
#
# Зачем это нужно сейчас. Число витрин на узле решается измерением: у них
# каталог на 121 МиБ, и RSS надо знать ДО того, как владелец создаст учётные
# записи и включит службы. Вторая причина не менее важная: на узле Python 3.12,
# а закрепление ячейки называет 3.10 — работает ли код на узле, словами не
# выяснить.
#
# Имена переменных только ASCII: кириллица в именах переменных оболочки падает
# в работе, а `bash -n` её пропускает (проверено на k2-trial-run.sh).
#
# Запуск на узле:  k2-measure-frontend.sh <site_id> <порт> [секунд прогрева]
set -uo pipefail

site="${1:?нужен site_id}"
port="${2:?нужен порт}"
warm="${3:-15}"
stand="$HOME/measure/$site"
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
echo "player_check=skipped-by-design"
echo "python=$(python3 -V 2>&1)"

if ! git clone --quiet "$bundle" "$stand/src" 2>"$stand/clone.log"; then
  echo "error=клон бандла не удался"
  tail -3 "$stand/clone.log" | sed 's/^/log| /'
  exit 1
fi
echo "head=$(git -C "$stand/src" rev-parse --short=12 HEAD)"

# Данные — КОПИЕЙ: измерение не вправе менять доставленный набор.
cp -a "$data_src" "$stand/data"

# Обёртка: окружение и проверки берутся у самого пускателя, не переписываются.
cat > "$stand/measure.py" <<'PY'
"""Запуск точки входа витрины для ИЗМЕРЕНИЯ: окружение — от её пускателя.

Проверка плеера намеренно не выполняется (витрина так не запускается, см.
k2-measure-frontend.sh). Остальные проверки пускателя выполняются: чужие пути
и наличие данных — иначе измерялась бы не витрина, а случайный набор файлов.
"""
import importlib.util
import os
import sys
from pathlib import Path

корень = Path(sys.argv[1]).resolve()
порт = sys.argv[2]
данные = Path(sys.argv[3]).resolve()

спец = importlib.util.spec_from_file_location("cell_run", корень / "run.py")
пускатель = importlib.util.module_from_spec(спец)
sys.modules["cell_run"] = пускатель
спец.loader.exec_module(пускатель)

конфиг = пускатель.load_config()
окружение = пускатель.environment(конфиг, данные)
окружение.update(пускатель.дополнения(конфиг, данные))

проблемы = пускатель.foreign_paths(окружение, конфиг) + пускатель.check_data(окружение)
if проблемы:
    print("измерение остановлено до первого запроса:", file=sys.stderr)
    for п in проблемы:
        print(f"  — {п}", file=sys.stderr)
    raise SystemExit(78)

os.environ.update(окружение)
точка = корень / "src" / конфиг["entrypoint"]
os.execv(sys.executable, [sys.executable, str(точка), "--port", порт])
PY

cd "$stand/src" || exit 1
nohup python3 "$stand/measure.py" "$stand/src" "$port" "$stand/data" >"$log" 2>&1 &
app_pid=$!
echo "pid=$app_pid"

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

# Прогрев: основные поверхности, как у посетителя.
for route in "/" "/catalog/" "/collections/" "/search/?q=%D0%B2%D0%B5%D1%82%D0%B5%D1%80"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "127.0.0.1:$port$route")
  bytes=$(curl -s -o /dev/null -w '%{size_download}' --max-time 25 "127.0.0.1:$port$route")
  echo "route $route code=$code bytes=$bytes"
done

title=$(python3 - "$stand/data/$site-catalog.json" <<'PY'
import json, sys
данные = json.load(open(sys.argv[1], encoding="utf-8"))
первый = (данные.get("items") or [{}])[0]
print(первый.get("slug") or первый.get("id") or "")
PY
)
if [ -n "$title" ]; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "127.0.0.1:$port/title/$title/")
  bytes=$(curl -s -o /dev/null -w '%{size_download}' --max-time 25 "127.0.0.1:$port/title/$title/")
  echo "route /title/<первый>/ code=$code bytes=$bytes"
  # Плеера у витрины без номера нет — и это должно быть ВИДНО в измерении,
  # а не предполагаться: страница обязана честно сказать о недоступности.
  noaccess=$(curl -s --max-time 25 "127.0.0.1:$port/title/$title/" \
             | grep -c "noaccess\|без доступа\|не подключ" || true)
  echo "player_state_noaccess=$noaccess"
fi

sleep "$warm"

rss=0
for p in $(pgrep -f "measure.py $stand/src $port") $(pgrep -f "lords-frontend.py --port $port") "$app_pid"; do
  if [ -r "/proc/$p/status" ]; then
    k=$(awk '/^VmRSS:/{print $2}' "/proc/$p/status" 2>/dev/null)
    [ -n "$k" ] && rss=$((rss + k))
  fi
done
echo "rss_mib=$((rss / 1024))"
echo "mem_available_mib=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)"
echo "load=$(cut -d' ' -f1-3 /proc/loadavg)"

robots=$(curl -s -D - -o /dev/null --max-time 10 "127.0.0.1:$port/" | grep -i "x-robots-tag" | tr -d '\r')
echo "x_robots_from_app=${robots:-нет заголовка от приложения}"

kill "$app_pid" 2>/dev/null
pkill -f "lords-frontend.py --port $port" 2>/dev/null
pkill -f "measure.py $stand/src $port" 2>/dev/null
sleep 2
echo "still_running=$(pgrep -cf "port $port")"
echo "finished_at=$(now_utc)"
