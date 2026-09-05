#!/usr/bin/env bash
# Canary одной витрины Lords на живом каталоге.
#
# Отличие от `lords-content-refresh.sh` — в объёме, а не в способе. Тот
# обслуживает все три витрины по расписанию; этот выкатывает ОДНУ и ровно один
# раз. Способ публикации общий: сборка в сторону, ворота, раскладка релиза,
# атомарная подмена `current`.
#
# Что здесь ограничено намеренно:
#
#   * список витрин зашит в сценарий, а не читается из окружения — переменную
#     можно передать по ошибке, строку в коде нельзя;
#   * отпечаток шаблона сверяется до единой мутации: выкатывается названный
#     артефакт, а не то, что оказалось в рабочем дереве;
#   * снимок каталога фиксируется один раз и записывается в журнал операции;
#   * ворота содержимого идут ДО подмены ссылки, а не после;
#   * при провале любых ворот ссылка не трогается вовсе;
#   * при провале приёмки после подмены выполняется откат тем же способом.
#
# Чего сценарий НЕ делает: не трогает nginx, TLS, соседние витрины, Yummy,
# провайдер плеера, robots и индексируемость, наблюдателя и обновление
# содержимого сверх названной витрины.
#
# Побочное следствие, о котором нужно знать заранее. Таймер
# `lords-content-refresh.timer` пересобирает все три витрины каждые десять
# минут из боевого checkout. Оставленный работающим, он вернул бы витрину на
# свою сборку в пределах цикла — canary прожил бы минуты. Поэтому таймер
# останавливается на время наблюдения, и это останавливает обновление
# содержимого у всех трёх витрин, а не только у canary. Цена названа в выводе
# и в журнале операции; команда возврата печатается там же.
set -Eeuo pipefail

SITE="${1:-}"
# Список зашит. Расширять его — отдельное осознанное изменение кода, а не
# значение переменной, переданное на бегу.
readonly ALLOWED_SITES=(lords-02)
readonly EXPECT_DIGEST="52b56d557564717adcf32011c3494bc8c548eae1a96e010f7bd499351e0847dc"
readonly REFRESH_TIMER="lords-content-refresh.timer"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
PYTHON="${FACTORY_PYTHON:-${REPO}/.venv/bin/python}"
AUDIT_DIR="${LORDS_CANARY_AUDIT:-/var/log/site-factory}"
STAGING=""
TIMER_WAS_ACTIVE=0

log()  { printf '[canary] %s\n' "$*"; }
die()  { printf '[canary] ОТКАЗ: %s\n' "$*" >&2; exit 1; }

cleanup() {
  [ -n "${STAGING}" ] && [ -d "${STAGING}" ] && rm -rf "${STAGING}"
}
trap cleanup EXIT

# ------------------------------------------------------------------ 0. ворота
allowed=0
for candidate in "${ALLOWED_SITES[@]}"; do
  [ "${SITE}" = "${candidate}" ] && allowed=1
done
[ "${allowed}" = "1" ] || die "витрина «${SITE:-не указана}» не в списке разрешённых: ${ALLOWED_SITES[*]}"

# Происхождение и целостность — без git.
#
# Операция идёт от root, а дерево принадлежит другой учётной записи. Git на это
# отвечает `detected dubious ownership` и отказывается работать: первый же
# запуск падал здесь, до единой проверки. Объявить каталог доверенным можно, но
# это лечило бы симптом — git давал только идентификатор коммита и признак
# «дерево не правили». Оба получаются из манифеста происхождения, который
# сверяется по содержимому файлов и в git не нуждается.
HEAD_SHA="$("${PYTHON}" "${SCRIPT_DIR}/lords-canary-provenance.py" --verify)" \
  || die "манифест происхождения не сошёлся: исполняемая оснастка не та, что проверялась"
log "происхождение подтверждено: commit ${HEAD_SHA:0:12}"

DIGEST="$("${PYTHON}" -c 'from factory.templates import digest; print(digest.compute()["template_digest"])')"
[ "${DIGEST}" = "${EXPECT_DIGEST}" ] \
  || die "отпечаток шаблона ${DIGEST:0:16} не совпал с закреплённым ${EXPECT_DIGEST:0:16}"
log "отпечаток шаблона совпал: ${DIGEST:0:16}"

RUNTIME="/srv/lords/${SITE}"
[ -d "${RUNTIME}/releases" ] || die "нет рантайма ${RUNTIME}"
CURRENT="$(readlink -f "${RUNTIME}/current" 2>/dev/null || true)"
[ -n "${CURRENT}" ] || die "у витрины нет текущего релиза: откатываться будет некуда"
log "текущий релиз: $(basename "${CURRENT}")"

# Снимок каталога живёт в боевом репозитории: его наполняет служба обновления.
# Сценарий же запускается из дерева с закреплённым артефактом, поэтому путь
# задаётся отдельно, а не выводится из расположения сценария. Умолчание —
# собственный var, чтобы запуск из боевого дерева работал без переменной.
SNAPSHOT_DIR="${LORDS_SNAPSHOT_DIR:-${REPO}/var/lords/lords/catalog-cache}"
SNAPSHOT="${SNAPSHOT_DIR}/${SITE}.json"
[ -f "${SNAPSHOT}" ] || die "нет снимка каталога ${SNAPSHOT}"
read -r SNAPSHOT_ITEMS SNAPSHOT_DIGEST < <(
  "${PYTHON}" "${SCRIPT_DIR}/lords-canary-snapshot.py" "${SNAPSHOT}") \
  || die "снимок каталога не прочитан: ${SNAPSHOT}"
log "снимок каталога: ${SNAPSHOT_DIGEST}, записей ${SNAPSHOT_ITEMS}"
[ "${SNAPSHOT_ITEMS}" -gt 1000 ] \
  || die "в снимке ${SNAPSHOT_ITEMS} записей — это не живой каталог, выкладка остановлена"

# ------------------------------------------------- 1. пауза обновления содержимого
if systemctl is-active --quiet "${REFRESH_TIMER}"; then
  TIMER_WAS_ACTIVE=1
  log "останавливаю ${REFRESH_TIMER} на время наблюдения"
  log "  цена: обновление содержимого приостановлено у ВСЕХ ТРЁХ витрин"
  systemctl stop "${REFRESH_TIMER}"
else
  log "${REFRESH_TIMER} уже остановлен"
fi

# ------------------------------------------------------------------ 2. сборка
mkdir -p "${RUNTIME}/.staging"
STAGING="$(mktemp -d -p "${RUNTIME}/.staging")"
log "собираю витрину на живом каталоге"
"${PYTHON}" "${SCRIPT_DIR}/lords-canary-build.py" "${SITE}" "${STAGING}" \
  || die "сборка на живом каталоге не выполнена; витрина осталась на прежнем релизе"

# ------------------------------------------------------- 3. ворота до подмены
log "ворота содержимого до подмены ссылки"
GATES_FILE="$(mktemp)"
if ! "${PYTHON}" "${SCRIPT_DIR}/lords-canary-gates.py" \
     "${STAGING}" "${SNAPSHOT}" "${CURRENT}/site" > "${GATES_FILE}"; then
  log "ворота не пройдены — ссылка не трогалась, витрина осталась на прежнем релизе"
  if [ "${TIMER_WAS_ACTIVE}" = "1" ]; then
    systemctl start "${REFRESH_TIMER}" && log "${REFRESH_TIMER} возвращён"
  fi
  rm -f "${GATES_FILE}"
  die "предпереключательные ворота содержимого"
fi
GATES="$(cat "${GATES_FILE}")"
rm -f "${GATES_FILE}"

# ------------------------------------------------------------- 4. раскладка
RELEASE="$(find "${STAGING}" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-12)"
TARGET="${RUNTIME}/releases/${RELEASE}"
log "релиз ${RELEASE}"
if [ ! -d "${TARGET}" ]; then
  mkdir -p "${TARGET}"
  cp -al "${STAGING}" "${TARGET}/site" 2>/dev/null || cp -a "${STAGING}" "${TARGET}/site"
  "${PYTHON}" "${REPO}/automation/host/emit-runtime.py" "${TARGET}/serve.py" \
    || cp -a "${CURRENT}/serve.py" "${TARGET}/serve.py"
  for extra in bundle-manifest.json rollback.json README.md Dockerfile; do
    [ -f "${CURRENT}/${extra}" ] && cp -a "${CURRENT}/${extra}" "${TARGET}/${extra}"
  done
  chown -R lords:lords "${TARGET}"
fi

# ------------------------------------------------------- 5. атомарная подмена
NEED_RESTART=0
cmp -s "${CURRENT}/serve.py" "${TARGET}/serve.py" || NEED_RESTART=1
SWITCHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ln -sfn "${TARGET}" "${RUNTIME}/current"
[ "${NEED_RESTART}" = "1" ] && systemctl restart "${SITE}.service"
log "ссылка переключена: $(basename "${CURRENT}") → ${RELEASE}"

# ---------------------------------------------------------------- 6. приёмка
PORT="$(grep -m1 -oP 'LORDS_PORT=\K[0-9]+' "/etc/systemd/system/${SITE}.service")"
ok=0
for _ in $(seq 1 10); do
  sleep 2
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "http://127.0.0.1:${PORT}/" || true)"
  [ "${code}" = "200" ] && { ok=1; break; }
done
if [ "${ok}" != "1" ]; then
  log "приёмка не пройдена — откатываю"
  ln -sfn "${CURRENT}" "${RUNTIME}/current"
  [ "${NEED_RESTART}" = "1" ] && systemctl restart "${SITE}.service"
  [ "${TIMER_WAS_ACTIVE}" = "1" ] && systemctl start "${REFRESH_TIMER}"
  die "витрина не ответила после подмены; возвращена на $(basename "${CURRENT}")"
fi

# ----------------------------------------------------------------- 7. журнал
mkdir -p "${AUDIT_DIR}"
AUDIT="${AUDIT_DIR}/lords-canary-${SITE}-${RELEASE}.json"
cat > "${AUDIT}" <<JSON
{
  "operation": "lords-canary",
  "site_id": "${SITE}",
  "switched_at_utc": "${SWITCHED_AT}",
  "template_sha": "${HEAD_SHA}",
  "template_digest": "${DIGEST}",
  "content_snapshot_digest": "${SNAPSHOT_DIGEST}",
  "content_snapshot_items": ${SNAPSHOT_ITEMS},
  "release": "${RELEASE}",
  "previous_release": "$(basename "${CURRENT}")",
  "gates": ${GATES},
  "refresh_timer_paused": ${TIMER_WAS_ACTIVE},
  "rollback_command": "ln -sfn ${CURRENT} ${RUNTIME}/current",
  "resume_refresh_command": "systemctl start ${REFRESH_TIMER}"
}
JSON
chmod 0644 "${AUDIT}"
log "журнал операции: ${AUDIT}"
log ""
log "откат одной командой:  ln -sfn ${CURRENT} ${RUNTIME}/current"
log "вернуть обновление:    systemctl start ${REFRESH_TIMER}"
[ "${TIMER_WAS_ACTIVE}" = "1" ] && log "ВНИМАНИЕ: обновление содержимого остановлено у всех трёх витрин до этой команды"
exit 0
