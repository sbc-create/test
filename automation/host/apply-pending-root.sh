#!/usr/bin/env bash
# Всё накопившееся, что требует root, одной командой.
#
#   sudo bash automation/host/apply-pending-root.sh [--dry-run]
#
# Что входит и зачем
# ------------------
#
#   1. обновление исполнителя  доставка недельного снимка в хранилище витрины
#                              и запись animedia-01 в реестре (без data_dir
#                              выпуск ICU отказывает до сборки)
#   2. nginx для zona-02       конфигурации zonafilm.cc нет ни в одном
#                              загружаемом каталоге; служба на 9123 отвечает
#   3. сертификат zonafilm.cc  webroot, как у остальных витрин
#   4. блок 443                отдельным шагом: со ссылкой на несуществующий
#                              сертификат nginx не перезагрузится вовсе
#
# Каждый шаг проверяется и не трогает соседей при отказе. Шаги независимы:
# провал одного не отменяет остальных, итог печатается в конце.
set -Eeuo pipefail

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

SRC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
DOMAIN=zonafilm.cc
TLS_SOURCE="${SRC_ROOT}/automation/host/nginx-site/zona-02-tls.conf"
SITE_CONF=/etc/nginx/lords/zona-02.conf
WEBROOT=/var/www/certbot

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"

declare -a results=()
step_ok()   { results+=("ok    $1"); }
step_fail() { results+=("ОТКАЗ $1: $2"); warn "$1: $2"; }

# ---------------------------------------------------------------- 1. исполнитель
log "шаг 1: обновление исполнителя"
if [ "$dry_run" = 1 ]; then
  printf '   [сухой прогон] bash automation/host/install-cell-executor.sh\n'
elif bash "${SRC_ROOT}/automation/host/install-cell-executor.sh"; then
  step_ok "исполнитель обновлён"
else
  step_fail "исполнитель" "install-cell-executor.sh вернул ненулевой код"
fi

# ------------------------------------------------------------------ 2. nginx
log "шаг 2: конфигурация nginx для zona-02"
if [ "$dry_run" = 1 ]; then
  printf '   [сухой прогон] bash automation/host/install-site-nginx.sh --site zona-02\n'
elif [ -f "$SITE_CONF" ]; then
  step_ok "конфигурация zona-02 уже стоит"
elif bash "${SRC_ROOT}/automation/host/install-site-nginx.sh" --site zona-02; then
  step_ok "конфигурация zona-02 подключена"
else
  step_fail "nginx zona-02" "см. вывод выше"
fi

# ------------------------------------------------------------ 3. сертификат
log "шаг 3: сертификат $DOMAIN"
if [ "$dry_run" = 1 ]; then
  printf '   [сухой прогон] certbot certonly --webroot -w %s -d %s -d www.%s\n' \
      "$WEBROOT" "$DOMAIN" "$DOMAIN"
elif [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
  step_ok "сертификат уже есть"
elif [ ! -f "$SITE_CONF" ]; then
  step_fail "сертификат" "нет конфигурации nginx — ACME-проверке некуда прийти"
elif certbot certonly --webroot -w "$WEBROOT" -d "$DOMAIN" -d "www.${DOMAIN}" \
       --non-interactive --agree-tos --register-unsafely-without-email \
       --keep-until-expiring; then
  step_ok "сертификат выпущен"
else
  step_fail "сертификат" "certbot вернул ненулевой код"
fi

# -------------------------------------------------------------- 4. блок 443
log "шаг 4: HTTPS для $DOMAIN"
if [ "$dry_run" = 1 ]; then
  printf '   [сухой прогон] дописать блок 443 из %s и перезагрузить nginx\n' "$TLS_SOURCE"
elif [ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
  step_fail "HTTPS" "сертификата нет — блок 443 уронил бы nginx целиком"
elif grep -qs "listen 443" "$SITE_CONF"; then
  step_ok "блок 443 уже стоит"
else
  cp -p "$SITE_CONF" "${SITE_CONF}.before-tls"
  cat "$TLS_SOURCE" >> "$SITE_CONF"
  if nginx -t; then
    nginx -s reload
    rm -f "${SITE_CONF}.before-tls"
    step_ok "HTTPS включён"
  else
    mv "${SITE_CONF}.before-tls" "$SITE_CONF"
    nginx -t >/dev/null 2>&1 && nginx -s reload || true
    step_fail "HTTPS" "nginx -t не прошёл, конфигурация возвращена"
  fi
fi

echo
log "итог"
printf '   %s\n' "${results[@]:-нечего делать}"
printf '%s\n' "${results[@]:-}" | grep -q '^ОТКАЗ' && exit 1
exit 0
