#!/usr/bin/env bash
# Окончательное снятие Basic Auth с трёх сайтов Lords.
#
# Пароль когда-то завёл сценарий первичного выката, а не человек. Решение
# владельца — сайты Lords публичны уже на fixture-каталоге. Этот сценарий
# снимает пароль, подтверждает результат обращением к настоящему nginx и
# уничтожает сам пароль, чтобы вернуть его было нечем.
#
# Идемпотентен: повторный запуск на уже публичных сайтах ничего не ломает и
# ничего не создаёт.
#
# Что НЕ делается:
#   * YummyAnime не трогается — ни конфигурация, ни его htpasswd, ни его
#     учётные данные;
#   * индексация не включается: X-Robots-Tag, robots.txt с Disallow и пустой
#     sitemap остаются на месте и от пароля никогда не зависели;
#   * бэкапы релизов и конфигураций не удаляются — только копии пароля внутри
#     них.

set -Eeuo pipefail

readonly REPO=/srv/site-factory/repo/var/lords-deploy
readonly EXPECT_SHA="${LORDS_EXPECT_SHA:-}"
readonly NGINX_DIR=/etc/nginx/lords
readonly HTPASSWD="${NGINX_DIR}/.htpasswd"
readonly CREDENTIALS=/root/lords-staging-credentials
readonly BACKUP_ROOT=/var/backups/lords-staging
readonly SITES=(lords-01 lords-02 lords-03)
readonly DOMAINS=(lordfilm47.space lordserial33.biz 1lordserials1.online)

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

WORKDIR=""
BACKUP_DIR=""
APPLIED=0

# Возврат к рабочей конфигурации — но всё равно без пароля.
#
# Копия нужна на случай, если новая конфигурация окажется нерабочей: тогда
# возвращается прежняя, из неё вычищается auth_basic, и nginx проверяется
# снова. Пароль не возвращается ни при каком исходе — в этом весь смысл.
restore_working_without_auth() {
  [[ "${APPLIED}" -eq 1 && -d "${BACKUP_DIR}/nginx-lords" ]] || return 0
  warn "возвращаю прежнюю конфигурацию и вычищаю из неё пароль"
  for site in "${SITES[@]}"; do
    local source="${BACKUP_DIR}/nginx-lords/${site}.conf"
    [[ -f "${source}" ]] || continue
    sed -e '/auth_basic_user_file/d' -e '/auth_basic[[:space:]]*"/d' \
        "${source}" > "${NGINX_DIR}/${site}.conf"
    chmod 0644 "${NGINX_DIR}/${site}.conf"
  done
  if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx >/dev/null 2>&1 || true
    warn "прежняя конфигурация возвращена, пароль из неё удалён"
  else
    warn "ВНИМАНИЕ: nginx -t не проходит и после возврата. Reload не выполнялся."
    warn "Копия нетронутой конфигурации: ${BACKUP_DIR}/nginx-lords"
  fi
}

cleanup() {
  [[ -n "${WORKDIR}" && -d "${WORKDIR}" ]] && rm -rf -- "${WORKDIR}"
  return 0
}
trap 'cleanup' EXIT
trap 'warn "прервано на строке ${LINENO}"; restore_working_without_auth; cleanup; exit 1' ERR

[[ ${EUID} -eq 0 ]] || die "нужен root: sudo bash $0"
[[ -n "${EXPECT_SHA}" ]] || die "не передан LORDS_EXPECT_SHA"
[[ -d "${REPO}" ]] || die "нет deployment worktree: ${REPO}"

HEAD_SHA="$(git -C "${REPO}" rev-parse HEAD 2>/dev/null || true)"
[[ "${HEAD_SHA}" == "${EXPECT_SHA}" ]] \
  || die "ожидался commit ${EXPECT_SHA}, в worktree ${HEAD_SHA:-неизвестно}"
log "deployed SHA: ${HEAD_SHA}"

PY="${REPO}/.venv/bin/python"
[[ -x "${PY}" ]] || PY="$(command -v python3)"
[[ -n "${PY}" ]] || die "python3 не найден"
[[ -d "${NGINX_DIR}" ]] || die "нет ${NGINX_DIR}"

WORKDIR="$(mktemp -d /run/lords-noauth.XXXXXX)"
chmod 0700 "${WORKDIR}"

# --------------------------------------------------------------------------
# 1. Копия фактической конфигурации
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
# 2. Конфигурация без пароля
# --------------------------------------------------------------------------
log "перерисовываю конфигурацию трёх сайтов без Basic Auth"
( cd "${REPO}" && "${PY}" -m factory lords-activation-config \
    --out "${WORKDIR}/public" --port 0 --form-site none --marker none --no-basic-auth ) \
  || die "не удалось собрать конфигурацию без пароля"

for site in "${SITES[@]}"; do
  grep -q 'auth_basic[[:space:]]*"' "${WORKDIR}/public/${site}.conf" \
    && die "в собранной конфигурации ${site} остался auth_basic — не применяю"
  install -m 0644 "${WORKDIR}/public/${site}.conf" "${NGINX_DIR}/${site}.conf"
done
APPLIED=1

if ! nginx -t >/dev/null 2>&1; then
  nginx -t 2>&1 | sed 's/^/    /' >&2
  restore_working_without_auth
  die "nginx -t не прошёл с конфигурацией без пароля"
fi
systemctl reload nginx
sleep 1

# --------------------------------------------------------------------------
# 3. Фактическая проверка настоящего nginx
# --------------------------------------------------------------------------
FAILURES=0
REPORT="${WORKDIR}/report.txt"
: > "${REPORT}"
record() { printf '%s\n' "$*" >> "${REPORT}"; }

probe() {
  local url="$1"; shift
  curl -sS -o /dev/null -D "${WORKDIR}/hdr" -w '%{http_code}' --max-time 20 "$@" "${url}" \
    2>/dev/null || printf 'curl-error'
}
fail() { record "  FAIL $*"; FAILURES=$((FAILURES + 1)); }

log "проверяю фактический nginx хоста"

for domain in "${DOMAINS[@]}"; do
  pin=(--resolve "${domain}:443:127.0.0.1")

  # apex по петле с корректным SNI.
  code="$(probe "https://${domain}/" "${pin[@]}")"
  [[ "${code}" == "200" ]] && record "  OK   ${domain} (петля): 200" \
    || fail "${domain} (петля): ${code}, ожидался 200"
  grep -qi '^www-authenticate:' "${WORKDIR}/hdr" \
    && fail "${domain}: остался WWW-Authenticate" \
    || record "  OK   ${domain}: пароля нет"
  grep -qi '^x-robots-tag:.*noindex' "${WORKDIR}/hdr" \
    && record "  OK   ${domain}: X-Robots-Tag noindex" \
    || fail "${domain}: нет X-Robots-Tag noindex"

  # apex публичным маршрутом.
  code="$(probe "https://${domain}/")"
  [[ "${code}" == "200" ]] && record "  OK   ${domain} (публично): 200" \
    || fail "${domain} (публично): ${code}, ожидался 200"
  grep -qi '^www-authenticate:' "${WORKDIR}/hdr" \
    && fail "${domain} (публично): остался WWW-Authenticate"

  # www обязан вести на apex.
  redirect="$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 20 \
    --resolve "www.${domain}:443:127.0.0.1" "https://www.${domain}/" 2>/dev/null || echo "curl-error -")"
  grep -q '^308 ' <<<"${redirect}" && record "  OK   www.${domain}: ${redirect}" \
    || fail "www.${domain}: ${redirect}, ожидался 308"

  # Сертификат обязан совпадать с именем.
  served="$(echo | openssl s_client -connect 127.0.0.1:443 -servername "${domain}" 2>/dev/null || true)"
  verdict="$(printf '%s' "${served}" | openssl x509 -noout -checkhost "${domain}" 2>/dev/null || true)"
  [[ "${verdict}" == *"does match certificate"* ]] \
    && record "  OK   ${domain}: сертификат совпадает" \
    || fail "${domain}: сертификат не совпадает с именем"

  # Индексация закрыта robots.txt.
  robots="$(curl -sS --max-time 20 "${pin[@]}" "https://${domain}/robots.txt" 2>/dev/null || true)"
  grep -q 'Disallow: /' <<<"${robots}" \
    && record "  OK   ${domain}: robots.txt закрывает сайт" \
    || fail "${domain}: robots.txt не закрывает сайт"
done

# Неизвестный Host не должен получать Lords.
unknown_body="$(curl -sS --max-time 20 -H 'Host: no-such-host.invalid' \
  http://127.0.0.1/ 2>/dev/null | head -c 2000 || true)"
if grep -qiE 'lords|lordfilm|lordserial' <<<"${unknown_body}"; then
  fail "неизвестный Host получает содержимое Lords"
else
  record "  OK   неизвестный Host не получает Lords"
fi

if [[ "${FAILURES}" -gt 0 ]]; then
  echo >&2
  warn "LORDS_PUBLIC_NOAUTH_VERIFIED=fail"
  printf 'deployed SHA: %s\n' "${HEAD_SHA}" >&2
  cat "${REPORT}" >&2
  echo "--- server/location из фактического nginx -T ---" >&2
  nginx -T 2>/dev/null | awk '/server_name|auth_basic|listen |proxy_pass/' \
    | sed 's/^/    /' >&2 || true
  restore_working_without_auth
  die "проверка не прошла; пароль всё равно не возвращён"
fi

cat "${REPORT}"
log "LORDS_PUBLIC_NOAUTH_VERIFIED=pass"

# --------------------------------------------------------------------------
# 4. Уничтожение самого пароля
# --------------------------------------------------------------------------
# Только после подтверждённого удаления: пока проверка не прошла, файл может
# ещё понадобиться для разбора.
stage_removed=0

if [[ -f "${HTPASSWD}" ]]; then
  # Путь проверяется явно: удаляется только файл Lords и только внутри его
  # каталога. Файл соседа лежит в другом месте и под это условие не подходит.
  if [[ "${HTPASSWD}" == "${NGINX_DIR}/.htpasswd" && "${NGINX_DIR}" == /etc/nginx/lords ]]; then
    rm -f "${HTPASSWD}"
    log "удалён ${HTPASSWD}"
    stage_removed=$((stage_removed + 1))
  else
    warn "путь ${HTPASSWD} не совпал с ожидаемым — не удаляю"
  fi
fi

if [[ -f "${CREDENTIALS}" ]]; then
  if [[ "${CREDENTIALS}" == /root/lords-staging-credentials ]]; then
    rm -f "${CREDENTIALS}"
    log "удалён ${CREDENTIALS}"
    stage_removed=$((stage_removed + 1))
  else
    warn "путь ${CREDENTIALS} не совпал с ожидаемым — не удаляю"
  fi
fi

# Копии пароля внутри бэкапов Lords. Сами бэкапы — конфигурации и релизы —
# остаются: они нужны для отката и пароля не содержат.
if [[ -d "${BACKUP_ROOT}" ]]; then
  while IFS= read -r stale; do
    [[ -n "${stale}" ]] || continue
    case "${stale}" in
      "${BACKUP_ROOT}"/*) rm -f "${stale}"; log "удалена копия пароля: ${stale}" ;;
      *) warn "пропущен путь вне ${BACKUP_ROOT}: ${stale}" ;;
    esac
  done < <(find "${BACKUP_ROOT}" -type f \
             \( -name '.htpasswd' -o -name 'lords-staging-credentials' \) 2>/dev/null)
fi

# Соседа не касались — подтверждаем это явно.
for foreign in /etc/nginx/.htpasswd /etc/nginx/yummyani/.htpasswd; do
  [[ -e "${foreign}" ]] && log "не тронут: ${foreign}"
done

echo
log "готово: три сайта Lords публичны, пароля больше нет"
for domain in "${DOMAINS[@]}"; do printf '      https://%s/\n' "${domain}"; done
log "индексация закрыта: X-Robots-Tag noindex, robots.txt Disallow: /"
log "YummyAnime не затронут"
