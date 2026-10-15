#!/usr/bin/env bash
# Сертификат и блок 443 для витрины партии K2 — одной командой на узле.
#
#   sudo bash /home/k2deploy/stage/k2-enable-tls.sh lords-10 [--dry-run]
#
# Зачем сценарий, а не восемь раз руками. Порядок здесь не переставляется, и
# каждая переставленная строка стоит дорого:
#
#   * `certbot` подтверждает владение именем по HTTP, поэтому конфигурация
#     порта 80 с `.well-known` обязана уже РАБОТАТЬ, а имя — уже указывать на
#     этот узел. Выпуск до перевода DNS сжигает попытку у Let's Encrypt;
#   * блок 443 ставится ПОСЛЕ выпуска: `ssl_certificate` на несуществующий
#     файл роняет проверку конфигурации целиком, а значит и СОСЕДНИЕ семь
#     витрин вместе со своей;
#   * сертификат обязан покрывать и `www`: заготовка 443 несёт оба блока и
#     ссылается на один каталог `live/<домен>`.
#
# При любой неудаче после установки файл 443 убирается и конфигурация
# возвращается к состоянию «работает только HTTP»: витрина остаётся доступной,
# соседи не задеты.
#
# Имена переменных только ASCII: кириллица в именах переменных оболочки падает
# в работе, а `bash -n` её пропускает.
set -Eeuo pipefail

site="${1:?нужен site_id, например lords-10}"
shift || true
dry_run=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    *) echo "неизвестный аргумент: $arg" >&2; exit 2 ;;
  esac
done

stage="${K2_STAGE:-$HOME/stage}"
[ -d "$stage" ] || stage=/home/k2deploy/stage
staged="$stage/nginx/$site-tls.conf"
installed="/etc/nginx/lords/$site-tls.conf"
http_conf="/etc/nginx/lords/$site.conf"
webroot=/var/www/certbot
hook_src="$stage/letsencrypt-reload-nginx.sh"
hook_dst=/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
this_ip="${K2_NODE_IP:-145.63.129.86}"

log() { printf '==> %s\n' "$*"; }
die() { printf '[x] %s\n' "$*" >&2; exit 1; }

# --- 1. Предусловия. Каждое названо: отказ обязан объяснять себя ------------
[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"
[ -f "$staged" ] || die "нет заготовки $staged"
[ -f "$http_conf" ] || die "нет конфигурации порта 80 $http_conf: сначала k2-launch-site.sh"
grep -q "acme-challenge" "$http_conf" || die "в $http_conf нет пути ACME: certbot не подтвердит владение"
[ -d "$webroot" ] || die "нет корня ACME $webroot"
command -v certbot >/dev/null || die "certbot не установлен"

# Домен берётся ИЗ ЗАГОТОВКИ, а не из таблицы в сценарии: таблица разошлась бы
# с конфигурацией молча.
domain="$(awk '/server_name/ {gsub(/;/,""); print $2; exit}' "$staged")"
[ -n "$domain" ] || die "в $staged не нашлось server_name"
log "витрина $site, домен $domain"

# --- 2. DNS. Выпуск до перевода записи сжигает попытку у Let's Encrypt -----
a_apex="$(dig +short A "$domain" @8.8.8.8 | tail -1)"
a_www="$(dig +short A "www.$domain" @8.8.8.8 | tail -1)"
[ "$a_apex" = "$this_ip" ] || die "A-запись $domain = ${a_apex:-нет} вместо $this_ip: перевод DNS ещё не выполнен"
[ "$a_www" = "$this_ip" ] || die "A-запись www.$domain = ${a_www:-нет} вместо $this_ip: сертификат обязан покрывать www, иначе блок 443 не поднимется"

# Имя обязано приходить именно в этот nginx: совпадения адреса недостаточно,
# бывает и чужой прокси впереди.
probe="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
  "http://$domain/.well-known/acme-challenge/probe-$$" || true)"
case "$probe" in
  404|200) log "путь ACME отвечает $probe — имя приходит сюда" ;;
  *) die "путь ACME ответил '${probe:-нет ответа}': certbot не подтвердит владение" ;;
esac

if [ "$dry_run" = 1 ]; then
  log "сухой прогон: предусловия выполнены, выпуск и установка не делались"
  exit 0
fi

# --- 3. Сертификат. Повторный запуск не выпускает лишнего ------------------
if [ -s "/etc/letsencrypt/live/$domain/fullchain.pem" ] \
   && openssl x509 -noout -text -in "/etc/letsencrypt/live/$domain/fullchain.pem" \
      | grep -q "DNS:www.$domain"; then
  log "сертификат уже есть и покрывает www — выпуск не нужен"
else
  log "выпускаю сертификат на $domain и www.$domain"
  certbot certonly --webroot -w "$webroot" \
    -d "$domain" -d "www.$domain" --cert-name "$domain" \
    --non-interactive --agree-tos --keep-until-expiring \
    --email "${K2_ACME_EMAIL:?нужен K2_ACME_EMAIL — адрес владельца для уведомлений Let\'s Encrypt}"
fi
[ -s "/etc/letsencrypt/live/$domain/fullchain.pem" ] || die "сертификата нет после выпуска"

# --- 4. Блок 443 с откатом -------------------------------------------------
install -m 0644 -o root -g root "$staged" "$installed"
if ! nginx -t; then
  rm -f "$installed"
  nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
  die "nginx -t не прошёл с блоком 443 — файл убран, витрина осталась на HTTP"
fi
systemctl reload nginx || { rm -f "$installed"; nginx -t && systemctl reload nginx; die "перезагрузка nginx не удалась — файл убран"; }
log "блок 443 установлен, nginx перечитал конфигурацию"

# --- 5. Автопродление: продление без перезагрузки ничего не меняет ---------
if [ -x "$hook_dst" ]; then
  log "хук перезагрузки уже стоит: $hook_dst"
elif [ -f "$hook_src" ]; then
  install -D -m 0755 "$hook_src" "$hook_dst"
  log "хук перезагрузки установлен: $hook_dst"
else
  printf '[!] нет %s и нет %s: продление положит новые файлы, но nginx продолжит отдавать ПРЕЖНИЙ сертификат\n' \
    "$hook_dst" "$hook_src" >&2
fi

# --- 6. Проверка результата, а не надежда на него --------------------------
log "проверка снаружи"
san="$(echo | openssl s_client -connect "$domain:443" -servername "$domain" 2>/dev/null \
  | openssl x509 -noout -ext subjectAltName 2>/dev/null | tr -d ' ')"
echo "    SAN: ${san:-не прочитан}"
case "$san" in
  *"DNS:$domain"*) ;;
  *) die "предъявленный сертификат не покрывает $domain" ;;
esac
printf '    апекс https:  %s\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$domain/")"
printf '    www   https:  %s (ожидается 301)\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://www.$domain/")"
printf '    http  апекс:  %s\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "http://$domain/")"
log "готово: $site"
