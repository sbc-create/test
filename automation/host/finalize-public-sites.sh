#!/usr/bin/env bash
# Публикация шести сайтов: три YummyAnime и три Lords.
#
#   sudo bash /srv/site-factory/repo/automation/host/finalize-public-sites.sh
#
# Одна команда делает всё привилегированное:
#   * обновляет Secret Hub и панель (перезапуск, иначе код не перечитывается);
#   * применяет уже сохранённые credentials Lords — без повторного ввода;
#   * ставит drop-in с LoadCredential и обновляет unit-файлы;
#   * снимает Basic Auth со всех шести сайтов и убирает ссылки на htpasswd;
#   * проверяет nginx -t, перезагружает nginx;
#   * перезапускает только затронутые службы и ждёт готовности;
#   * собирает живой каталог Lords из CDNVideoHub;
#   * выполняет публичную приёмку всех шести доменов.
#
# Идемпотентен: повторный запуск на уже опубликованных сайтах ничего не ломает.
#
# Чего скрипт НЕ делает: не создаёт форм ввода credentials, не читает и не
# печатает значения секретов, не включает индексацию, не трогает базы и
# контейнеры YummyAnime, не выпускает сертификаты.

set -Eeuo pipefail

readonly REPO=/srv/site-factory/repo
readonly LORDS_NGINX=/etc/nginx/lords
readonly SITES_AVAILABLE=/etc/nginx/sites-available
readonly LORDS_UNITS=(lords-01.service lords-02.service lords-03.service)
readonly LORDS_SITES=(lords-01 lords-02 lords-03)
readonly LORDS_DOMAINS=(lordfilm47.space lordserial33.biz 1lordserials1.online)
readonly LORDS_PORTS=(9101 9102 9103)
readonly YUMMY_DOMAINS=(yummyani.site yummyani.org yummyani.biz)
readonly YUMMY_CONFS=(yummyani.site.conf yummyani.org.conf yummyani.biz.conf)
readonly HUB_UNIT=site-factory-secret-hub.service
readonly PANEL_UNIT=site-factory-secret-panel.service

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

STAGE="запуск"
stage() { STAGE="$1"; log "$1"; }

WORKDIR=""
BACKUP=""
NGINX_TOUCHED=0

restore_nginx() {
  [[ "${NGINX_TOUCHED}" -eq 1 && -d "${BACKUP}/nginx" ]] || return 0
  warn "возвращаю конфигурацию nginx из копии"
  cp -a "${BACKUP}/nginx/." /etc/nginx/ 2>/dev/null || true
  if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx >/dev/null 2>&1 || true
    warn "конфигурация возвращена"
  else
    warn "ВНИМАНИЕ: nginx -t не проходит и после возврата; reload не выполнялся"
    warn "копия: ${BACKUP}/nginx"
  fi
  NGINX_TOUCHED=0
}

on_error() {
  local line="$1" cmd="$2"
  trap - ERR
  set +e
  case "${cmd}" in
    *token*|*TOKEN*|*credential*|*secret*) cmd='<команда работы с секретами скрыта>' ;;
  esac
  printf '\033[31m[x]\033[0m отказ на этапе: %s (строка %s)\n' "${STAGE}" "${line}" >&2
  printf '\033[31m[x]\033[0m команда: %s\n' "${cmd}" >&2
  restore_nginx
  [[ -n "${WORKDIR}" && -d "${WORKDIR}" ]] && rm -rf -- "${WORKDIR}"
  exit 1
}
trap 'on_error "${LINENO}" "${BASH_COMMAND}"' ERR

[[ ${EUID} -eq 0 ]] || die "нужен root: sudo bash $0"
[[ -d "${REPO}" ]] || die "нет репозитория ${REPO}"

HEAD_SHA="$(git -C "${REPO}" rev-parse HEAD 2>/dev/null || true)"
[[ -n "${HEAD_SHA}" ]] || die "не прочитать commit ${REPO}"
log "deployed SHA: ${HEAD_SHA}"

PY="${REPO}/.venv/bin/python"
[[ -x "${PY}" ]] || PY="$(command -v python3)"
[[ -n "${PY}" ]] || die "python3 не найден"

WORKDIR="$(mktemp -d /run/finalize-public.XXXXXX)"
chmod 0700 "${WORKDIR}"
BACKUP="${WORKDIR}/backup"
install -d -m 0700 "${BACKUP}"
cp -a /etc/nginx "${BACKUP}/nginx"
log "копия /etc/nginx: ${BACKUP}/nginx"

# --------------------------------------------------------------------------
# 1. Secret Hub: перезапуск, иначе исправления не перечитываются
# --------------------------------------------------------------------------
stage "обновление Secret Hub"
# `enable --now` для работающей службы не делает ничего: процесс продолжит
# крутить код, загруженный при старте. Именно на этом Lords и встали —
# исправление лежало на диске, а панель отвечала прежним «цель недоступна».
systemctl daemon-reload
for unit in "${HUB_UNIT}" "${PANEL_UNIT}"; do
  systemctl restart "${unit}"
  for _ in $(seq 1 20); do
    systemctl is-active --quiet "${unit}" && break
    sleep 1
  done
  systemctl is-active --quiet "${unit}" || {
    journalctl -u "${unit}" --no-pager -n 20 >&2
    die "${unit} не запустился"
  }
  log "  ${unit}: active"
done

# --------------------------------------------------------------------------
# 2. Применение сохранённых credentials Lords
# --------------------------------------------------------------------------
stage "применение сохранённых credentials Lords"
# Работает с уже сохранённой активной версией: новых не создаёт и ввода не
# требует. Значения не печатаются — только имена потребителей и статусы.
if ! "${PY}" -m factory.secret_hub.rootcmd reconcile --portfolio lords 2>&1 \
     | sed 's/^/    /'; then
  die "credentials Lords не применились; см. вывод выше"
fi

for site in "${LORDS_SITES[@]}"; do
  dropin="/etc/systemd/system/${site}.service.d/10-cdnvideohub-credentials.conf"
  [[ -f "${dropin}" ]] || die "drop-in ${dropin} не создан — credentials не применены"
done
log "  drop-in созданы для трёх юнитов"
systemctl daemon-reload

# --------------------------------------------------------------------------
# 3. Basic Auth: снять со всех шести сайтов
# --------------------------------------------------------------------------
stage "снятие Basic Auth"
NGINX_TOUCHED=1

# Lords: конфигурация перерисовывается генератором, в котором пароля больше нет.
( cd "${REPO}" && "${PY}" -m factory lords-staging >/dev/null ) \
  || die "не собралась конфигурация Lords"
for site in "${LORDS_SITES[@]}"; do
  generated="${REPO}/artifacts/lords/staging/nginx/phase2/${site}.conf"
  [[ -f "${generated}" ]] || die "нет ${generated}"
  grep -q 'auth_basic "' "${generated}" && die "в собранной конфигурации ${site} остался пароль"
  install -m 0644 "${generated}" "${LORDS_NGINX}/${site}.conf"
done
rm -f "${LORDS_NGINX}"/activation/*.conf 2>/dev/null || true

# YummyAnime: конфигурации правятся точечно — их генератор живёт в другом
# репозитории, и переписывать их целиком отсюда было бы вторжением.
for conf in "${YUMMY_CONFS[@]}"; do
  target="${SITES_AVAILABLE}/${conf}"
  [[ -f "${target}" ]] || { warn "нет ${target}"; continue; }
  sed -i -e '/auth_basic_user_file/d' -e '/auth_basic[[:space:]]*"/d' "${target}"
done

# Ни одной ссылки на htpasswd не должно остаться нигде в /etc/nginx.
if grep -rn "auth_basic_user_file" /etc/nginx/ 2>/dev/null | grep -q .; then
  grep -rn "auth_basic_user_file" /etc/nginx/ >&2
  die "остались ссылки на htpasswd"
fi
log "  ссылок на htpasswd не осталось"

nginx -t >/dev/null 2>&1 || { nginx -t 2>&1 | sed 's/^/    /' >&2; die "nginx -t не прошёл"; }
systemctl reload nginx
sleep 1
log "  nginx перезагружен"

# Пароль не должен вернуться при следующем выкате.
for stale in "${LORDS_NGINX}/.htpasswd" /etc/nginx/yummyani-staging.htpasswd; do
  [[ -f "${stale}" ]] && { rm -f "${stale}"; log "  удалён ${stale}"; }
done
[[ -f /root/lords-staging-credentials ]] && rm -f /root/lords-staging-credentials

# --------------------------------------------------------------------------
# 4. Живой каталог Lords
# --------------------------------------------------------------------------
stage "сборка живого каталога Lords"
# Значения берутся из файлов Secret Hub, а не из окружения: окружение видно в
# `systemctl show` и в дампе процесса.
CREDS_DIR="/etc/site-factory/secrets/lords/lords-01"
[[ -r "${CREDS_DIR}/cdnvideohub-api-token" ]] \
  || die "нет файла credentials ${CREDS_DIR}/cdnvideohub-api-token"

if ! ( cd "${REPO}" && CREDENTIALS_DIRECTORY="${CREDS_DIR}" \
        CDNVIDEOHUB_API_TOKEN_CREDENTIAL=cdnvideohub-api-token \
        CDNVIDEOHUB_PUBLISHER_ID_CREDENTIAL=cdnvideohub-publisher-id \
        "${PY}" -m factory lords-live ); then
  die "живой каталог не собрался — переключение не выполнено"
fi

# Раскладка релизов и перезапуск только трёх юнитов Lords.
BUNDLE="${REPO}/artifacts/lords/bundle"
for index in "${!LORDS_SITES[@]}"; do
  site="${LORDS_SITES[${index}]}"
  archive="${BUNDLE}/${site}.tar"
  [[ -f "${archive}" ]] || die "нет пакета ${archive}"
  release="$(sha256sum "${archive}" | cut -c1-12)"
  runtime="/srv/lords/${site}"
  target="${runtime}/releases/${release}"
  if [[ ! -d "${target}" ]]; then
    install -d -m 0755 "${target}.tmp"
    tar -xf "${archive}" -C "${target}.tmp"
    chown -R lords:lords "${target}.tmp"
    mv "${target}.tmp" "${target}"
  fi
  ln -sfn "${target}" "${runtime}/.current.new"
  mv -Tf "${runtime}/.current.new" "${runtime}/current"
  chown -h lords:lords "${runtime}/current"
  log "  ${site}: релиз ${release}"
done

stage "перезапуск юнитов Lords"
for unit in "${LORDS_UNITS[@]}"; do
  systemctl restart "${unit}"
done
for index in "${!LORDS_PORTS[@]}"; do
  port="${LORDS_PORTS[${index}]}"
  ready=0
  for _ in $(seq 1 30); do
    curl -fsS --max-time 3 "http://127.0.0.1:${port}/readyz" >/dev/null 2>&1 && { ready=1; break; }
    sleep 1
  done
  [[ "${ready}" -eq 1 ]] || die "${LORDS_SITES[${index}]}: /readyz не ответил"
done
sleep 3
for unit in "${LORDS_UNITS[@]}"; do
  # Restart loop виден по числу перезапусков за короткое время.
  n="$(systemctl show -p NRestarts --value "${unit}" 2>/dev/null || echo 0)"
  [[ "${n}" -lt 3 ]] || die "${unit}: похоже на restart loop (NRestarts=${n})"
  systemctl is-active --quiet "${unit}" || die "${unit} не активен"
done
log "  три юнита активны, restart loop не обнаружен"

# --------------------------------------------------------------------------
# 5. Публичная приёмка шести доменов
# --------------------------------------------------------------------------
stage "публичная приёмка"
FAILURES=0
check() {
  local label="$1" got="$2" want="$3"
  if [[ "${got}" == "${want}" ]]; then
    printf '    OK   %s: %s\n' "${label}" "${got}"
  else
    printf '    FAIL %s: %s, ожидался %s\n' "${label}" "${got}" "${want}" >&2
    FAILURES=$((FAILURES + 1))
  fi
}

probe_all() {
  local domain="$1"
  local pin=(--resolve "${domain}:443:127.0.0.1")
  local code
  code="$(curl -sS -o /dev/null -D "${WORKDIR}/h" -w '%{http_code}' --max-time 20 \
          "${pin[@]}" "https://${domain}/" 2>/dev/null || echo curl-error)"
  check "${domain} /" "${code}" "200"
  if grep -qi '^www-authenticate:' "${WORKDIR}/h"; then
    printf '    FAIL %s: остался WWW-Authenticate\n' "${domain}" >&2
    FAILURES=$((FAILURES + 1))
  fi
  grep -qi '^x-robots-tag:.*noindex' "${WORKDIR}/h" \
    || { printf '    FAIL %s: нет noindex\n' "${domain}" >&2; FAILURES=$((FAILURES + 1)); }
  local robots
  robots="$(curl -sS --max-time 20 "${pin[@]}" "https://${domain}/robots.txt" 2>/dev/null || true)"
  grep -q 'Disallow: /' <<<"${robots}" \
    || { printf '    FAIL %s: robots.txt не закрывает сайт\n' "${domain}" >&2; FAILURES=$((FAILURES + 1)); }
}

for domain in "${YUMMY_DOMAINS[@]}" "${LORDS_DOMAINS[@]}"; do
  probe_all "${domain}"
done

# Каталог Lords обязан быть непустым и не fixture.
for index in "${!LORDS_DOMAINS[@]}"; do
  domain="${LORDS_DOMAINS[${index}]}"
  body="$(curl -sS --max-time 20 --resolve "${domain}:443:127.0.0.1" \
          "https://${domain}/" 2>/dev/null || true)"
  grep -q 'card__title' <<<"${body}" \
    || { printf '    FAIL %s: на главной нет карточек каталога\n' "${domain}" >&2
         FAILURES=$((FAILURES + 1)); }
done

if [[ "${FAILURES}" -gt 0 ]]; then
  warn "приёмка не прошла: отказов ${FAILURES}"
  restore_nginx
  die "часть проверок не прошла; конфигурация nginx возвращена"
fi

rm -rf -- "${WORKDIR}"
echo
log "готово: шесть сайтов публичны"
for domain in "${YUMMY_DOMAINS[@]}" "${LORDS_DOMAINS[@]}"; do
  printf '      https://%s/\n' "${domain}"
done
log "индексация закрыта: noindex, nofollow и robots.txt Disallow: /"
log "PUBLIC_SITES_VERIFIED=pass"
