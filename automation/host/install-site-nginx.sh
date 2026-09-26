#!/usr/bin/env bash
# Подключение НОВОЙ витрины к nginx: upstream, конфигурация, проверка.
#
#   sudo bash automation/host/install-site-nginx.sh --site zona-02 [--dry-run]
#
# Чем отличается от wire-nginx-upstream.sh
# ----------------------------------------
#
# Тот переписывает `proxy_pass` в УЖЕ существующей конфигурации, найдя её по
# порту. Для витрины, которой в nginx ещё нет вовсе, ему нечего искать: он
# честно отказывает «не нашёл конфигурации с proxy_pass на 127.0.0.1:<порт>».
# Здесь конфигурация ставится с нуля, а upstream создаётся сразу правильным.
#
# Почему без TLS
# --------------
#
# Сертификата без записи DNS не выпустить, а блок 443 со ссылкой на
# несуществующий файл не даст nginx перезагрузиться — то есть уронит и соседей.
# Порядок: эта конфигурация -> запись A -> certbot -> блок 443.
set -Eeuo pipefail

site=""
dry_run=0
new_site=0
while [ $# -gt 0 ]; do
  case "$1" in
    --site) site="${2:-}"; shift ;;
    --new-site) new_site=1 ;;
    --dry-run) dry_run=1 ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$site" ] || { echo "нужен --site" >&2; exit 2; }

SRC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${SRC_ROOT}/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
NGINX_DIR=/etc/nginx
CELLS="${NGINX_DIR}/cells"
UPSTREAMS="${NGINX_DIR}/conf.d/site-cells-upstreams.conf"
TARGET_DIR="${NGINX_DIR}/lords"
SOURCE="${SRC_ROOT}/automation/host/nginx-site/${site}.conf"

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"
[ -f "$SOURCE" ] || die "нет заготовки конфигурации $SOURCE"

# Порт и имя upstream — из реестра, а не из аргументов: реестр единственный
# источник правды о размещении.
port="$("$PY" -c "
import sys; sys.path.insert(0, '$SRC_ROOT')
from factory.cell import runtime
print(runtime.размещение('$site').port or '')
" 2>/dev/null)" || die "не удалось получить порт $site из реестра"
[ -n "$port" ] || die "в реестре нет порта для $site"
upstream_name="cell_$(printf '%s' "$site" | tr '.-' '__')"
upstream_file="${CELLS}/${site}.upstream"

grep -q "proxy_pass http://${upstream_name}\b" "$SOURCE" \
  || die "заготовка не ссылается на ${upstream_name}: маршрут окажется непереключаемым"

log "витрина $site: порт $port, upstream $upstream_name"
if [ "$dry_run" = 1 ]; then
  printf '   [сухой прогон] %s <- server 127.0.0.1:%s\n' "$upstream_file" "$port"
  printf '   [сухой прогон] объявить %s в %s\n' "$upstream_name" "$UPSTREAMS"
  printf '   [сухой прогон] %s -> %s/%s.conf\n' "$SOURCE" "$TARGET_DIR" "$site"
  printf '   [сухой прогон] nginx -t и reload\n'
  exit 0
fi

# Витрина обязана отвечать ДО того, как на неё направят маршрут: иначе первый
# же посетитель получит 502, а причина будет выглядеть как ошибка nginx.
#
# У ПЕРВОГО запуска домена это требование невыполнимо, и не по недосмотру, а
# по кругу в зависимостях: служба не поднимется, пока в хранилище витрины
# ничего нет; положить туда выпуск может только исполнитель; а его
# `switch_route` отказывает, пока файл upstream не включён в конфигурацию
# nginx — то есть пока не выполнен этот сценарий. Круг размыкается здесь,
# потому что терять на новом домене нечего: он никогда ничего не отдавал.
#
# Исключение узкое, и каждое из условий проверяется:
#   * запрошено явно (--new-site);
#   * конфигурации этого домена в nginx ещё нет;
#   * в реестре витрина числится planned, то есть не работает;
#   * файла upstream нет либо он пуст.
# На действующей витрине ни одно из них не выполнится, и проверка останется.
if [ "$new_site" = 1 ]; then
  [ ! -f "${TARGET_DIR}/${site}.conf" ] \
    || die "--new-site, но конфигурация ${TARGET_DIR}/${site}.conf уже есть: это не первый запуск"
  [ ! -s "$upstream_file" ] \
    || die "--new-site, но ${upstream_file} уже заполнен: маршрут существует"
  status="$("$PY" -c "
import json, sys
d = json.load(open('$SRC_ROOT/config/site-cells.json', encoding='utf-8'))
print(next((c.get('status') or '') for c in d.get('cells') or [] if c['site_id'] == '$site'), end='')
")"
  [ "$status" = "planned" ] \
    || die "--new-site, но в реестре $site числится '$status', а не 'planned'"
  log "  первый запуск домена: проверка отклика пропущена, до выпуска будет 502"
else
  "$PY" -c "
import sys, urllib.request
try:
    r = urllib.request.urlopen('http://127.0.0.1:$port/healthz', timeout=10)
    sys.exit(0 if r.status == 200 else 1)
except Exception:
    sys.exit(1)
" || die "витрина не отвечает на 127.0.0.1:${port}/healthz — подключать нечего"
  log "  витрина отвечает на ${port}"
fi

install -d -m 0755 "$CELLS"
printf 'server 127.0.0.1:%s;\n' "$port" > "$upstream_file"
if ! grep -qs "upstream ${upstream_name}" "$UPSTREAMS" 2>/dev/null; then
  touch "$UPSTREAMS"
  {
    printf '\n# %s: точка переключения трафика. Содержимое include меняет\n' "$site"
    printf '# исполнитель при выкладке; здесь только объявление.\n'
    printf 'upstream %s {\n    include %s;\n}\n' "$upstream_name" "$upstream_file"
  } >> "$UPSTREAMS"
fi
install -m 0644 "$SOURCE" "${TARGET_DIR}/${site}.conf"

log "проверка конфигурации"
if ! nginx -t; then
  rm -f "${TARGET_DIR}/${site}.conf"
  nginx -t >/dev/null 2>&1 || true
  die "nginx -t не прошёл; конфигурация витрины удалена, соседи не затронуты"
fi
nginx -s reload
log "готово: ${TARGET_DIR}/${site}.conf подключён через ${upstream_name}"
echo
echo "Дальше по порядку: запись A в DNS -> certbot -> блок 443."
