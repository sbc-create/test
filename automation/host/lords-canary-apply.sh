#!/usr/bin/env bash
# Canary одной витрины Lords: две фазы с разными правами.
#
# ## Почему две фазы, а не одна
#
# Первая редакция делала всё от root: и рендер, и переключение. Рендер — это
# разбор тридцати пяти мегабайт данных поставщика и отрисовка пятидесяти трёх
# тысяч страниц; выполнять его с полными правами незачем и опасно. Root нужен
# ровно для трёх системных действий: смены владельца каталога релиза, подмены
# ссылки и остановки таймера обновления.
#
#   render  — ограниченная учётная запись, учётные данные, никакого доступа на
#             запись в /srv/lords. Долгая фаза.
#   switch  — root, БЕЗ учётных данных вовсе. Короткая фаза.
#
# Секрет и полные права никогда не встречаются в одном процессе.
#
# ## Почему ограниченная запись — claude, а не lords
#
# `lords` не может войти в /home/claude: каталог `drwxr-x---`, и код операции
# ему недоступен. Расширять права на домашний каталог ради этого нельзя — это
# открыло бы куда больше, чем нужно. `claude` при этом не root и не имеет
# записи в /srv/lords: рендер физически не может тронуть боевой рантайм.
#
# ## Когда останавливается таймер обновления
#
# В фазе switch, а не перед рендером. Рендер идёт часами, и остановка таймера
# на всё это время заморозила бы свежесть каталога у всех трёх витрин. Теперь
# пауза длится столько, сколько идёт переключение и наблюдение.
set -Eeuo pipefail

PHASE="${1:-}"
SITE="${2:-}"
readonly ALLOWED_SITES=(lords-02)
# Отпечаток артефакта закреплён константой намеренно: он не следует за кодом
# автоматически, иначе сценарий выкатывал бы всё, что оказалось в дереве, и
# перестал бы быть воротами. Смена значения — решение, а не правка.
#
# Версия 2. Отличие от версии 1 (52b56d557564717adcf32011c3494bc8c548eae1a96e010f7bd499351e0847dc,
# принята по TEMPLATE_TO_CORE-008) — одна: метка происхождения данных в
# factory/lords/render.py перестала быть зашитой строкой `fixture/test`.
# Версия 1 объявляла живой каталог CDNVideoHub синтетическим на всех трёх
# боевых витринах, и по этой метке CORE_TO_OWNER-011 вывел несуществующий
# блокер выкладки.
readonly EXPECT_DIGEST="7b38ca10685a75c3d52527746208539cc30015fc1bfb3fce010a9491616ed965"
readonly REFRESH_TIMER="lords-content-refresh.timer"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
PYTHON="${FACTORY_PYTHON:-${REPO}/.venv/bin/python}"
AUDIT_DIR="${LORDS_CANARY_AUDIT:-/var/log/site-factory}"
STAGING_ROOT="${LORDS_CANARY_STAGING:-${REPO}/var/canary-staging}"
STAGING="${STAGING_ROOT}/${SITE}"

STEP_LOG="${AUDIT_DIR}/lords-canary-${SITE:-unknown}.steps.log"
mkdir -p "$(dirname "${STEP_LOG}")" 2>/dev/null || true
step() { printf '%s [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${PHASE:-?}" "$*" \
         >> "${STEP_LOG}" 2>/dev/null || true; }
log()  { step "$*"; printf '[canary:%s] %s\n' "${PHASE:-?}" "$*"; }
die()  { step "ОТКАЗ: $*"; printf '[canary:%s] ОТКАЗ: %s\n' "${PHASE:-?}" "$*" >&2; exit 1; }

step "=== фаза «${PHASE:-не указана}» для «${SITE:-не указана}», uid $(id -u) ==="

case "${PHASE}" in
  render|switch) ;;
  *) die "фаза должна быть render или switch, получено «${PHASE:-пусто}»" ;;
esac

allowed=0
for candidate in "${ALLOWED_SITES[@]}"; do
  [ "${SITE}" = "${candidate}" ] && allowed=1
done
[ "${allowed}" = "1" ] || die "витрина «${SITE:-не указана}» не в списке разрешённых: ${ALLOWED_SITES[*]}"

# Происхождение и отпечаток сверяются в обеих фазах: между ними проходит время,
# и подмена оснастки между рендером и переключением — реальный путь атаки.
HEAD_SHA="$("${PYTHON}" "${SCRIPT_DIR}/lords-canary-provenance.py" --verify)" \
  || die "манифест происхождения не сошёлся: исполняемая оснастка не та, что проверялась"
DIGEST="$("${PYTHON}" -c 'from factory.templates import digest; print(digest.compute()["template_digest"])')"
[ "${DIGEST}" = "${EXPECT_DIGEST}" ] \
  || die "отпечаток шаблона ${DIGEST:0:16} не совпал с закреплённым ${EXPECT_DIGEST:0:16}"
log "происхождение подтверждено: commit ${HEAD_SHA:0:12}, отпечаток ${DIGEST:0:16}"

RUNTIME="/srv/lords/${SITE}"
SNAPSHOT_DIR="${LORDS_SNAPSHOT_DIR:-${REPO}/var/lords/lords/catalog-cache}"
SNAPSHOT="${SNAPSHOT_DIR}/${SITE}.json"

# --------------------------------------------------------------------- render
if [ "${PHASE}" = "render" ]; then
  [ "$(id -u)" != "0" ] || die "рендер не должен идти от root: это долгая фаза с данными поставщика"
  [ -f "${SNAPSHOT}" ] || die "нет снимка каталога ${SNAPSHOT}"
  read -r SNAPSHOT_ITEMS SNAPSHOT_DIGEST < <(
    "${PYTHON}" "${SCRIPT_DIR}/lords-canary-snapshot.py" "${SNAPSHOT}") \
    || die "снимок каталога не прочитан: ${SNAPSHOT}"
  log "снимок каталога: ${SNAPSHOT_DIGEST}, записей ${SNAPSHOT_ITEMS}"
  [ "${SNAPSHOT_ITEMS}" -gt 1000 ] \
    || die "в снимке ${SNAPSHOT_ITEMS} записей — это не живой каталог"

  rm -rf "${STAGING}"
  mkdir -p "${STAGING}"
  log "собираю витрину на живом каталоге (полный рендер, это долго)"
  BUILD_STARTED="$(date -u +%s)"
  LORDS_SNAPSHOT_DIR="${SNAPSHOT_DIR}" \
    "${PYTHON}" "${SCRIPT_DIR}/lords-canary-build.py" "${SITE}" "${STAGING}" \
    || die "сборка на живом каталоге не выполнена; боевая витрина не тронута"
  PAGES="$(find "${STAGING}" -name index.html | wc -l)"
  log "сборка завершена за $(( ($(date -u +%s) - BUILD_STARTED) / 60 )) мин, страниц: ${PAGES}"

  # Расписка о сборке: фаза switch обязана знать, что и на чём собрано, и не
  # обязана доверять тому, что найдёт в каталоге.
  cat > "${STAGING_ROOT}/${SITE}.render.json" <<JSON
{
  "site_id": "${SITE}",
  "rendered_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "rendered_by_uid": $(id -u),
  "template_sha": "${HEAD_SHA}",
  "template_digest": "${DIGEST}",
  "content_snapshot_digest": "${SNAPSHOT_DIGEST}",
  "content_snapshot_items": ${SNAPSHOT_ITEMS},
  "pages": ${PAGES},
  "staging": "${STAGING}"
}
JSON
  log "готово к переключению: ${STAGING}"
  exit 0
fi

# --------------------------------------------------------------------- switch
[ "$(id -u)" = "0" ] || die "переключение требует прав root"
[ -z "${CREDENTIALS_DIRECTORY:-}" ] \
  || die "фазе переключения учётные данные не передаются: секрет и полные права не должны встречаться"

RENDER_RECEIPT="${STAGING_ROOT}/${SITE}.render.json"
[ -f "${RENDER_RECEIPT}" ] || die "нет расписки о сборке ${RENDER_RECEIPT}: сначала фаза render"
[ -d "${STAGING}" ] || die "нет собранной витрины ${STAGING}"

RECEIPT_DIGEST="$("${PYTHON}" -c '
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["template_digest"])' "${RENDER_RECEIPT}")"
[ "${RECEIPT_DIGEST}" = "${DIGEST}" ] \
  || die "расписка о сборке собрана на другом отпечатке ${RECEIPT_DIGEST:0:16}"
SNAPSHOT_DIGEST="$("${PYTHON}" -c '
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["content_snapshot_digest"])' "${RENDER_RECEIPT}")"
SNAPSHOT_ITEMS="$("${PYTHON}" -c '
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["content_snapshot_items"])' "${RENDER_RECEIPT}")"
log "расписка о сборке принята: снимок ${SNAPSHOT_DIGEST}, записей ${SNAPSHOT_ITEMS}"

CURRENT="$(readlink -f "${RUNTIME}/current" 2>/dev/null || true)"
[ -n "${CURRENT}" ] || die "у витрины нет текущего релиза: откатываться будет некуда"
log "текущий релиз: $(basename "${CURRENT}")"

log "ворота содержимого до подмены ссылки"
GATES_FILE="$(mktemp)"
if ! "${PYTHON}" "${SCRIPT_DIR}/lords-canary-gates.py" \
     "${STAGING}" "${SNAPSHOT}" "${CURRENT}/site" > "${GATES_FILE}"; then
  rm -f "${GATES_FILE}"
  die "предпереключательные ворота содержимого; ссылка не трогалась"
fi
GATES="$(cat "${GATES_FILE}")"
rm -f "${GATES_FILE}"

TIMER_WAS_ACTIVE=0
if systemctl is-active --quiet "${REFRESH_TIMER}"; then
  TIMER_WAS_ACTIVE=1
  log "останавливаю ${REFRESH_TIMER} на время наблюдения"
  log "  цена: обновление содержимого приостановлено у ВСЕХ ТРЁХ витрин"
  systemctl stop "${REFRESH_TIMER}"
fi

RELEASE="$(find "${STAGING}" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-12)"
TARGET="${RUNTIME}/releases/${RELEASE}"
log "релиз ${RELEASE}"
if [ ! -d "${TARGET}" ]; then
  mkdir -p "${TARGET}"
  cp -a "${STAGING}" "${TARGET}/site"
  "${PYTHON}" "${SCRIPT_DIR}/emit-runtime.py" "${TARGET}/serve.py" \
    || cp -a "${CURRENT}/serve.py" "${TARGET}/serve.py"
  for extra in bundle-manifest.json rollback.json README.md Dockerfile; do
    [ -f "${CURRENT}/${extra}" ] && cp -a "${CURRENT}/${extra}" "${TARGET}/${extra}"
  done
  chown -R lords:lords "${TARGET}"
fi

NEED_RESTART=0
cmp -s "${CURRENT}/serve.py" "${TARGET}/serve.py" || NEED_RESTART=1
SWITCHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ln -sfn "${TARGET}" "${RUNTIME}/current"
[ "${NEED_RESTART}" = "1" ] && systemctl restart "${SITE}.service"
log "ссылка переключена: $(basename "${CURRENT}") → ${RELEASE}"

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
  "rendered_by_uid": $("${PYTHON}" -c '
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["rendered_by_uid"])' "${RENDER_RECEIPT}"),
  "switched_by_uid": $(id -u),
  "gates": ${GATES},
  "refresh_timer_paused": ${TIMER_WAS_ACTIVE},
  "rollback_command": "ln -sfn ${CURRENT} ${RUNTIME}/current",
  "resume_refresh_command": "systemctl start ${REFRESH_TIMER}"
}
JSON
chmod 0644 "${AUDIT}"
log "журнал операции: ${AUDIT}"
log "откат одной командой:  ln -sfn ${CURRENT} ${RUNTIME}/current"
log "вернуть обновление:    systemctl start ${REFRESH_TIMER}"
exit 0
