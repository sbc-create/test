#!/usr/bin/env bash
# Включает HTTPS на трёх витринах ПОСЛЕ выпуска сертификата.
#
# Сертификат этот скрипт не выпускает: выпуск требует certbot, который остаётся
# в deny настроек, и снимать это правило самостоятельно нельзя — изменение
# разрешений делает владелец. Здесь только то, что можно сделать после.
#
# Идемпотентен: повторный запуск не дублирует блоки и не ломает конфигурацию.
# Перед перезагрузкой обязателен nginx -t; при отказе конфигурация возвращается.
set -Eeuo pipefail

CERT_DIR=/etc/letsencrypt/live
NGINX_DIR=/etc/nginx/lords
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

declare -A SITES=(
  [zona-01]="zonafilm.space:9120"
  [animedia-01]="animedia.icu:9121"
  [animedia-02]="animedia.space:9122"
)

changed=0
for site in "${!SITES[@]}"; do
  IFS=: read -r domain port <<< "${SITES[$site]}"
  conf="${NGINX_DIR}/${site}.conf"

  if [ ! -d "${CERT_DIR}/${domain}" ]; then
    echo "[tls] ${domain}: сертификата нет — пропускаю (выпустите certbot)"
    continue
  fi
  if grep -q "listen 443" "$conf" 2>/dev/null; then
    echo "[tls] ${domain}: HTTPS уже настроен"
    continue
  fi

  cp "$conf" "${conf}.bak.${STAMP}"
  cat >> "$conf" <<VHOST

# HTTPS добавлен $(date -u +%Y-%m-%d) после выпуска сертификата.
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name ${domain};

    ssl_certificate     ${CERT_DIR}/${domain}/fullchain.pem;
    ssl_certificate_key ${CERT_DIR}/${domain}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

    server_tokens off;
    # Индексация закрыта: витрина тестовая.
    add_header X-Robots-Tag "noindex, nofollow" always;

    location / {
        proxy_pass http://127.0.0.1:${port};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 30s;
    }

    location = /healthz {
        proxy_pass http://127.0.0.1:${port}/healthz;
        access_log off;
    }
}
VHOST
  changed=$((changed + 1))
  echo "[tls] ${domain}: блок HTTPS добавлен"
done

if [ "$changed" -eq 0 ]; then
  echo "[tls] изменений нет"
  exit 0
fi

if ! nginx -t >/dev/null 2>&1; then
  echo "[tls] ОТКАЗ: nginx -t не прошёл, возвращаю конфигурацию" >&2
  for site in "${!SITES[@]}"; do
    [ -f "${NGINX_DIR}/${site}.conf.bak.${STAMP}" ] && \
      cp "${NGINX_DIR}/${site}.conf.bak.${STAMP}" "${NGINX_DIR}/${site}.conf"
  done
  nginx -t
  exit 1
fi
systemctl reload nginx
echo "[tls] nginx перезагружен, HTTPS включён на ${changed} витринах"
