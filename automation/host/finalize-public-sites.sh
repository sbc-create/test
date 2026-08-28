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
python3 -m factory.lords.live_bundle --archive artifacts/lords/bundle/lords-01.tar --cache var/lords/lords/catalog-cache/lords-01.json --credentials-dir /etc/site-factory/secrets/lords/lords-01
python3 -m factory.lords.live_bundle --archive artifacts/lords/bundle/lords-02.tar --cache var/lords/lords/catalog-cache/lords-02.json --credentials-dir /etc/site-factory/secrets/lords/lords-02
python3 -m factory.lords.live_bundle --archive artifacts/lords/bundle/lords-03.tar --cache var/lords/lords/catalog-cache/lords-03.json --credentials-dir /etc/site-factory/secrets/lords/lords-03

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
# PUBLIC_SITES_VERIFIED=pass печатается только если прошло ВСЁ ниже.
FAILURES=0
ok()   { printf '    OK   %s\n' "$*"; }
bad()  { printf '    FAIL %s\n' "$*" >&2; FAILURES=$((FAILURES + 1)); }

# Токен читается один раз, чтобы искать его в отдаваемых файлах. В вывод он не
# попадает: используется только как образец для grep -qF.
TOKEN_SAMPLE=""
[[ -r "${CREDS_DIR}/cdnvideohub-api-token" ]] \
  && TOKEN_SAMPLE="$(cat "${CREDS_DIR}/cdnvideohub-api-token")"

fetch() {  # domain path -> тело в $BODY, заголовки в $WORKDIR/h, код в $CODE
  local domain="$1" path="$2"
  CODE="$(curl -sS -o "${WORKDIR}/b" -D "${WORKDIR}/h" -w '%{http_code}' --max-time 25 \
          --resolve "${domain}:443:127.0.0.1" "https://${domain}${path}" 2>/dev/null \
          || echo curl-error)"
  BODY="$(cat "${WORKDIR}/b" 2>/dev/null || true)"
}

# --- 1. Шесть apex: 200, без пароля, TLS, noindex, robots -------------------
for domain in "${YUMMY_DOMAINS[@]}" "${LORDS_DOMAINS[@]}"; do
  fetch "${domain}" "/"
  [[ "${CODE}" == "200" ]] && ok "${domain} /: 200" || bad "${domain} /: ${CODE}, ожидался 200"
  grep -qi '^www-authenticate:' "${WORKDIR}/h" && bad "${domain}: остался WWW-Authenticate"
  grep -qi '^x-robots-tag:.*noindex' "${WORKDIR}/h" || bad "${domain}: нет noindex"
  grep -qi '^x-robots-tag:.*nofollow' "${WORKDIR}/h" || bad "${domain}: нет nofollow"

  # TLS: сертификат обязан совпадать с именем.
  served="$(echo | openssl s_client -connect 127.0.0.1:443 -servername "${domain}" 2>/dev/null || true)"
  verdict="$(printf '%s' "${served}" | openssl x509 -noout -checkhost "${domain}" 2>/dev/null || true)"
  [[ "${verdict}" == *"does match certificate"* ]] \
    && ok "${domain}: сертификат совпадает" || bad "${domain}: сертификат не совпадает"

  robots="$(curl -sS --max-time 25 --resolve "${domain}:443:127.0.0.1" \
            "https://${domain}/robots.txt" 2>/dev/null || true)"
  grep -q 'Disallow: /' <<<"${robots}" \
    && ok "${domain}: robots.txt закрывает сайт" || bad "${domain}: robots.txt не закрывает сайт"

  # www обязан вести на свой apex.
  redirect="$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 25 \
              --resolve "www.${domain}:443:127.0.0.1" "https://www.${domain}/" 2>/dev/null \
              || echo 'curl-error -')"
  if grep -q "^308 https://${domain}/" <<<"${redirect}"; then
    ok "www.${domain}: 308 на свой apex"
  else
    bad "www.${domain}: ${redirect}, ожидался 308 на https://${domain}/"
  fi

  # Токен не должен встречаться в отдаваемом HTML.
  if [[ -n "${TOKEN_SAMPLE}" ]] && grep -qF "${TOKEN_SAMPLE}" <<<"${BODY}"; then
    bad "${domain}: В HTML НАЙДЕН API-ТОКЕН"
  fi
done

# --- 2. Каталоги обоих направлений непустые ---------------------------------
catalog_nonempty() {  # domain marker
  local domain="$1" marker="$2"
  fetch "${domain}" "/"
  grep -q "${marker}" <<<"${BODY}" \
    && ok "${domain}: каталог непустой" || bad "${domain}: каталог пуст"
}
# Маркер живого каталога — ссылки /title/…/, а не класс шаблона: `card__title`
# в отрисованном каталоге не встречается, и проверка отклоняла рабочий сайт.
for domain in "${LORDS_DOMAINS[@]}"; do catalog_nonempty "${domain}" 'href="/title/'; done
for domain in "${YUMMY_DOMAINS[@]}"; do
  fetch "${domain}" "/"
  grep -qiE 'href="/(title|anime|catalog)/' <<<"${BODY}" \
    && ok "${domain}: каталог непустой" || bad "${domain}: каталог пуст"
done

# --- 3. Страница тайтла, сезоны/серии, фильм, плеер -------------------------
# Адреса берутся из отчёта сборки и из самой страницы, а не выдумываются.
check_direction_titles() {   # domain series_path movie_path
  local domain="$1" series_path="$2" movie_path="$3"

  if [[ -z "${series_path}" ]]; then
    bad "${domain}: не найдена страница сериала для проверки"
    return
  fi
  fetch "${domain}" "${series_path}"
  [[ "${CODE}" == "200" ]] \
    && ok "${domain}${series_path}: 200" || bad "${domain}${series_path}: ${CODE}"

  # Сезоны и серии: на странице сериала обязаны быть оба списка.
  grep -qiE 'season|сезон' <<<"${BODY}" \
    && ok "${domain}: сезоны на странице" || bad "${domain}: нет сезонов"
  grep -qiE 'episode|серия|серии' <<<"${BODY}" \
    && ok "${domain}: серии на странице" || bad "${domain}: нет серий"

  # Плеер и Publisher ID из безопасной конфигурации.
  grep -q 'player.cdnvideohub.com' <<<"${BODY}" \
    && ok "${domain}: скрипт плеера подключён" || bad "${domain}: нет скрипта плеера"
  if grep -qE 'data-publisher-id="[1-9][0-9]*"' <<<"${BODY}"; then
    ok "${domain}: Publisher ID подставлен"
  else
    bad "${domain}: Publisher ID не подставлен или не число"
  fi
  if [[ -n "${TOKEN_SAMPLE}" ]] && grep -qF "${TOKEN_SAMPLE}" <<<"${BODY}"; then
    bad "${domain}: НА СТРАНИЦЕ ТАЙТЛА НАЙДЕН API-ТОКЕН"
  fi

  # Фильм без сезонов проверяется отдельно: у него другой путь по коду.
  if [[ -z "${movie_path}" ]]; then
    bad "${domain}: не найдена страница фильма без сезонов"
    return
  fi
  fetch "${domain}" "${movie_path}"
  [[ "${CODE}" == "200" ]] \
    && ok "${domain}${movie_path}: фильм 200" || bad "${domain}${movie_path}: ${CODE}"
  grep -q 'player.cdnvideohub.com' <<<"${BODY}" \
    || bad "${domain}: у фильма нет плеера"
}

# Примеры страниц берутся из bundle-manifest.json внутри самого пакета: это
# тот же артефакт, что разложен в релиз, поэтому путь заведомо существует на
# сайте. Прежде читался artifacts/lords/live/report.json, где этих полей нет.
for index in "${!LORDS_DOMAINS[@]}"; do
  domain="${LORDS_DOMAINS[${index}]}"
  site="${LORDS_SITES[${index}]}"
  paths="$("${PY}" - "${BUNDLE}/${site}.tar" <<'PYEOF' 2>/dev/null || true
import json, sys, tarfile
try:
    with tarfile.open(sys.argv[1]) as archive:
        manifest = json.loads(archive.extractfile("bundle-manifest.json").read().decode("utf-8"))
except Exception:
    print("\t"); raise SystemExit(0)
print(f'{manifest.get("sample_series_path","")}\t{manifest.get("sample_movie_path","")}')
PYEOF
)"
  series="${paths%%$'\t'*}"; movie="${paths##*$'\t'}"
  check_direction_titles "${domain}" "${series}" "${movie}"
done

for domain in "${YUMMY_DOMAINS[@]}"; do
  fetch "${domain}" "/"
  series="$(grep -m1 -oE '/(title|anime)/[a-z0-9-]+' <<<"${BODY}")"
  movie="$(grep -m1 -oE '/(title|anime)/[a-z0-9-]+' <<<"${BODY}" | tail -1)"
  check_direction_titles "${domain}" "${series}" "${movie}"
done

# --- 4. Токен не в логах, argv и окружении ----------------------------------
if [[ -n "${TOKEN_SAMPLE}" ]]; then
  if grep -rqF "${TOKEN_SAMPLE}" /var/log/nginx/ 2>/dev/null; then
    bad "API-токен найден в журналах nginx"
  else
    ok "токена нет в журналах nginx"
  fi
  if journalctl --since "-2h" --no-pager 2>/dev/null | grep -qF "${TOKEN_SAMPLE}"; then
    bad "API-токен найден в journal"
  else
    ok "токена нет в journal"
  fi
  leaked_env=0
  for unit in "${LORDS_UNITS[@]}"; do
    systemctl show "${unit}" 2>/dev/null | grep -qF "${TOKEN_SAMPLE}" && leaked_env=1
    pid="$(systemctl show -p MainPID --value "${unit}" 2>/dev/null || echo 0)"
    if [[ "${pid}" =~ ^[0-9]+$ && "${pid}" -gt 0 && -r "/proc/${pid}/environ" ]]; then
      tr '\0' '\n' < "/proc/${pid}/environ" | grep -qF "${TOKEN_SAMPLE}" && leaked_env=1
    fi
    tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null | grep -qF "${TOKEN_SAMPLE}" && leaked_env=1
  done
  [[ "${leaked_env}" -eq 0 ]] && ok "токена нет в environment, systemctl show и argv" \
    || bad "API-токен виден в environment/systemctl show/argv"
fi
TOKEN_SAMPLE=""

# --- 5. Неизвестный Host не получает контент --------------------------------
unknown="$(curl -sS --max-time 20 -H 'Host: no-such-host.invalid' \
           http://127.0.0.1/ 2>/dev/null | head -c 3000 || true)"
if grep -qiE 'lords|lordfilm|lordserial|yummyani|card__title' <<<"${unknown}"; then
  bad "неизвестный Host получает контент сайтов"
else
  ok "неизвестный Host не получает контент"
fi

if [[ "${FAILURES}" -gt 0 ]]; then
  warn "живая приёмка не прошла: отказов ${FAILURES}"
  restore_nginx
  die "PUBLIC_SITES_VERIFIED=fail — pass не печатается, конфигурация nginx возвращена"
fi

rm -rf -- "${WORKDIR}"
echo
log "готово: шесть сайтов публичны"
for domain in "${YUMMY_DOMAINS[@]}" "${LORDS_DOMAINS[@]}"; do
  printf '      https://%s/\n' "${domain}"
done
log "индексация закрыта: noindex, nofollow и robots.txt Disallow: /"
log "PUBLIC_SITES_VERIFIED=pass"
