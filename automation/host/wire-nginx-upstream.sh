#!/usr/bin/env bash
# Подключение управляемого upstream к фактической конфигурации nginx.
#
#   sudo bash automation/host/wire-nginx-upstream.sh --site zona-01 [--dry-run]
#
# Зачем
# -----
#
# Исполнитель переключает трафик заменой ОДНОГО файла upstream. На боевом хосте
# конфигурации сайтов проксируют прямо на `127.0.0.1:<порт>`, и такого файла
# никто не читает: запись в него проходит, `nginx -t` доволен, reload
# выполняется — а трафик остаётся на прежней версии. Операция выглядит
# успешной, посетители остаются на старом. Худший исход из возможных.
#
# Что делает
# ----------
#
#   /etc/nginx/cells/<site>.upstream          server 127.0.0.1:<порт>;
#   /etc/nginx/conf.d/site-cells-upstreams.conf   upstream cell_<site> { include …; }
#   конфигурация сайта                        proxy_pass -> http://cell_<site>
#
# Поведение не меняется: upstream с одним server ведёт туда же, куда вёл прямой
# proxy_pass. Меняется только то, что теперь у маршрута есть одна точка, которую
# исполнитель может переставить.
#
# Безопасность перехода
# ---------------------
#
# Копия конфигурации снимается до правки. `nginx -t` выполняется ДО reload; не
# прошёл — копия возвращается и reload не делается вовсе. После reload маршрут
# проверяется живым запросом; не ответил — возврат копии и повторный reload.
set -Eeuo pipefail

site=""
dry_run=0
while [ $# -gt 0 ]; do
  case "$1" in
    --site) site="${2:-}"; shift ;;
    --dry-run) dry_run=1 ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$site" ] || { echo "нужен --site" >&2; exit 2; }

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${REPO}/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
NGINX_DIR=/etc/nginx
CELLS="${NGINX_DIR}/cells"
UPSTREAMS="${NGINX_DIR}/conf.d/site-cells-upstreams.conf"
BACKUP_ROOT=/var/backups/site-cells-nginx

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }
run()  { if [ "$dry_run" = 1 ]; then printf '   [сухой прогон] %s\n' "$*"; else "$@"; fi; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"

# Порт и имя upstream берутся из реестра, а не из аргументов: аргументом можно
# попросить что угодно, а реестр — единственный источник правды о размещении.
port="$("$PY" -c "
import json, os, sys
sys.path.insert(0, '$REPO')
from factory.cell import runtime
print(runtime.размещение('$site').port or '')
" 2>/dev/null)" || die "не удалось получить порт $site из реестра"
[ -n "$port" ] || die "в реестре нет порта для $site"

upstream_name="cell_$(printf '%s' "$site" | tr '.-' '__')"
upstream_file="${CELLS}/${site}.upstream"

# Конфигурация сайта — та, где этот порт назван. Ищем по факту, а не по
# соглашению об именах: имена файлов в этом контуре не единообразны.
# Ищем ТОЛЬКО там, откуда nginx читает: sites-available он не включает
# (в nginx.conf стоит `include sites-enabled/*`), и правка там меняла бы файл,
# который никто не исполняет, зато разводила бы копии. На этом хосте
# sites-enabled — обычные файлы, а не ссылки, поэтому расхождение реально.
mapfile -t configs < <(grep -rl "proxy_pass http://127\.0\.0\.1:${port}\b" \
    "${NGINX_DIR}/sites-enabled" "${NGINX_DIR}/conf.d" "${NGINX_DIR}/lords" \
    --include='*.conf' 2>/dev/null | grep -v -e '\.bak' -e '\.before' || true)
if [ "${#configs[@]}" -eq 0 ]; then
  if grep -rqs "proxy_pass http://${upstream_name}\b" "${NGINX_DIR}"; then
    log "уже подключено: конфигурация ссылается на ${upstream_name}"
    exit 0
  fi
  die "не нашёл конфигурации nginx с proxy_pass на 127.0.0.1:${port}"
fi
log "конфигурации сайта: ${configs[*]}"

log "файл upstream и общий блок"
run install -d -m 0755 "$CELLS"
if [ "$dry_run" = 0 ]; then
  printf 'server 127.0.0.1:%s;\n' "$port" > "${upstream_file}"
else
  printf '   [сухой прогон] %s <- server 127.0.0.1:%s;\n' "$upstream_file" "$port"
fi
if ! grep -qs "upstream ${upstream_name}" "$UPSTREAMS" 2>/dev/null; then
  if [ "$dry_run" = 0 ]; then
    touch "$UPSTREAMS"
    {
      printf '\n# %s: точка переключения трафика. Содержимое include меняет\n' "$site"
      printf '# исполнитель при выкладке; здесь только объявление.\n'
      printf 'upstream %s {\n    include %s;\n}\n' "$upstream_name" "$upstream_file"
    } >> "$UPSTREAMS"
  else
    printf '   [сухой прогон] добавить upstream %s в %s\n' "$upstream_name" "$UPSTREAMS"
  fi
fi

log "резервная копия и правка proxy_pass"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run install -d -m 0700 "${BACKUP_ROOT}/${stamp}"
for conf_file in "${configs[@]}"; do
  run cp -p "$conf_file" "${BACKUP_ROOT}/${stamp}/$(basename "$conf_file")"
  if [ "$dry_run" = 0 ]; then
    sed -i "s|proxy_pass http://127\.0\.0\.1:${port}\b|proxy_pass http://${upstream_name}|g" "$conf_file"
  else
    printf '   [сухой прогон] %s: proxy_pass -> http://%s\n' "$conf_file" "$upstream_name"
  fi
done

restore() {
  printf '\033[33m[!]\033[0m возврат конфигурации из %s\n' "${BACKUP_ROOT}/${stamp}" >&2
  for conf_file in "${configs[@]}"; do
    cp -p "${BACKUP_ROOT}/${stamp}/$(basename "$conf_file")" "$conf_file" || true
  done
  nginx -t >/dev/null 2>&1 && nginx -s reload || true
}

if [ "$dry_run" = 1 ]; then
  echo
  echo "сухой прогон завершён: ничего не менялось"
  exit 0
fi

log "проверка конфигурации"
if ! nginx -t; then
  restore
  die "nginx -t не прошёл; конфигурация возвращена, reload не делался"
fi

log "перезагрузка и проверка маршрута живым запросом"
nginx -s reload
ok=0
for _ in $(seq 1 20); do
  if curl -fsS --max-time 5 -o /dev/null "http://127.0.0.1:${port}/healthz"; then ok=1; break; fi
  sleep 1
done
[ "$ok" = 1 ] || { restore; die "витрина не отвечает после reload; конфигурация возвращена"; }

log "готово: маршрут $site идёт через $upstream_name (сейчас 127.0.0.1:${port})"
