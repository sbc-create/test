#!/usr/bin/env bash
# Сертификат и блок 443 для витрины. Отдельным шагом после HTTP-конфигурации.
#
#   sudo bash automation/host/install-site-tls.sh --site zona-03 [--dry-run]
#
# Порядок именно такой и не переставляется: certbot проверяет владение
# доменом по HTTP, поэтому конфигурация порта 80 с `.well-known` обязана уже
# работать. А блок 443 ставится ПОСЛЕ выпуска сертификата, потому что
# `ssl_certificate` на несуществующий файл роняет проверку конфигурации
# целиком — вместе с соседними витринами.
#
# При любой неудаче файл 443 удаляется и конфигурация возвращается к
# состоянию «работает только HTTP»: новый домен не должен задевать соседей.
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

SRC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${SRC_ROOT}/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
TARGET_DIR=/etc/nginx/lords
SOURCE="${SRC_ROOT}/automation/host/nginx-site/${site}-tls.conf"
WEBROOT=/var/www/certbot

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"
[ -f "$SOURCE" ] || die "нет заготовки $SOURCE"
[ -f "${TARGET_DIR}/${site}.conf" ] || die "сначала HTTP-конфигурация ${TARGET_DIR}/${site}.conf"

# Имена доменов берутся из реестра, а не из аргументов: сертификат не на тот
# домен — это ошибка, которую замечают уже посетители.
domains="$("$PY" - "$SRC_ROOT" "$site" <<'PYDOM'
import json, sys
корень, site = sys.argv[1], sys.argv[2]
д = json.load(open(f"{корень}/config/site-cells.json", encoding="utf-8"))
for c in д.get("cells") or []:
    if c["site_id"] == site:
        имена = [c["domain"], *(c.get("aliases") or [])]
        print(" ".join(f"-d {и}" for и in имена), end="")
        break
PYDOM
)"
[ -n "$domains" ] || die "в реестре нет доменов для $site"
primary="$("$PY" - "$SRC_ROOT" "$site" <<'PYPRIM'
import json, sys
д = json.load(open(f"{sys.argv[1]}/config/site-cells.json", encoding="utf-8"))
print(next(c["domain"] for c in д["cells"] if c["site_id"] == sys.argv[2]), end="")
PYPRIM
)"

log "сертификат для: $domains"
if [ "$dry_run" = 1 ]; then
  echo "   [сухой прогон] certbot certonly --webroot -w $WEBROOT $domains"
  echo "   [сухой прогон] $SOURCE -> ${TARGET_DIR}/${site}-tls.conf, nginx -t, reload"
  exit 0
fi

install -d -m 0755 "$WEBROOT"
if [ -f "/etc/letsencrypt/live/${primary}/fullchain.pem" ]; then
  log "сертификат уже есть, выпуск пропущен"
else
  # shellcheck disable=SC2086
  certbot certonly --webroot -w "$WEBROOT" --non-interactive --agree-tos \
      --register-unsafely-without-email --keep-until-expiring $domains \
    || die "certbot не выдал сертификат; HTTP-конфигурация не тронута"
fi
[ -f "/etc/letsencrypt/live/${primary}/fullchain.pem" ] \
  || die "certbot отчитался успехом, но /etc/letsencrypt/live/${primary}/fullchain.pem нет"

install -m 0644 "$SOURCE" "${TARGET_DIR}/${site}-tls.conf"
if ! nginx -t; then
  rm -f "${TARGET_DIR}/${site}-tls.conf"
  nginx -t >/dev/null 2>&1 || true
  die "nginx -t не прошёл; блок 443 удалён, соседи не затронуты"
fi
nginx -s reload
log "готово: HTTPS ${primary}"
