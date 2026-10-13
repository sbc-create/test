#!/usr/bin/env bash
# Запуск ОДНОЙ витрины на узле K2: данные, выпуск, nginx, служба, проверка.
# Выполняется от root на самом узле. Одна команда на витрину.
#
# Почему скриптом, а не руками. Шагов восемь, порядок значим (данные раньше
# службы, nginx раньше перезагрузки, проверка раньше объявления успеха), а при
# неуспехе нужно вернуть узел в прежнее состояние, а не оставить половину.
# Руками это повторяется восемь раз и расходится на третий.
#
# Что НЕ делает: не трогает DNS, не выпускает сертификат, не ставит блок 443,
# не открывает индексацию. Витрина рождается закрытой — так и остаётся.
#
# Имена переменных только ASCII: кириллица в именах переменных оболочки падает
# в работе, а `bash -n` её пропускает.
#
# Запуск:  k2-launch-site.sh <site_id> [--dry-run]
set -uo pipefail

site="${1:?нужен site_id}"
dry=0
[ "${2:-}" = "--dry-run" ] && dry=1

stage="/home/k2deploy/stage"
manifest="$stage/MANIFEST.json"
#: Порог доступной памяти, ниже которого витрину не запускаем. Согласован и
#: измерен: swap на узле ОТСУТСТВУЕТ, поэтому «чуть-чуть за предел» означает
#: убитый процесс, а не замедление.
mem_floor_mib=2000

log() { printf '==> %s\n' "$*"; }
bad() { printf '[x] %s\n' "$*" >&2; }

[ "$dry" = 1 ] || [ "$(id -u)" = 0 ] || { bad "нужен root"; exit 1; }
[ -f "$manifest" ] || { bad "нет описи $manifest"; exit 2; }

read -r account port unit domain <<EOF
$(python3 - "$manifest" "$site" <<'PY'
import json, sys
опись = json.load(open(sys.argv[1], encoding="utf-8"))
ячейка = (опись.get("cells") or {}).get(sys.argv[2])
if not ячейка:
    raise SystemExit(f"в описи нет {sys.argv[2]}")
print(ячейка["account"], ячейка["port"], ячейка["unit"], ячейка["domain"])
PY
)
EOF
[ -n "${account:-}" ] || { bad "в описи нет данных по $site"; exit 2; }
log "$site: домен $domain, учётка $account, порт $port, юнит $unit"

bundle="$stage/bundles/$site.bundle"
data_src="$stage/data/$site"
conf="$stage/nginx/$site.conf"
root="/srv/$account"
for p in "$bundle" "$data_src" "$conf"; do
  [ -e "$p" ] || { bad "нет $p"; exit 2; }
done

# 1. Память: проверяем ДО установки, а не после запуска.
avail=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)
log "доступно памяти $avail МиБ, порог $mem_floor_mib"
if [ "$avail" -lt "$mem_floor_mib" ]; then
  bad "памяти меньше порога: витрину не запускаем, узел на пределе"
  exit 1
fi

# 2. Плеер. Без publisher_id витрина сама остановится до первого запроса —
# лучше сказать это здесь, чем в журнале через минуту.
player="$stage/player/$site-player.json"
if [ ! -f "$player" ]; then
  bad "нет $player: publisher_id не передан, витрина не стартует (D138/D177)"
  bad "это вход владельца: подставлять чужой или выдуманный номер запрещено"
  exit 3
fi

if [ "$dry" = 1 ]; then
  log "сухой прогон: проверено наличие комплекта, памяти и плеера; ничего не менялось"
  exit 0
fi

# 3. Данные — на место, с правами витрины. Каталог данных принадлежит ТОЛЬКО
# витрине: выкладка в него не пишет.
install -d -m 0750 -o "$account" -g "$account" "$root/data"
for f in "$data_src"/*.json; do
  install -m 0640 -o "$account" -g "$account" "$f" "$root/data/"
done
log "данных установлено: $(ls -1 "$root/data" | wc -l) файлов"

# 4. Выпуск из бандла.
head_sha="$(git ls-remote "$bundle" HEAD | cut -f1 | cut -c1-12)"
release="$root/releases/$head_sha"
install -d -m 2775 -o "$account" -g "$account" "$root/releases"
if [ ! -d "$release" ]; then
  git clone --quiet "$bundle" "$release" || { bad "клон бандла не удался"; exit 1; }
  chown -R "$account:$account" "$release"
fi
install -m 0640 -o "$account" -g "$account" "$player" "$release/config/player.json"
ln -sfn "$release" "$root/current"
chown -h "$account:$account" "$root/current"
log "выпуск $head_sha установлен, current -> $release"

# 5. nginx: конфигурация домена и проверка ДО перезагрузки.
install -m 0644 "$conf" "/etc/nginx/lords/$site.conf"
if ! nginx -t; then
  bad "nginx -t не прошёл: конфигурация витрины снята, соседи не затронуты"
  rm -f "/etc/nginx/lords/$site.conf"
  nginx -t >/dev/null 2>&1
  exit 1
fi
systemctl reload nginx
log "nginx перезагружен"

# 6. Служба.
systemctl enable --now "$unit"
ready=0
for _ in $(seq 1 120); do
  if curl -fsS --max-time 3 "127.0.0.1:$port/healthz" >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
if [ "$ready" = 0 ]; then
  bad "витрина не ответила на healthz за 120 с: откатываюсь"
  systemctl disable --now "$unit"
  rm -f "/etc/nginx/lords/$site.conf"
  nginx -t >/dev/null 2>&1 && systemctl reload nginx
  journalctl -u "$unit" -n 15 --no-pager | sed 's/^/log| /'
  exit 1
fi
log "healthz отвечает"

# 7. Прогрев и измерение — то, чем подтверждается вместимость узла.
for route in "/" "/catalog/" "/search/?q=%D0%B2%D0%B5%D1%82%D0%B5%D1%80"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "127.0.0.1:$port$route")
  printf '    route %-28s code=%s\n' "$route" "$code"
done
sleep 15
main_pid=$(systemctl show -p MainPID --value "$unit")
rss=0
if [ -r "/proc/$main_pid/status" ]; then
  rss=$(awk '/^VmRSS:/{print int($2/1024)}' "/proc/$main_pid/status")
fi
avail_after=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)
log "RSS витрины $rss МиБ; доступно памяти $avail_after МиБ (было $avail)"
if [ "$avail_after" -lt "$mem_floor_mib" ]; then
  bad "после запуска памяти меньше порога $mem_floor_mib МиБ — следующую витрину НЕ запускать"
fi

# 8. Индексация обязана остаться закрытой.
robots=$(curl -s -D - -o /dev/null --max-time 10 -H "Host: $domain" "127.0.0.1:80/" | grep -i "x-robots-tag" | tr -d '\r')
log "x-robots-tag через nginx: ${robots:-ЗАГОЛОВКА НЕТ — проверить include режима}"
log "готово: $site"
