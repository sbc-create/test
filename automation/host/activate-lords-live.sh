#!/usr/bin/env bash
# Переключение трёх сайтов Lords с fixture-каталога на живой CDNVideoHub.
#
# Запуск:
#   sudo bash /srv/site-factory/repo/var/activate-lords-live.sh
#
# Запускается через тонкий пускатель в var/, который подставляет ожидаемый SHA.
#
# Спрашивает ровно три вещи: API-токен (скрыто), числовой Publisher ID и
# подтверждение прав. Больше вводить нечего.
#
# Что сценарий НЕ делает:
#   * не трогает YummyAnime — ни конфигурацию, ни контейнеры, ни базы;
#   * не выпускает и не перевыпускает сертификаты;
#   * не меняет Basic Auth, DNS и nginx соседа;
#   * не включает индексацию: noindex и robots Disallow остаются;
#   * не выполняет seed, db reset и db push --accept-data-loss;
#   * не печатает введённые значения нигде.
#
# При любой ошибке возвращает предыдущий fixture-релиз и прежние секреты.
# Повторный запуск с теми же данными не создаёт дублей.

set -Eeuo pipefail

readonly REPO=/srv/site-factory/repo/var/lords-deploy
readonly EXPECT_SHA="${LORDS_EXPECT_SHA:-}"
readonly SECRET_DIR=/etc/site-factory/secrets/cdnvideohub/lords
readonly TOKEN_FILE="${SECRET_DIR}/api-token"
readonly PUBLISHER_FILE="${SECRET_DIR}/publisher-id"
readonly RUNTIME_ROOT=/srv/lords
readonly BACKUP_ROOT=/var/backups/lords-live
readonly UNITS=(lords-01.service lords-02.service lords-03.service)
readonly SITES=(lords-01 lords-02 lords-03)
readonly DOMAINS=(lordfilm47.space lordserial33.biz 1lordserials1.online)
readonly PORTS=(9101 9102 9103)

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

STAGE="запуск"
stage() { STAGE="$1"; }

ROLLBACK_READY=0
ROLLBACK_MARKER=""
BACKUP_DIR=""

# Секреты живут только в переменных этого процесса и гасятся в конце.
API_TOKEN=""
PUBLISHER_ID=""
scrub() { API_TOKEN=""; PUBLISHER_ID=""; }

rollback() {
  [[ "${ROLLBACK_READY}" -eq 1 ]] || return 0
  # Признак в файле, а не в переменной: отказ внутри подстановки команды
  # поднимает ERR и в подоболочке, и в родителе, а присваивание из подоболочки
  # родителю не видно. Создание под noclobber атомарно.
  if [[ -n "${ROLLBACK_MARKER}" ]]; then
    if ! (set -o noclobber; : > "${ROLLBACK_MARKER}") 2>/dev/null; then
      return 0
    fi
  fi
  ROLLBACK_READY=0

  warn "откат: возвращаю предыдущий fixture-релиз и прежние секреты"

  for index in "${!SITES[@]}"; do
    local_site="${SITES[${index}]}"
    previous_file="${BACKUP_DIR}/${local_site}.previous-release"
    if [[ -s "${previous_file}" ]]; then
      previous="$(cat "${previous_file}")"
      target="${RUNTIME_ROOT}/${local_site}/releases/${previous}"
      if [[ -d "${target}" ]]; then
        ln -sfn "${target}" "${RUNTIME_ROOT}/${local_site}/.current.new"
        mv -Tf "${RUNTIME_ROOT}/${local_site}/.current.new" \
               "${RUNTIME_ROOT}/${local_site}/current"
        chown -h lords:lords "${RUNTIME_ROOT}/${local_site}/current" 2>/dev/null || true
        warn "  ${local_site}: возвращён релиз ${previous}"
      else
        warn "  ${local_site}: каталог прежнего релиза ${previous} не найден"
      fi
    fi
    # Юнит возвращается к fixture-виду: без LoadCredential он поднимется и
    # без секретов, а с ним — не поднялся бы вовсе.
    if [[ -f "${BACKUP_DIR}/systemd/${UNITS[${index}]}" ]]; then
      install -m 0644 "${BACKUP_DIR}/systemd/${UNITS[${index}]}" \
        "/etc/systemd/system/${UNITS[${index}]}"
    fi
  done

  systemctl daemon-reload >/dev/null 2>&1 || true
  for unit in "${UNITS[@]}"; do
    systemctl restart "${unit}" >/dev/null 2>&1 || warn "не удалось перезапустить ${unit}"
  done

  # Секреты: если их не было до запуска, они и не должны остаться.
  #
  # Исключение — веб-приём: там владелец ввёл значения в браузере, они уже
  # проверены обращением к источнику и сохранены верно. Отказ переключения
  # каталога не делает их неверными, а стирать их значило бы заставить вводить
  # всё заново из-за постороннего сбоя.
  if [[ "${LORDS_KEEP_SECRETS_ON_ROLLBACK:-0}" == "1" ]]; then
    warn "  секреты сохранены: они введены и проверены отдельно от переключения"
  elif [[ -f "${BACKUP_DIR}/secrets-existed" ]]; then
    for name in api-token publisher-id; do
      [[ -f "${BACKUP_DIR}/secrets/${name}" ]] \
        && install -m 0600 -o root -g root "${BACKUP_DIR}/secrets/${name}" "${SECRET_DIR}/${name}"
    done
    warn "  секреты возвращены к прежним значениям"
  else
    rm -f "${TOKEN_FILE}" "${PUBLISHER_FILE}"
    warn "  секреты удалены: до запуска их не было"
  fi

  scrub
  warn "откат выполнен; снимок: ${BACKUP_DIR}"
}

on_error() {
  local status="$1" line="$2" command="$3"
  trap - ERR
  set +e
  case "${command}" in
    *TOKEN*|*token*|*PUBLISHER*|*publisher*|*read\ *)
      command='<команда работы с учётными данными скрыта>' ;;
  esac
  printf '\033[31m[x]\033[0m отказ на этапе: %s\n' "${STAGE}" >&2
  printf '\033[31m[x]\033[0m строка %s, код возврата %s\n' "${line}" "${status}" >&2
  printf '\033[31m[x]\033[0m команда: %s\n' "${command}" >&2
  rollback
  exit 1
}
trap 'on_error "$?" "${LINENO}" "${BASH_COMMAND}"' ERR
trap 'scrub' EXIT

[[ ${EUID} -eq 0 ]] || die "нужен root: sudo bash $0"

# --------------------------------------------------------------------------
# 1. Тот ли commit
# --------------------------------------------------------------------------
stage "сверка commit"
# Ожидаемый SHA передаёт пускатель. Без него сверять не с чем, а выкатывать
# «что окажется в worktree» — значит выкатывать неизвестно что.
[[ -n "${EXPECT_SHA}" ]] \
  || die "не передан LORDS_EXPECT_SHA; запускайте через var/activate-lords-live.sh"
[[ -d "${REPO}" ]] || die "нет deployment worktree: ${REPO}"
HEAD_SHA="$(git -C "${REPO}" rev-parse HEAD 2>/dev/null || true)"
[[ -n "${HEAD_SHA}" ]] || die "не удалось прочитать commit в ${REPO}"
[[ "${HEAD_SHA}" == "${EXPECT_SHA}" ]] \
  || die "ожидался commit ${EXPECT_SHA}, в worktree ${HEAD_SHA}; ничего не изменено"
[[ -z "$(git -C "${REPO}" status --porcelain --untracked-files=no 2>/dev/null)" ]] \
  || die "рабочее дерево worktree грязное"
log "commit: ${HEAD_SHA}"

PY="${REPO}/.venv/bin/python"
[[ -x "${PY}" ]] || PY="$(command -v python3)"
[[ -n "${PY}" ]] || die "python3 не найден"

# --------------------------------------------------------------------------
# 2. Что именно переключается
# --------------------------------------------------------------------------
echo
log "переключаются три сайта:"
for index in "${!DOMAINS[@]}"; do
  printf '      https://%-24s %s  :%s\n' \
    "${DOMAINS[${index}]}" "${SITES[${index}]}" "${PORTS[${index}]}"
done
echo
log "не затрагиваются: YummyAnime, сертификаты, Basic Auth, DNS, индексация"
echo

# --------------------------------------------------------------------------
# 3-5. Ввод
# --------------------------------------------------------------------------
stage "ввод учётных данных"
# Неинтерактивный режим: значения уже лежат в secret-файлах, их записал
# веб-приём. Спрашивать нечего, и терминала здесь может не быть вовсе.
#
# Права подтверждаются в том же месте, где вводились секреты: переспрашивать их
# второй раз в другом канале — не усиление проверки, а её размывание.
if [[ "${LORDS_NONINTERACTIVE:-0}" == "1" ]]; then
  [[ -r "${TOKEN_FILE}" && -r "${PUBLISHER_FILE}" ]] \
    || die "неинтерактивный режим: нет ${TOKEN_FILE} или ${PUBLISHER_FILE}"
  API_TOKEN="$(cat "${TOKEN_FILE}")"
  PUBLISHER_ID="$(cat "${PUBLISHER_FILE}")"
  [[ -n "${API_TOKEN// /}" ]] || die "токен в secret-файле пуст"
  [[ "${PUBLISHER_ID}" =~ ^[1-9][0-9]*$ ]] \
    || die "Publisher ID в secret-файле не является положительным целым"
  [[ "${LORDS_RIGHTS_CONFIRMED:-}" == "yes" ]] \
    || die "права на контент не подтверждены; ничего не изменено"
  log "учётные данные прочитаны из secret-файлов (значения не печатаются)"
else
  read -rsp "CDNVIDEOHUB_API_TOKEN (ввод скрыт): " API_TOKEN
  echo
  [[ -n "${API_TOKEN// /}" ]] || die "токен пуст"

  read -rp "CDNVIDEOHUB_PUBLISHER_ID (число): " PUBLISHER_ID
  [[ "${PUBLISHER_ID}" =~ ^[1-9][0-9]*$ ]] \
    || die "Publisher ID обязан быть положительным целым без ведущего нуля"

  read -rp "Права на контент подтверждены? введите RIGHTS_CONFIRMED=yes: " RIGHTS
  [[ "${RIGHTS}" == "RIGHTS_CONFIRMED=yes" ]] \
    || die "подтверждение прав не получено; ничего не изменено"
  log "ввод принят (значения не печатаются)"
fi

# --------------------------------------------------------------------------
# 7-8. Проверка токена до единой мутации
# --------------------------------------------------------------------------
stage "проверка токена"
PROBE_URL="$("${PY}" - <<'PY'
import yaml, urllib.parse, pathlib
raw = yaml.safe_load(pathlib.Path(
    "/srv/site-factory/repo/var/lords-deploy/knowledge/cdnvideohub/content-api.yaml"
).read_text(encoding="utf-8"))
base = raw["base_url"]
path = raw["endpoints"]["titles"]["path"]
size = raw["pagination"]["size_param"]
print(urllib.parse.urljoin(base, path) + f"?{size}=1")
PY
)"
probe_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 30 \
  -H "Accept: application/json" -H "Authorization: Bearer ${API_TOKEN}" \
  "${PROBE_URL}" 2>/dev/null)" || probe_code="curl-error"
case "${probe_code}" in
  200) log "источник принял токен" ;;
  401|403) die "источник отклонил токен (${probe_code}); ничего не изменено" ;;
  *) die "проверка токена не удалась (${probe_code}); ничего не изменено" ;;
esac

# --------------------------------------------------------------------------
# 10. Снимок. Дальше начинаются изменения.
# --------------------------------------------------------------------------
stage "снимок текущего стенда"
BACKUP_DIR="${BACKUP_ROOT}/$(date +%Y%m%d-%H%M%S)-${HEAD_SHA:0:12}"
install -d -m 0700 "${BACKUP_ROOT}" "${BACKUP_DIR}" "${BACKUP_DIR}/systemd" \
  "${BACKUP_DIR}/secrets"
for index in "${!SITES[@]}"; do
  site="${SITES[${index}]}"
  current="${RUNTIME_ROOT}/${site}/current"
  [[ -L "${current}" ]] && basename "$(readlink -f "${current}")" \
    > "${BACKUP_DIR}/${site}.previous-release"
  [[ -f "/etc/systemd/system/${UNITS[${index}]}" ]] \
    && cp -a "/etc/systemd/system/${UNITS[${index}]}" "${BACKUP_DIR}/systemd/"
done
if [[ -f "${TOKEN_FILE}" || -f "${PUBLISHER_FILE}" ]]; then
  : > "${BACKUP_DIR}/secrets-existed"
  [[ -f "${TOKEN_FILE}" ]] && cp -a "${TOKEN_FILE}" "${BACKUP_DIR}/secrets/api-token"
  [[ -f "${PUBLISHER_FILE}" ]] && cp -a "${PUBLISHER_FILE}" "${BACKUP_DIR}/secrets/publisher-id"
fi
chmod -R go-rwx "${BACKUP_DIR}"
ROLLBACK_MARKER="${BACKUP_DIR}/.rollback-done"
ROLLBACK_READY=1
log "снимок: ${BACKUP_DIR}"

# --------------------------------------------------------------------------
# 9. Секреты — атомарно
# --------------------------------------------------------------------------
stage "запись секретов"
install -d -m 0700 -o root -g root /etc/site-factory /etc/site-factory/secrets \
  /etc/site-factory/secrets/cdnvideohub "${SECRET_DIR}"
umask 077
printf '%s' "${API_TOKEN}"    > "${TOKEN_FILE}.tmp"
printf '%s' "${PUBLISHER_ID}" > "${PUBLISHER_FILE}.tmp"
chmod 0600 "${TOKEN_FILE}.tmp" "${PUBLISHER_FILE}.tmp"
chown root:root "${TOKEN_FILE}.tmp" "${PUBLISHER_FILE}.tmp"
mv -f "${TOKEN_FILE}.tmp" "${TOKEN_FILE}"
mv -f "${PUBLISHER_FILE}.tmp" "${PUBLISHER_FILE}"
log "секреты записаны: ${SECRET_DIR} (root:root, 0600, значения не печатаются)"

# --------------------------------------------------------------------------
# 11-12. Живой каталог
# --------------------------------------------------------------------------
stage "сборка живого каталога"
# Токен уходит в окружение дочернего процесса, а не в argv: argv виден в `ps`
# любому пользователю, окружение дочернего процесса — только root.
if ! (
      cd "${REPO}" \
      && CDNVIDEOHUB_API_TOKEN="${API_TOKEN}" \
         CDNVIDEOHUB_PUBLISHER_ID="${PUBLISHER_ID}" \
         "${PY}" -m factory lords-live
     ); then
  die "сборка живого каталога не прошла — переключение отменено"
fi

CATALOG_REPORT="${REPO}/artifacts/lords/live/report.json"
[[ -s "${CATALOG_REPORT}" ]] || die "нет отчёта сборки ${CATALOG_REPORT}"
"${PY}" - "${CATALOG_REPORT}" <<'PY' || die "живой каталог непригоден — переключение отменено"
import json, sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
bad = []
for site_id, site in report.get("sites", {}).items():
    if site.get("status") not in ("FRESH",):
        bad.append(f"{site_id}: статус {site.get('status')}")
    if site.get("item_count", 0) < 1:
        bad.append(f"{site_id}: пустой каталог")
    if not site.get("sections_enabled"):
        bad.append(f"{site_id}: ни одного раздела с материалами")
if bad:
    print("; ".join(bad), file=sys.stderr)
    raise SystemExit(1)
print(f"каталог принят: {len(report.get('sites', {}))} сайта(ов)")
PY

# --------------------------------------------------------------------------
# 13-14. Миграции — только deploy, без seed и reset
# --------------------------------------------------------------------------
stage "миграции"
# seed, db reset и db push --accept-data-loss не вызываются нигде в этом файле.
if [[ -d "${REPO}/prisma/migrations" ]] || [[ -d "${REPO}/migrations" ]]; then
  log "найдены миграции — применяю только deploy"
  if ! ( cd "${REPO}" && "${PY}" -m factory db migrate-deploy ); then
    die "migrate deploy не прошёл или подкоманда отсутствует; переключение отменено"
  fi
else
  # На этом коммите миграций в репозитории нет, поэтому шага и не будет.
  # Ветка оставлена намеренно: она сработает, когда миграции появятся, и не
  # даст выкатить каталог мимо схемы.
  log "миграций нет — шаг пропущен"
fi

# --------------------------------------------------------------------------
# 15-16. Установка релизов и перезапуск
# --------------------------------------------------------------------------
stage "установка живых релизов"
BUNDLE_DIR="${REPO}/artifacts/lords/bundle"
for index in "${!SITES[@]}"; do
  site="${SITES[${index}]}"
  unit="${UNITS[${index}]}"
  archive="${BUNDLE_DIR}/${site}.tar"
  [[ -f "${archive}" ]] || die "нет пакета ${archive}"
  release="$(sha256sum "${archive}" | cut -c1-12)"
  runtime="${RUNTIME_ROOT}/${site}"
  target="${runtime}/releases/${release}"

  if [[ -d "${target}" ]]; then
    log "  ${site}: релиз ${release} уже разложен"
  else
    install -d -m 0755 "${target}.tmp"
    tar -xf "${archive}" -C "${target}.tmp"
    chown -R lords:lords "${target}.tmp"
    mv "${target}.tmp" "${target}"
    log "  ${site}: разложен релиз ${release}"
  fi

  ln -sfn "${target}" "${runtime}/.current.new"
  mv -Tf "${runtime}/.current.new" "${runtime}/current"
  chown -h lords:lords "${runtime}/current"

  install -m 0644 "${REPO}/artifacts/lords/staging/systemd/${unit}" \
    "/etc/systemd/system/${unit}"
done

systemctl daemon-reload
stage "перезапуск трёх юнитов Lords"
for unit in "${UNITS[@]}"; do
  systemctl restart "${unit}" || die "${unit} не перезапустился"
done

# --------------------------------------------------------------------------
# 17. Готовность
# --------------------------------------------------------------------------
stage "проверка готовности"
for index in "${!SITES[@]}"; do
  port="${PORTS[${index}]}"
  ready=0
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 3 "http://127.0.0.1:${port}/readyz" >/dev/null 2>&1; then
      ready=1; break
    fi
    sleep 1
  done
  [[ "${ready}" -eq 1 ]] || die "${SITES[${index}]}: /readyz не ответил"
  log "  ${SITES[${index}]} готов"
done

# --------------------------------------------------------------------------
# 18-21. Приёмка
# --------------------------------------------------------------------------
stage "публичная приёмка"
AUTH_PASSWORD=""
[[ -r /root/lords-staging-credentials ]] \
  && AUTH_PASSWORD="$(sed -n 's/^пароль: //p' /root/lords-staging-credentials | head -1)"
[[ -n "${AUTH_PASSWORD}" ]] || die "не прочитан пароль Basic Auth"

failures=0
for index in "${!DOMAINS[@]}"; do
  apex="${DOMAINS[${index}]}"
  port="${PORTS[${index}]}"
  site="${SITES[${index}]}"
  pin=(--resolve "${apex}:443:127.0.0.1")

  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "${pin[@]}" \
    "https://${apex}/" 2>/dev/null)" || code="curl-error"
  [[ "${code}" == "401" ]] || { warn "  ${apex}: без пароля ${code}, ожидался 401"; failures=$((failures+1)); }

  body="$(curl -sS --max-time 15 "${pin[@]}" -u "lords:${AUTH_PASSWORD}" \
    "https://${apex}/" 2>/dev/null)" || body=""
  grep -q "card__title" <<<"${body}" \
    || { warn "  ${apex}: на главной нет карточек каталога"; failures=$((failures+1)); }

  headers="$(curl -sS -D - -o /dev/null --max-time 15 "${pin[@]}" \
    -u "lords:${AUTH_PASSWORD}" "https://${apex}/" 2>/dev/null)" || headers=""
  grep -qi '^x-robots-tag:.*noindex' <<<"${headers}" \
    || { warn "  ${apex}: нет X-Robots-Tag noindex"; failures=$((failures+1)); }

  robots="$(curl -sS --max-time 15 "${pin[@]}" -u "lords:${AUTH_PASSWORD}" \
    "https://${apex}/robots.txt" 2>/dev/null)" || robots=""
  grep -q 'Disallow: /' <<<"${robots}" \
    || { warn "  ${apex}: robots.txt не закрывает сайт"; failures=$((failures+1)); }

  www_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
    --resolve "www.${apex}:443:127.0.0.1" "https://www.${apex}/" 2>/dev/null)" || www_code="curl-error"
  [[ "${www_code}" == "308" ]] \
    || { warn "  www.${apex}: ${www_code}, ожидался 308"; failures=$((failures+1)); }

  # Плеер: скрипт провайдера и параметры именно этого сайта.
  title_path="$("${PY}" - "${REPO}/artifacts/lords/live/report.json" "${site}" <<'PY'
import json, sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
print(report["sites"][sys.argv[2]].get("sample_title_path", ""))
PY
)"
  if [[ -n "${title_path}" ]]; then
    title_html="$(curl -sS --max-time 15 "${pin[@]}" -u "lords:${AUTH_PASSWORD}" \
      "https://${apex}${title_path}" 2>/dev/null)" || title_html=""
    grep -q "player.cdnvideohub.com" <<<"${title_html}" \
      || { warn "  ${apex}: на странице тайтла нет скрипта плеера"; failures=$((failures+1)); }
    grep -q "<video-player" <<<"${title_html}" \
      || { warn "  ${apex}: нет элемента video-player"; failures=$((failures+1)); }
    grep -q "data-publisher-id=\"${PUBLISHER_ID}\"" <<<"${title_html}" \
      || { warn "  ${apex}: publisher-id не подставлен"; failures=$((failures+1)); }
    grep -qi "iframe" <<<"${title_html}" \
      && { warn "  ${apex}: плеер обёрнут в iframe (PC-4)"; failures=$((failures+1)); }
    # Токен не должен попасть в разметку ни при каких условиях.
    if grep -qF "${API_TOKEN}" <<<"${title_html}"; then
      warn "  ${apex}: В РАЗМЕТКЕ НАЙДЕН ТОКЕН"
      failures=$((failures+1))
    fi
  else
    warn "  ${site}: в отчёте нет страницы тайтла для проверки плеера"
    failures=$((failures+1))
  fi

  # Секреты не должны быть в отдаваемых файлах.
  js="$(curl -sS --max-time 15 "${pin[@]}" -u "lords:${AUTH_PASSWORD}" \
    "https://${apex}/assets/app.js" 2>/dev/null)" || js=""
  if grep -qF "${API_TOKEN}" <<<"${js}"; then
    warn "  ${apex}: токен найден в app.js"
    failures=$((failures+1))
  fi

  [[ "${failures}" -eq 0 ]] && log "  ${apex}: приёмка пройдена"
done

# Сосед не затронут.
stage "проверка соседа"
yummy="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 \
  -H 'Host: yummyani.biz' http://127.0.0.1/ 2>/dev/null)" || yummy="curl-error"
[[ "${yummy}" =~ ^(200|301|308)$ ]] \
  || { warn "  YummyAnime отвечает ${yummy}"; failures=$((failures+1)); }

if [[ "${failures}" -gt 0 ]]; then
  warn "приёмка не прошла: отказов ${failures}"
  rollback
  die "стенд возвращён на предыдущий fixture-релиз; живой каталог не опубликован"
fi

ROLLBACK_READY=0
scrub

echo
log "готово: три сайта работают на живом каталоге CDNVideoHub"
for index in "${!DOMAINS[@]}"; do
  printf '      https://%-24s %s\n' "${DOMAINS[${index}]}" "${SITES[${index}]}"
done
echo
log "снимок для отката: ${BACKUP_DIR}"
log "индексация по-прежнему выключена, Basic Auth и сертификаты не менялись"
log "YummyAnime не затронут"
