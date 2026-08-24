#!/usr/bin/env bash
# Публикация fixture-staging направления Lords на управляющем сервере.
#
# Сценарий идемпотентен: повторный запуск не создаёт второй сайт, второй
# сертификат, второго пользователя и второй юнит. Каждый шаг сначала смотрит на
# фактическое состояние и только потом решает, нужно ли что-то делать.
#
# Что он НЕ делает — и это так же важно, как то, что он делает:
#   * не трогает конфигурацию, контейнеры, базы и бэкапы YummyAnime;
#   * не занимает портов вне 9101-9103;
#   * не включает индексацию, не создаёт Метрику и не добавляет хосты в Вебмастер;
#   * не выкатывает production: пакеты объявлены staging и не авторизованы;
#   * не печатает значения секретов — только пути к ним.
#
# Запуск:
#   sudo bash automation/host/lords-staging-apply.sh
#
# Переменные окружения (все необязательны):
#   LORDS_ACME_EMAIL   адрес для уведомлений Let's Encrypt о продлении.
#                      Не задан — регистрация без адреса, писем об истечении не будет.
#   LORDS_SKIP_CERTS=1 остановиться после фазы 1 (сертификаты не выпускать).

set -Eeuo pipefail

readonly NGINX_DIR=/etc/nginx/lords
readonly RUNTIME_ROOT=/srv/lords
readonly ACME_ROOT=/var/www/lords-acme
readonly HTPASSWD="${NGINX_DIR}/.htpasswd"
readonly CREDENTIALS=/root/lords-staging-credentials
readonly DEFAULT_CERT="${NGINX_DIR}/default-self-signed"
readonly SERVICE_USER=lords
readonly PORTS=(9101 9102 9103)

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

trap 'die "прервано на строке ${LINENO}; ничего не перезагружено после последней успешной проверки"' ERR

[[ ${EUID} -eq 0 ]] || die "нужен root: sudo bash $0"

# --------------------------------------------------------------------------
# 0. Где мы и чем собирать
# --------------------------------------------------------------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
[[ -f "${REPO_ROOT}/config/directions/lords.json" ]] \
  || die "не похоже на репозиторий фабрики: ${REPO_ROOT}"

if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PY="${REPO_ROOT}/.venv/bin/python"
else
  PY="$(command -v python3 || true)"
fi
[[ -n "${PY}" ]] || die "python3 не найден"
command -v nginx >/dev/null || die "nginx не установлен"

log "репозиторий: ${REPO_ROOT}"
log "интерпретатор: ${PY}"
log "nginx: $(nginx -v 2>&1)"

# --------------------------------------------------------------------------
# 1. Сборка конфигурации и пакетов. Ничего ещё не применяется.
# --------------------------------------------------------------------------
log "собираю конфигурацию и пакеты стенда"
( cd "${REPO_ROOT}" && "${PY}" -m factory lords-staging ) \
  || die "сборка стенда не прошла — на сервере ничего не изменено"

STAGING_DIR="${REPO_ROOT}/artifacts/lords/staging"
BUNDLE_DIR="${REPO_ROOT}/artifacts/lords/bundle"
[[ -f "${STAGING_DIR}/staging.json" ]] || die "нет ${STAGING_DIR}/staging.json"

mapfile -t SITES < <("${PY}" -c '
import json, sys
data = json.load(open(sys.argv[1]))
for s in data["sites"]:
    print(f"{s[\"site_id\"]}\t{s[\"apex\"]}\t{s[\"www\"]}\t{s[\"port\"]}\t{s[\"unit\"]}\t{s[\"runtime_root\"]}")
' "${STAGING_DIR}/staging.json")
[[ ${#SITES[@]} -eq 3 ]] || die "ожидалось три сайта, получено ${#SITES[@]}"

# --------------------------------------------------------------------------
# 2. Чужое не трогаем: порты и сервер по умолчанию
# --------------------------------------------------------------------------
log "проверяю, что не мешаю соседям"
for port in "${PORTS[@]}"; do
  if ss -ltnp 2>/dev/null | grep -qE "127\.0\.0\.1:${port}\b"; then
    holder="$(ss -ltnp 2>/dev/null | grep -E "127\.0\.0\.1:${port}\b" | head -1)"
    if ! grep -qE "lords-0[123]|python3" <<<"${holder}"; then
      die "порт ${port} занят посторонним процессом: ${holder}"
    fi
    log "  порт ${port} уже держит наш же рантайм — это повторный запуск"
  fi
done

INSTALL_DEFAULT=1
if grep -rlsE '^\s*listen[^;]*default_server' /etc/nginx --include='*.conf' 2>/dev/null \
     | grep -v "^${NGINX_DIR}/" | grep -q .; then
  INSTALL_DEFAULT=0
  warn "в /etc/nginx уже объявлен default_server вне ${NGINX_DIR}."
  warn "Свой сервер по умолчанию не ставлю: два default_server на одном порту —"
  warn "это отказ nginx -t. Ответ 421 на неизвестный Host остаётся за существующей"
  warn "конфигурацией; проверьте её отдельно."
fi

# --------------------------------------------------------------------------
# 3. Пользователь, каталоги, права
# --------------------------------------------------------------------------
if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  log "создаю системного пользователя ${SERVICE_USER}"
  useradd --system --home-dir "${RUNTIME_ROOT}" --shell /usr/sbin/nologin "${SERVICE_USER}"
else
  log "пользователь ${SERVICE_USER} уже есть"
fi

install -d -m 0755 "${NGINX_DIR}" "${RUNTIME_ROOT}" "${ACME_ROOT}"
install -d -m 0755 -o "${SERVICE_USER}" -g "${SERVICE_USER}" "${RUNTIME_ROOT}"

# --------------------------------------------------------------------------
# 4. Basic Auth. Пароль рождается здесь и в вывод не попадает.
# --------------------------------------------------------------------------
if [[ -s "${HTPASSWD}" ]]; then
  log "файл Basic Auth уже есть — пароль не меняю"
else
  log "создаю пароль Basic Auth"
  password="$(openssl rand -base64 24 | tr -d '\n/+=' | cut -c1-24)"
  if command -v htpasswd >/dev/null; then
    htpasswd -bcB "${HTPASSWD}" lords "${password}" >/dev/null 2>&1
  else
    printf 'lords:%s\n' "$(openssl passwd -apr1 "${password}")" > "${HTPASSWD}"
  fi
  umask 077
  { printf 'Lords staging — Basic Auth\n'
    printf 'создано: %s\n' "$(date -Is)"
    printf 'логин: lords\n'
    printf 'пароль: %s\n' "${password}"
  } > "${CREDENTIALS}"
  chmod 0600 "${CREDENTIALS}"
  unset password
  log "пароль записан в ${CREDENTIALS} (права 0600). В этот вывод он не попал."
fi
chown root:www-data "${HTPASSWD}" 2>/dev/null || chown root:root "${HTPASSWD}"
chmod 0640 "${HTPASSWD}"

# --------------------------------------------------------------------------
# 5. Раскладка релизов. Переключение симлинка — атомарное.
# --------------------------------------------------------------------------
for row in "${SITES[@]}"; do
  IFS=$'\t' read -r site_id apex www port unit runtime <<<"${row}"
  archive="${BUNDLE_DIR}/${site_id}.tar"
  [[ -f "${archive}" ]] || die "нет пакета ${archive}"
  release="$(sha256sum "${archive}" | cut -c1-12)"
  target="${runtime}/releases/${release}"

  install -d -m 0755 -o "${SERVICE_USER}" -g "${SERVICE_USER}" \
    "${runtime}" "${runtime}/releases" "${runtime}/data"

  if [[ -d "${target}" ]]; then
    log "${site_id}: релиз ${release} уже разложен"
  else
    log "${site_id}: раскладываю релиз ${release}"
    install -d -m 0755 "${target}.tmp"
    tar -xf "${archive}" -C "${target}.tmp"
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${target}.tmp"
    mv "${target}.tmp" "${target}"
  fi

  # Симлинк переставляется через временное имя: в каталоге нет момента,
  # когда current отсутствует.
  ln -sfn "${target}" "${runtime}/.current.new"
  mv -Tf "${runtime}/.current.new" "${runtime}/current"
  chown -h "${SERVICE_USER}:${SERVICE_USER}" "${runtime}/current"

  # Предыдущие релизы: держим три последних, остальное удаляем.
  # Удаляется только то, что лежит под нашим же releases/ и не является текущим.
  mapfile -t old < <(ls -1dt "${runtime}/releases/"*/ 2>/dev/null | tail -n +4)
  for stale in "${old[@]:-}"; do
    [[ -n "${stale}" && "${stale}" != "${target}/" ]] || continue
    log "${site_id}: убираю старый релиз $(basename "${stale}")"
    rm -rf -- "${stale}"
  done

  install -m 0644 "${STAGING_DIR}/systemd/${unit}" "/etc/systemd/system/${unit}"
done

systemctl daemon-reload

# --------------------------------------------------------------------------
# 6. Фаза 1: только HTTP, чтобы выпустить сертификаты
# --------------------------------------------------------------------------
install_phase() {
  local phase="$1"
  log "устанавливаю конфигурацию nginx (${phase})"
  rm -f "${NGINX_DIR}"/*.conf
  for conf in "${STAGING_DIR}/nginx/${phase}"/*.conf; do
    local name; name="$(basename "${conf}")"
    if [[ "${name}" == "00-default.conf" && "${INSTALL_DEFAULT}" -eq 0 ]]; then
      continue
    fi
    install -m 0644 "${conf}" "${NGINX_DIR}/${name}"
  done

  if ! grep -qrs "include ${NGINX_DIR}/\*.conf;" /etc/nginx/nginx.conf; then
    if [[ -d /etc/nginx/conf.d ]]; then
      printf 'include %s/*.conf;\n' "${NGINX_DIR}" > /etc/nginx/conf.d/lords.conf
      log "подключил ${NGINX_DIR} через /etc/nginx/conf.d/lords.conf"
    else
      die "не нашёл, куда подключить ${NGINX_DIR}: нет /etc/nginx/conf.d"
    fi
  fi

  # Настоящая проверка. Пока она не прошла, ничего не перезагружается.
  nginx -t || die "nginx -t не прошёл на фазе ${phase}; reload не выполнялся"
  systemctl reload nginx || systemctl start nginx
  log "nginx перезагружен (${phase})"
}

# Самоподписанный сертификат сервера по умолчанию: ssl_reject_handshake
# появился только в 1.19.4, а цель — 1.18.
if [[ "${INSTALL_DEFAULT}" -eq 1 && ! -s "${DEFAULT_CERT}.crt" ]]; then
  log "создаю самоподписанный сертификат для сервера по умолчанию"
  openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
    -keyout "${DEFAULT_CERT}.key" -out "${DEFAULT_CERT}.crt" \
    -subj "/CN=invalid.invalid" >/dev/null 2>&1
  chmod 0600 "${DEFAULT_CERT}.key"
fi

install_phase phase1

for row in "${SITES[@]}"; do
  IFS=$'\t' read -r site_id apex www port unit runtime <<<"${row}"
  log "${site_id}: запускаю ${unit}"
  systemctl enable --now "${unit}" >/dev/null 2>&1 || systemctl restart "${unit}"
done

log "жду готовности рантаймов"
for row in "${SITES[@]}"; do
  IFS=$'\t' read -r site_id apex www port unit runtime <<<"${row}"
  for attempt in $(seq 1 30); do
    if curl -fsS --max-time 3 "http://127.0.0.1:${port}/readyz" >/dev/null 2>&1; then
      log "  ${site_id} готов на 127.0.0.1:${port}"
      break
    fi
    [[ ${attempt} -eq 30 ]] && die "${site_id}: /readyz не ответил за 30 попыток"
    sleep 1
  done
done

if [[ "${LORDS_SKIP_CERTS:-0}" == "1" ]]; then
  warn "LORDS_SKIP_CERTS=1 — останавливаюсь после фазы 1. HTTPS не настроен."
  exit 0
fi

# --------------------------------------------------------------------------
# 7. Сертификаты Let's Encrypt
# --------------------------------------------------------------------------
command -v certbot >/dev/null || die "certbot не установлен"

acme_account_args=()
if [[ -n "${LORDS_ACME_EMAIL:-}" ]]; then
  acme_account_args=(--email "${LORDS_ACME_EMAIL}")
else
  acme_account_args=(--register-unsafely-without-email)
  warn "LORDS_ACME_EMAIL не задан: писем об истечении сертификата не будет."
fi

for row in "${SITES[@]}"; do
  IFS=$'\t' read -r site_id apex www port unit runtime <<<"${row}"
  if [[ -s "/etc/letsencrypt/live/${apex}/fullchain.pem" ]]; then
    log "${apex}: сертификат уже есть"
    continue
  fi
  log "${apex}: выпускаю сертификат на apex и www"
  certbot certonly --webroot -w "${ACME_ROOT}" \
    -d "${apex}" -d "${www}" \
    --non-interactive --agree-tos --keep-until-expiring \
    "${acme_account_args[@]}" \
    || die "certbot не смог выпустить сертификат для ${apex}; HTTPS не включён, фаза 1 работает"
done

# Продление с перезагрузкой nginx. Хук идемпотентен: файл просто перезаписывается.
install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/lords-nginx-reload.sh <<'HOOK'
#!/usr/bin/env bash
# Перезагрузка nginx после успешного продления сертификата Lords.
set -Eeuo pipefail
nginx -t
systemctl reload nginx
HOOK
chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/lords-nginx-reload.sh

systemctl enable --now certbot.timer >/dev/null 2>&1 \
  || warn "certbot.timer не включился: проверьте, чем настроено автопродление"
certbot renew --dry-run >/dev/null 2>&1 \
  && log "пробное продление прошло" \
  || warn "пробное продление не прошло — проверьте certbot renew --dry-run вручную"

# --------------------------------------------------------------------------
# 8. Фаза 2: HTTPS
# --------------------------------------------------------------------------
install_phase phase2

# --------------------------------------------------------------------------
# 9. Проверка того, что получилось
# --------------------------------------------------------------------------
log "проверяю результат"
failures=0
for row in "${SITES[@]}"; do
  IFS=$'\t' read -r site_id apex www port unit runtime <<<"${row}"

  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "https://${apex}/" || echo 000)"
  [[ "${code}" == "401" ]] \
    && log "  ${apex}: 401 без пароля — Basic Auth работает" \
    || { warn "  ${apex}: ожидался 401, получен ${code}"; failures=$((failures + 1)); }

  redirect="$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 10 \
    "https://${www}/" || echo '000 -')"
  grep -q '^308 ' <<<"${redirect}" \
    && log "  ${www}: ${redirect}" \
    || { warn "  ${www}: ожидался 308, получено ${redirect}"; failures=$((failures + 1)); }

  robots="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 \
    "http://127.0.0.1:${port}/robots.txt" || echo 000)"
  [[ "${robots}" == "200" ]] \
    && log "  ${site_id}: robots.txt отдаётся рантаймом" \
    || { warn "  ${site_id}: robots.txt вернул ${robots}"; failures=$((failures + 1)); }
done

if [[ "${INSTALL_DEFAULT}" -eq 1 ]]; then
  unknown="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 \
    -H 'Host: no-such-host.invalid' http://127.0.0.1/ || echo 000)"
  [[ "${unknown}" == "421" ]] \
    && log "  неизвестный Host: 421" \
    || { warn "  неизвестный Host вернул ${unknown}, ожидался 421"; failures=$((failures + 1)); }
fi

echo
log "готово"
"${PY}" -c '
import json, sys
data = json.load(open(sys.argv[1]))
for s in data["sites"]:
    print(f"  {s[\"url\"]:38} {s[\"site_id\"]}  {s[\"profile\"]:14} :{s[\"port\"]}")
' "${STAGING_DIR}/staging.json"
echo
log "учётные данные Basic Auth: ${CREDENTIALS} (значение в вывод не печатается)"
log "индексация выключена, X-Robots-Tag: noindex, nofollow, robots.txt: Disallow: /"

if [[ "${failures}" -gt 0 ]]; then
  die "проверок не прошло: ${failures}. Конфигурация применена, но результат не соответствует ожидаемому."
fi
