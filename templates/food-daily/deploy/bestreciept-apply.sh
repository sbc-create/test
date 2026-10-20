#!/usr/bin/env bash
# Выкладка bestreciept.site (food-daily) на этом сервере: root-шаг, который применяет владелец.
#
#   sudo bash templates/food-daily/deploy/bestreciept-apply.sh --kit <каталог комплекта> [--dry-run]
#   sudo bash templates/food-daily/deploy/bestreciept-apply.sh --rollback
#
# Комплект собирается из коммита: bash templates/food-daily/bin/food-daily kit build --out <каталог>.
# Что делает (идемпотентно, повтор безопасен):
#   1. проверяет комплект (sha256sum -c), ставит релиз в /srv/bestreciept-site/releases/<коммит>/ (только чтение);
#   2. системный пользователь bestreciept-site, данные /srv/bestreciept-site/var и секреты /srv/bestreciept-site/secrets — вне релиза;
#   3. первичная инициализация данных — один раз (редакционная база с версиями из комплекта, если она есть);
#   4. служба recipe-bestreciept-site.service на 127.0.0.1:9211 с SITE_CONFIG=site.bestreciept.yaml (адреса на домене, индексация закрыта);
#   5. nginx: HTTP → HTTPS, www → bestreciept.site, /redaktor/ снаружи закрыт; X-Robots-Tag noindex — пока в конфигурации
#      релиза production_authorized не true (тот же флаг, что у robots.txt, meta robots и sitemap приложения);
#   6. сертификат Let's Encrypt (webroot /var/www/certbot); продление — certbot.timer и хук reload-nginx.sh.
# Соседние сайты не затрагиваются: каждая правка nginx проходит nginx -t, при отказе наш файл убирается.
set -Eeuo pipefail

DOMAIN=bestreciept.site
TPL=food-daily
PKG=fooddaily
CFG=site.bestreciept.yaml
PORT=9211
SITE_USER=bestreciept-site
ROOT=/srv/bestreciept-site
UNIT=recipe-bestreciept-site.service
EDITOR_ENV=FOOD_DAILY_C_EDITOR_SECRET
WEBROOT=/var/www/certbot
NGX_AVAIL=/etc/nginx/sites-available
NGX_EN=/etc/nginx/sites-enabled
HTTP_CONF="${DOMAIN}.conf"
TLS_CONF="${DOMAIN}-tls.conf"

kit=""
dry=0
rollback=0
while [ $# -gt 0 ]; do
  case "$1" in
    --kit) kit="${2:-}"; shift ;;
    --dry-run) dry=1 ;;
    --rollback) rollback=1 ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done

log() { printf '==> %s\n' "$*"; }
die() { printf '[x] %s\n' "$*" >&2; exit 1; }
run() { if [ "$dry" = 1 ]; then echo "   [сухой прогон] $*"; else "$@"; fi; }

[ "$dry" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"

health() {
  python3 - "$PORT" "$DOMAIN" <<'PYH'
import sys, time, urllib.request
port, host = sys.argv[1], sys.argv[2]
for _ in range(60):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/healthz", headers={"Host": host})
        urllib.request.urlopen(req, timeout=2)
        sys.exit(0)
    except Exception:
        time.sleep(0.5)
sys.exit(1)
PYH
}

if [ "$rollback" = 1 ]; then
  prev="$(cat "${ROOT}/previous" 2>/dev/null || true)"
  [ -n "$prev" ] && [ -d "$prev" ] || die "нет предыдущего релиза для отката"
  cur="$(readlink -f "${ROOT}/current")"
  run ln -sfn "$prev" "${ROOT}/current.new"
  run mv -T "${ROOT}/current.new" "${ROOT}/current"
  [ "$dry" = 1 ] || echo "$cur" > "${ROOT}/previous"
  run systemctl restart "$UNIT"
  [ "$dry" = 1 ] || health || die "после отката служба не отвечает"
  log "откат: ${prev}"
  exit 0
fi

[ -n "$kit" ] || die "нужен --kit <каталог комплекта>"
[ -f "${kit}/MANIFEST.json" ] || die "в ${kit} нет MANIFEST.json"
(cd "$kit" && sha256sum -c --quiet SHA256SUMS) || die "контрольные суммы комплекта не сходятся"
read -r site commit < <(python3 -c 'import json,sys;m=json.load(open(sys.argv[1]));print(m["site"],m["commit"])' "${kit}/MANIFEST.json")
[ "$site" = "$TPL" ] || die "комплект сайта ${site}, а нужен ${TPL}"
rel="${ROOT}/releases/${commit:0:12}"
log "${DOMAIN}: комплект ${TPL} ${commit:0:12}"

# 1–2. пользователь, каталоги, релиз
if ! id -u "$SITE_USER" >/dev/null 2>&1; then
  run useradd --system --home-dir "$ROOT" --no-create-home --shell /usr/sbin/nologin "$SITE_USER"
fi
run install -d -m 0755 -o root -g root "$ROOT" "${ROOT}/releases"
run install -d -m 0750 -o "$SITE_USER" -g "$SITE_USER" "${ROOT}/var"
run install -d -m 0700 -o "$SITE_USER" -g "$SITE_USER" "${ROOT}/secrets"
if [ ! -d "$rel" ]; then
  run install -d -m 0755 "${rel}.tmp"
  run tar -xzf "${kit}/code.tar.gz" -C "${rel}.tmp"
  run tar -xzf "${kit}/content.tar.gz" -C "${rel}.tmp"
  run ln -sfn "${ROOT}/var" "${rel}.tmp/var"
  run chown -R root:root "${rel}.tmp"
  run chmod -R go-w "${rel}.tmp"
  run mv -T "${rel}.tmp" "$rel"
else
  log "релиз ${rel} уже стоит"
fi
TDIR="${rel}/templates/${TPL}"

# 3. первичная инициализация данных — ровно один раз
if [ -f "${kit}/private/${TPL}.sqlite3" ]; then
  db="${ROOT}/var/${TPL}/preview/${TPL}.sqlite3"
  if [ -f "$db" ]; then
    log "редакционная база уже есть — не трогаю"
  else
    imp="${ROOT}/var/.import-${commit:0:12}.sqlite3"
    run install -m 0600 -o "$SITE_USER" -g "$SITE_USER" "${kit}/private/${TPL}.sqlite3" "$imp"
    run runuser -u "$SITE_USER" -- env SITE_CONFIG="$CFG" PYTHONDONTWRITEBYTECODE=1 \
      sh -c "cd '$TDIR' && python3 -m ${PKG}.editorial clone-db --from '$imp'"
    run install -m 0600 -o "$SITE_USER" -g "$SITE_USER" "${kit}/private/versions.json" "${ROOT}/var/.import-versions.json"
    run runuser -u "$SITE_USER" -- env PYTHONDONTWRITEBYTECODE=1 \
      sh -c "cd '$TDIR' && python3 -m ${PKG}.kit verify-db --db '$db' --versions '${ROOT}/var/.import-versions.json'"
    run rm -f "$imp" "${ROOT}/var/.import-versions.json"
  fi
fi
if [ ! -f "${ROOT}/secrets/editor.json" ]; then
  run runuser -u "$SITE_USER" -- env "${EDITOR_ENV}=${ROOT}/secrets/editor.json" SITE_CONFIG="$CFG" \
    PYTHONDONTWRITEBYTECODE=1 sh -c "cd '$TDIR' && python3 -m ${PKG}.editor_secret >/dev/null"
  log "учётка редактора: ${ROOT}/secrets/editor-password.txt (0600, пароль в вывод не попадает)"
fi

# 4. служба
unit_text="[Unit]
Description=${DOMAIN} (${TPL}) — витрина
After=network-online.target

[Service]
User=${SITE_USER}
Group=${SITE_USER}
WorkingDirectory=${ROOT}/current/templates/${TPL}
Environment=SITE_CONFIG=${CFG}
Environment=${EDITOR_ENV}=${ROOT}/secrets/editor.json
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 -m ${PKG}.server
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=${ROOT}/var ${ROOT}/secrets

[Install]
WantedBy=multi-user.target
"
if [ "$dry" = 1 ]; then
  echo "   [сухой прогон] /etc/systemd/system/${UNIT}:"; printf '%s' "$unit_text" | sed 's/^/      /'
else
  printf '%s' "$unit_text" > "/etc/systemd/system/${UNIT}"
fi
cur="$(readlink -f "${ROOT}/current" 2>/dev/null || true)"
if [ "$cur" != "$rel" ]; then
  [ -z "$cur" ] || [ "$dry" = 1 ] || echo "$cur" > "${ROOT}/previous"
  run ln -sfn "$rel" "${ROOT}/current.new"
  run mv -T "${ROOT}/current.new" "${ROOT}/current"
fi
run systemctl daemon-reload
run systemctl enable "$UNIT"
run systemctl restart "$UNIT"
if [ "$dry" != 1 ] && ! health; then
  if [ -n "$cur" ] && [ "$cur" != "$rel" ]; then
    ln -sfn "$cur" "${ROOT}/current.new" && mv -T "${ROOT}/current.new" "${ROOT}/current"
    systemctl restart "$UNIT"
  fi
  die "служба ${UNIT} не ответила на 127.0.0.1:${PORT}/healthz — возвращён прежний релиз"
fi

# 5. nginx: сначала HTTP (нужен certbot), потом сертификат, потом 443
http_conf="# ${DOMAIN}: HTTP — подтверждение Let's Encrypt и перенаправление на HTTPS. Ставит ${TPL}/deploy.
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} www.${DOMAIN};
    server_tokens off;
    location /.well-known/acme-challenge/ { root ${WEBROOT}; }
    location / { return 301 https://${DOMAIN}\$request_uri; }
}
"
# Индексация: один флаг production_authorized в конфигурации релиза. Пока он не true — nginx дублирует
# noindex приложения; после открытия заголовок не ставится, чтобы не противоречить robots.txt и sitemap.
if tar -xzOf "${kit}/code.tar.gz" "templates/${TPL}/config/${CFG}" | grep -Eq '^production_authorized:[[:space:]]*true\b'; then
  robots_hdr=""; log "индексация: открыта (production_authorized: true)"
else
  robots_hdr='    add_header X-Robots-Tag "noindex, nofollow" always;'; log "индексация: закрыта (production_authorized не true)"
fi
tls_conf="# ${DOMAIN}: HTTPS. Индексация — по production_authorized в конфигурации релиза.
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN};
    server_tokens off;
    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
${robots_hdr}
    add_header X-Content-Type-Options \"nosniff\" always;
    # редактор доступен только с самого сервера (туннель на 127.0.0.1:${PORT}), снаружи — 404
    location ^~ /redaktor { return 404; }
    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name www.${DOMAIN};
    server_tokens off;
    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
${robots_hdr}
    return 301 https://${DOMAIN}\$request_uri;
}
"
put_conf() {  # имя, текст: ставит и включает, при отказе nginx -t убирает своё
  local name="$1" text="$2"
  if [ "$dry" = 1 ]; then echo "   [сухой прогон] ${NGX_AVAIL}/${name}"; printf '%s' "$text" | sed 's/^/      /'; return 0; fi
  if [ -f "${NGX_AVAIL}/${name}" ] && [ "$(cat "${NGX_AVAIL}/${name}")" = "$text" ] && [ -L "${NGX_EN}/${name}" ]; then
    log "${name} без изменений"; return 0
  fi
  [ -f "${NGX_AVAIL}/${name}" ] && cp -p "${NGX_AVAIL}/${name}" "${NGX_AVAIL}/${name}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
  printf '%s' "$text" > "${NGX_AVAIL}/${name}"
  ln -sfn "${NGX_AVAIL}/${name}" "${NGX_EN}/${name}"
  if ! nginx -t; then
    rm -f "${NGX_EN}/${name}"
    die "nginx -t не прошёл на ${name}; файл выключен, соседние сайты не затронуты"
  fi
  systemctl reload nginx
}
run install -d -m 0755 "$WEBROOT"
put_conf "$HTTP_CONF" "$http_conf"

# 6. сертификат
if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
  log "сертификат ${DOMAIN} уже есть"
else
  run certbot certonly --webroot -w "$WEBROOT" --non-interactive --agree-tos \
    --register-unsafely-without-email --keep-until-expiring -d "$DOMAIN" -d "www.${DOMAIN}" \
    || die "certbot не выдал сертификат; HTTP-конфигурация работает, HTTPS не включён"
fi
put_conf "$TLS_CONF" "$tls_conf"
run certbot renew --dry-run --cert-name "$DOMAIN"
run systemctl is-enabled certbot.timer

# итог: проверка снаружи по домену
if [ "$dry" != 1 ]; then
  python3 - "$DOMAIN" <<'PYCHK'
import sys, urllib.request, urllib.error, ssl
d = sys.argv[1]
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
op = urllib.request.build_opener(NoRedirect)
def code(url):
    try: r = op.open(url, timeout=10); return r.status, r.headers.get("Location")
    except urllib.error.HTTPError as e: return e.code, e.headers.get("Location")
print("http://   ->", code(f"http://{d}/"))
print("http://www->", code(f"http://www.{d}/"))
print("https://www->", code(f"https://www.{d}/"))
r = urllib.request.urlopen(f"https://{d}/", timeout=10, context=ssl.create_default_context())
print("https://  ->", r.status, r.headers.get("X-Robots-Tag"))
PYCHK
fi
log "готово: https://${DOMAIN}/ (релиз ${commit:0:12}); откат: --rollback"
