#!/usr/bin/env bash
# Одноразовая веб-активация живого каталога Lords.
#
# Открывает форму на https://lordfilm47.space/__lords-activate, принимает
# учётные данные из браузера, активирует живой каталог и убирает форму.
#
# Схема простая и без косвенности. На время приёма Basic Auth снимается со всех
# трёх сайтов, а адрес формы вписывается прямо в серверный блок — не через
# include отдельного каталога. Прежняя схема была хрупкой ровно этим: файл со
# временным адресом лежал на месте, `nginx -t` проходил, а include в
# развёрнутой конфигурации отсутствовал, и форма молча уходила под пароль.
#
# ГЛАВНОЕ. Прежде чем напечатать адрес и код, сценарий проверяет НАСТОЯЩИЙ
# nginx этого хоста: по петле с корректным SNI и обычным публичным запросом,
# по всем трём доменам, с проверкой сертификата и маркера в теле. Не сошлось —
# ни адрес, ни код не печатаются, пароль возвращается, конфигурация
# восстанавливается из копии, и печатается диагностика.
#
# Что не делается: YummyAnime не трогается, сертификаты не выпускаются,
# индексация не включается — noindex, robots Disallow и пустой sitemap остаются
# на месте и от пароля не зависят.

set -Eeuo pipefail

readonly REPO=/srv/site-factory/repo/var/lords-deploy
readonly EXPECT_SHA="${LORDS_EXPECT_SHA:-}"
readonly NGINX_DIR=/etc/nginx/lords
readonly ACTIVATION_DIR="${NGINX_DIR}/activation"
readonly LOCATION_PATH=/__lords-activate
readonly SECRET_DIR=/etc/site-factory/secrets/cdnvideohub/lords
readonly TOKEN_FILE="${SECRET_DIR}/api-token"
readonly PUBLISHER_FILE="${SECRET_DIR}/publisher-id"
readonly TTL="${LORDS_INTAKE_TTL:-900}"
readonly SITES=(lords-01 lords-02 lords-03)
readonly DOMAINS=(lordfilm47.space lordserial33.biz 1lordserials1.online)
readonly FORM_DOMAIN=lordfilm47.space

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

WORKDIR=""
INTAKE_PID=""
BACKUP_DIR=""
CONFIG_APPLIED=0
KEEP_AUTH_OFF=0
TEARDOWN_DONE=""

# --------------------------------------------------------------------------
# Восстановление
# --------------------------------------------------------------------------
restore_config() {
  # Возврат конфигурации сайтов из копии. Пароль вместе с ней.
  [[ "${CONFIG_APPLIED}" -eq 1 && -d "${BACKUP_DIR}/nginx-lords" ]] || return 0
  for site in "${SITES[@]}"; do
    [[ -f "${BACKUP_DIR}/nginx-lords/${site}.conf" ]] \
      && install -m 0644 "${BACKUP_DIR}/nginx-lords/${site}.conf" "${NGINX_DIR}/${site}.conf"
  done
  rm -f "${ACTIVATION_DIR}"/*.conf 2>/dev/null || true
  if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx >/dev/null 2>&1 || true
    warn "конфигурация сайтов возвращена из копии, Basic Auth восстановлен"
  else
    warn "ВНИМАНИЕ: после возврата nginx -t не проходит. Reload не выполнялся."
    warn "Копия: ${BACKUP_DIR}/nginx-lords"
  fi
  CONFIG_APPLIED=0
}

stop_intake() {
  if [[ -n "${INTAKE_PID}" ]] && kill -0 "${INTAKE_PID}" 2>/dev/null; then
    kill -TERM "${INTAKE_PID}" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "${INTAKE_PID}" 2>/dev/null || break
      sleep 0.5
    done
    kill -KILL "${INTAKE_PID}" 2>/dev/null || true
  fi
  INTAKE_PID=""
}

teardown() {
  [[ -n "${TEARDOWN_DONE}" ]] && return 0
  TEARDOWN_DONE=1
  stop_intake
  if [[ "${KEEP_AUTH_OFF}" -eq 1 ]]; then
    # Успешная активация: пароль остаётся снятым, убирается только форма.
    remove_form_keep_auth_off
  else
    restore_config
  fi
  [[ -n "${WORKDIR}" && -d "${WORKDIR}" ]] && rm -rf -- "${WORKDIR}"
  return 0
}
trap 'teardown' EXIT
trap 'warn "прервано на строке ${LINENO}"; teardown; exit 1' ERR

remove_form_keep_auth_off() {
  # Пароль снят окончательно, но форма жить не должна: адрес обязан отвечать 404.
  log "убираю форму, пароль остаётся снятым"
  # --form-site none: форму не получает ни один сайт. Пароль остаётся снятым.
  ( cd "${REPO}" && "${PY}" -m factory lords-activation-config \
      --out "${WORKDIR}/final" --port 0 --form-site none --marker final \
      --no-basic-auth >/dev/null ) || {
    warn "не удалось собрать конфигурацию без формы"; return 0; }
  for site in "${SITES[@]}"; do
    [[ -f "${WORKDIR}/final/${site}.conf" ]] \
      && install -m 0644 "${WORKDIR}/final/${site}.conf" "${NGINX_DIR}/${site}.conf"
  done
  rm -f "${ACTIVATION_DIR}"/*.conf 2>/dev/null || true
  if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx >/dev/null 2>&1 || true
    log "форма снята"
  else
    warn "nginx -t не прошёл после снятия формы; конфигурация возвращена"
    restore_config
  fi
}

[[ ${EUID} -eq 0 ]] || die "нужен root: sudo bash $0"
[[ -n "${EXPECT_SHA}" ]] || die "не передан LORDS_EXPECT_SHA"
[[ -d "${REPO}" ]] || die "нет deployment worktree: ${REPO}"

HEAD_SHA="$(git -C "${REPO}" rev-parse HEAD 2>/dev/null || true)"
[[ "${HEAD_SHA}" == "${EXPECT_SHA}" ]] \
  || die "ожидался commit ${EXPECT_SHA}, в worktree ${HEAD_SHA:-неизвестно}"

PY="${REPO}/.venv/bin/python"
[[ -x "${PY}" ]] || PY="$(command -v python3)"
[[ -n "${PY}" ]] || die "python3 не найден"
[[ -d "${NGINX_DIR}" ]] || die "нет ${NGINX_DIR}: сначала должен работать стенд"
for domain in "${DOMAINS[@]}"; do
  [[ -s "/etc/letsencrypt/live/${domain}/fullchain.pem" ]] \
    || die "нет сертификата ${domain}"
done

log "deployed SHA: ${HEAD_SHA}"

# --------------------------------------------------------------------------
# 1. Уборка следов прошлого запуска
# --------------------------------------------------------------------------
if compgen -G "${ACTIVATION_DIR}/*.conf" >/dev/null 2>&1; then
  warn "найдены временные адреса прошлого запуска — убираю"
  rm -f "${ACTIVATION_DIR}"/*.conf
fi
if pgrep -f "factory.lords.web_intake_main" >/dev/null 2>&1; then
  warn "найден приёмный процесс прошлого запуска — останавливаю"
  pkill -TERM -f "factory.lords.web_intake_main" 2>/dev/null || true
  sleep 2
  pkill -KILL -f "factory.lords.web_intake_main" 2>/dev/null || true
fi
rm -rf -- /run/lords-activation.* 2>/dev/null || true

WORKDIR="$(mktemp -d /run/lords-activation.XXXXXX)"
chmod 0700 "${WORKDIR}"

# --------------------------------------------------------------------------
# 2. Копия фактической конфигурации
# --------------------------------------------------------------------------
BACKUP_DIR="${WORKDIR}/backup"
install -d -m 0700 "${BACKUP_DIR}" "${BACKUP_DIR}/nginx-lords"
for site in "${SITES[@]}"; do
  [[ -f "${NGINX_DIR}/${site}.conf" ]] \
    && cp -a "${NGINX_DIR}/${site}.conf" "${BACKUP_DIR}/nginx-lords/${site}.conf"
done
tar -czf "${BACKUP_DIR}/etc-nginx.tar.gz" -C /etc nginx 2>/dev/null || true
log "копия конфигурации: ${BACKUP_DIR}"

# --------------------------------------------------------------------------
# 3. Приёмный процесс
# --------------------------------------------------------------------------
ACCESS_CODE="$("${PY}" -c \
  'from factory.lords.web_intake import generate_code; print(generate_code())')"
FORM_MARKER="lords-form-$("${PY}" -c \
  'import secrets; print(secrets.token_hex(8))')"

PROBE_URL="$("${PY}" - "${REPO}" <<'PY'
import pathlib, sys, urllib.parse, yaml
raw = yaml.safe_load(
    (pathlib.Path(sys.argv[1]) / "knowledge/cdnvideohub/content-api.yaml")
    .read_text(encoding="utf-8"))
base, path = raw["base_url"], raw["endpoints"]["titles"]["path"]
print(urllib.parse.urljoin(base, path) + f"?{raw['pagination']['size_param']}=1")
PY
)"

( cd "${REPO}" && "${PY}" -m factory.lords.web_intake_main \
    --code "${ACCESS_CODE}" --ttl "${TTL}" \
    --token-file "${TOKEN_FILE}" --publisher-file "${PUBLISHER_FILE}" \
    --probe-url "${PROBE_URL}" \
    --port-file "${WORKDIR}/port" --result-file "${WORKDIR}/result.json" \
    --marker "${FORM_MARKER}" \
    >"${WORKDIR}/intake.log" 2>&1 ) &
INTAKE_PID=$!

for _ in $(seq 1 40); do
  [[ -s "${WORKDIR}/port" ]] && break
  kill -0 "${INTAKE_PID}" 2>/dev/null || die "приёмный процесс не запустился"
  sleep 0.25
done
[[ -s "${WORKDIR}/port" ]] || die "приёмный процесс не сообщил порт"
INTAKE_PORT="$(cat "${WORKDIR}/port")"

# --------------------------------------------------------------------------
# 4. Конфигурация окна: пароль снят, форма вписана в серверный блок
# --------------------------------------------------------------------------
log "снимаю Basic Auth на время приёма и ставлю форму"
( cd "${REPO}" && "${PY}" -m factory lords-activation-config \
    --out "${WORKDIR}/open" --port "${INTAKE_PORT}" \
    --form-site lords-01 --marker "${FORM_MARKER}" --no-basic-auth ) \
  || die "не удалось собрать конфигурацию окна"

for site in "${SITES[@]}"; do
  install -m 0644 "${WORKDIR}/open/${site}.conf" "${NGINX_DIR}/${site}.conf"
done
CONFIG_APPLIED=1

if ! nginx -t >/dev/null 2>&1; then
  nginx -t 2>&1 | sed 's/^/    /' >&2
  die "nginx -t не прошёл с конфигурацией окна"
fi
systemctl reload nginx
sleep 1

# --------------------------------------------------------------------------
# 5. Живая проверка НАСТОЯЩЕГО nginx. До неё ничего не печатается.
# --------------------------------------------------------------------------
GATE_FAILURES=0
GATE_REPORT="${WORKDIR}/gate.txt"
: > "${GATE_REPORT}"

record() { printf '%s\n' "$*" >> "${GATE_REPORT}"; }

# Код ответа и наличие WWW-Authenticate одним запросом.
probe() {
  local url="$1"; shift
  curl -sS -o /dev/null -D "${WORKDIR}/hdr" -w '%{http_code}' --max-time 20 "$@" "${url}" \
    2>/dev/null || printf 'curl-error'
}
has_auth_header() { grep -qi '^www-authenticate:' "${WORKDIR}/hdr"; }

check() {
  local label="$1" code="$2" want="$3"
  if [[ "${code}" == "${want}" ]]; then
    record "  OK   ${label}: ${code}"
  else
    record "  FAIL ${label}: ${code}, ожидался ${want}"
    GATE_FAILURES=$((GATE_FAILURES + 1))
  fi
}

log "проверяю фактический nginx хоста"

for domain in "${DOMAINS[@]}"; do
  pin=(--resolve "${domain}:443:127.0.0.1")

  code="$(probe "https://${domain}/" "${pin[@]}")"
  check "${domain} / (петля, SNI)" "${code}" "200"
  if has_auth_header; then
    record "  FAIL ${domain} /: остался WWW-Authenticate"
    GATE_FAILURES=$((GATE_FAILURES + 1))
  fi

  # Сертификат обязан совпадать с именем.
  served="$(echo | openssl s_client -connect 127.0.0.1:443 -servername "${domain}" 2>/dev/null || true)"
  verdict="$(printf '%s' "${served}" | openssl x509 -noout -checkhost "${domain}" 2>/dev/null || true)"
  if [[ "${verdict}" == *"does match certificate"* ]]; then
    record "  OK   ${domain}: сертификат совпадает с именем"
  else
    record "  FAIL ${domain}: сертификат не совпадает с именем"
    GATE_FAILURES=$((GATE_FAILURES + 1))
  fi

  # Индексация обязана остаться закрытой.
  robots="$(curl -sS --max-time 20 "${pin[@]}" "https://${domain}/robots.txt" 2>/dev/null || true)"
  if grep -q 'Disallow: /' <<<"${robots}"; then
    record "  OK   ${domain}: robots.txt закрывает сайт"
  else
    record "  FAIL ${domain}: robots.txt не закрывает сайт"
    GATE_FAILURES=$((GATE_FAILURES + 1))
  fi
done

# Форма: по петле и обычным публичным запросом.
FORM_URL="https://${FORM_DOMAIN}${LOCATION_PATH}"

code="$(probe "${FORM_URL}" --resolve "${FORM_DOMAIN}:443:127.0.0.1")"
check "форма (петля, SNI)" "${code}" "200"
has_auth_header && { record "  FAIL форма (петля): WWW-Authenticate присутствует"; \
                     GATE_FAILURES=$((GATE_FAILURES + 1)); }

code="$(probe "${FORM_URL}")"
check "форма (публичный запрос)" "${code}" "200"
has_auth_header && { record "  FAIL форма (публично): WWW-Authenticate присутствует"; \
                     GATE_FAILURES=$((GATE_FAILURES + 1)); }

body="$(curl -sS --max-time 20 --resolve "${FORM_DOMAIN}:443:127.0.0.1" "${FORM_URL}" 2>/dev/null || true)"
if grep -qF "${FORM_MARKER}" <<<"${body}"; then
  record "  OK   форма отдаёт свой маркер"
else
  record "  FAIL форма не отдаёт маркер: отвечает не приёмник"
  GATE_FAILURES=$((GATE_FAILURES + 1))
fi

# --------------------------------------------------------------------------
# 6. Не сошлось — ничего не печатаем и всё возвращаем
# --------------------------------------------------------------------------
if [[ "${GATE_FAILURES}" -gt 0 ]]; then
  echo >&2
  warn "LIVE_FORM_VERIFIED=fail — адрес и код не печатаются"
  echo >&2
  printf 'deployed SHA: %s\n' "${HEAD_SHA}" >&2
  echo "--- проверки ---" >&2
  cat "${GATE_REPORT}" >&2
  echo "--- какой файл обслуживает ${FORM_DOMAIN} ---" >&2
  grep -rl "server_name.*${FORM_DOMAIN}" /etc/nginx/ 2>/dev/null | sed 's/^/    /' >&2 || true
  echo "--- server/location из фактического nginx -T (без секретов) ---" >&2
  nginx -T 2>/dev/null \
    | awk '/server_name|location |auth_basic|include |proxy_pass|listen /' \
    | grep -v 'auth_basic_user_file' \
    | sed 's/^/    /' >&2 || true
  stop_intake
  restore_config
  die "фактическая проверка не прошла; Basic Auth восстановлен, форма снята"
fi

log "LIVE_FORM_VERIFIED=pass"
record "LIVE_FORM_VERIFIED=pass"

# --------------------------------------------------------------------------
# 7. Только теперь — адрес и код
# --------------------------------------------------------------------------
echo
printf '  URL:   %s\n' "${FORM_URL}"
printf '  Код:   %s\n' "${ACCESS_CODE}"
printf '  Срок:  %s минут\n' "$((TTL / 60))"
printf '  Статус: ожидание ввода\n'
echo
warn "на время окна три сайта открыты без пароля; индексация остаётся закрытой"
echo

# --------------------------------------------------------------------------
# 8. Ожидание
# --------------------------------------------------------------------------
wait "${INTAKE_PID}" && INTAKE_RC=0 || INTAKE_RC=$?
INTAKE_PID=""

ACCEPTED="$("${PY}" - "${WORKDIR}/result.json" <<'PY'
import json, pathlib, sys
try:
    print("yes" if json.loads(pathlib.Path(sys.argv[1]).read_text())["accepted"] else "no")
except Exception:
    print("no")
PY
)"

if [[ "${ACCEPTED}" != "yes" ]]; then
  warn "учётные данные не приняты (код возврата ${INTAKE_RC})"
  restore_config
  die "Basic Auth восстановлен, форма снята, ничего не изменено"
fi

log "учётные данные приняты и сохранены (значения не печатались)"

# --------------------------------------------------------------------------
# 9. Активация
# --------------------------------------------------------------------------
log "переключаю каталог на живой источник"
if LORDS_NONINTERACTIVE=1 LORDS_RIGHTS_CONFIRMED=yes \
   LORDS_KEEP_SECRETS_ON_ROLLBACK=1 LORDS_EXPECT_SHA="${EXPECT_SHA}" \
   bash "${REPO}/automation/host/activate-lords-live.sh"; then
  log "живой каталог активирован"
else
  warn "активация не прошла"
  restore_config
  die "стенд возвращён на fixture-релиз, Basic Auth восстановлен.
Сохранённые учётные данные не удалены и не печатались."
fi

# --------------------------------------------------------------------------
# 10. После успеха: пароль снят окончательно, форма исчезает
# --------------------------------------------------------------------------
KEEP_AUTH_OFF=1
remove_form_keep_auth_off
TEARDOWN_DONE=1
stop_intake

sleep 1
FINAL_FAIL=0
for domain in "${DOMAINS[@]}"; do
  pin=(--resolve "${domain}:443:127.0.0.1")
  code="$(probe "https://${domain}/" "${pin[@]}")"
  [[ "${code}" == "200" ]] || { warn "  ${domain}: ${code}, ожидался 200"; FINAL_FAIL=1; }
  robots="$(curl -sS --max-time 20 "${pin[@]}" "https://${domain}/robots.txt" 2>/dev/null || true)"
  grep -q 'Disallow: /' <<<"${robots}" \
    || { warn "  ${domain}: robots.txt не закрывает сайт"; FINAL_FAIL=1; }
done
code="$(probe "https://${FORM_DOMAIN}${LOCATION_PATH}" --resolve "${FORM_DOMAIN}:443:127.0.0.1")"
[[ "${code}" == "404" ]] || { warn "  форма отвечает ${code}, ожидался 404"; FINAL_FAIL=1; }

[[ "${FINAL_FAIL}" -eq 0 ]] || die "итоговая проверка не прошла; разберитесь по выводу выше"

echo
log "готово: три сайта на живом каталоге, без Basic Auth, индексация закрыта"
for domain in "${DOMAINS[@]}"; do printf '      https://%s/\n' "${domain}"; done
log "форма снята, ${LOCATION_PATH} отвечает 404"
log "YummyAnime не затронут"
