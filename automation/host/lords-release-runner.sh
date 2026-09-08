#!/bin/bash
# Выкладка одной витрины Lords: предполёт → сборка (или повторное взятие
# готовой) → ворота → переключение → публичная приёмка → откат при провале.
#
# Запускается от root внутри отдельного systemd-юнита. Свой журнал ведёт сам и
# кладёт его в мировидимый файл: журнал root-юнита недоступен учётной записи,
# которая ведёт работу, и прошлое расследование пришлось вести по следам на
# диске. Наблюдаемость — часть контура, а не удобство.
#
# Итог ровно один: DEPLOYED_AND_VERIFIED, ROLLED_BACK или ROLLBACK_FAILED.
set -Eeuo pipefail

SITE="${1:-lords-02}"
case "${SITE}" in
  lords-01) DOMAIN=lordfilm47.space ;;
  lords-02) DOMAIN=lordserial33.biz ;;
  lords-03) DOMAIN=1lordserials1.online ;;
  *) echo "витрина «${SITE}» вне списка разрешённых"; exit 1 ;;
esac

BASE="https://${DOMAIN}"
RT=/srv/lords/${SITE}
REPO=${LORDS_RELEASE_REPO:-/home/claude/wt-release-03}
HEAD_EXPECT=${LORDS_RELEASE_HEAD:-f8f20dde0efb24e58f239c8e662cdbb5f0bf2bcf}
DIGEST_EXPECT=${LORDS_RELEASE_DIGEST:-a0cfaf7135255d62e70432162cadc554c393c2c01dec3936baddafd8ca694859}
PY=${REPO}/.venv/bin/python
HOST=${REPO}/automation/host
STAGING_ROOT=${REPO}/var/canary-staging
STAGING=${STAGING_ROOT}/${SITE}
RECEIPT=${STAGING_ROOT}/${SITE}.render.json
ART_ROOT=/srv/lords/.artifacts
CH=/opt/pw-browsers/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell
STAMP="$(date -u +%Y%m%d-%H%M%S)"
W=/var/log/site-factory/${SITE}-acceptance
LOG=/var/log/site-factory/${SITE}-release-${STAMP}.log
VERDICT=/run/${SITE}-release.verdict
REPORT=/var/log/site-factory/${SITE}-release-report.json
LOCK=/run/lords-release-${SITE}.lock

SWITCHED=0; IN_ROLLBACK=0; PREV=""; NEW=""; SHOT_OK=0
REUSED=нет; PHASE=старт; REASON=""
CHROMIUM_RESULT=не_запускался; FIREFOX_RESULT=не_запускался
IMAGES_OK=0; IMAGES_CHECKED=0; ROUTES_OK=""; SWITCHED_AT=""
REV=""; ARCHIVE_SHA=""

rm -rf "${W}"; mkdir -p "${W}"; chmod 0755 "${W}"
: > "${LOG}"; chmod 0644 "${LOG}"
exec > >(tee -a "${LOG}") 2>&1

say() { printf '%s [%s] %s\n' "$(date -u +%H:%M:%S)" "${PHASE}" "$*"; }
verdict() { [ -s "${VERDICT}" ] || { printf '%s\n' "$1" > "${VERDICT}"; chmod 0644 "${VERDICT}"; }; }

# Отчёт пишется на КАЖДОМ переходе фазы, а не только при выходе. В прошлом
# отказе отчёта не оказалось вовсе, и восстанавливать ход пришлось по временам
# изменения файлов. Частичный отчёт лучше отсутствующего.
report() {
  local итог="${1:-в работе}"
  # Режим errexit восстанавливается ровно тот, что был. Безусловный `set -e` в
  # конце включал бы его и внутри отката, где он снят намеренно: первая же
  # ненулевая команда обрывала бы откат на середине.
  local было="$-"
  set +e
  {
    printf '{\n'
    printf '  "site": "%s",\n' "${SITE}"
    printf '  "domain": "%s",\n' "${DOMAIN}"
    printf '  "url": "%s",\n' "${BASE}"
    printf '  "verdict": "%s",\n' "${итог}"
    printf '  "phase": "%s",\n' "${PHASE}"
    printf '  "reason": "%s",\n' "${REASON}"
    printf '  "head": "%s",\n' "${HEAD_EXPECT}"
    printf '  "template_digest": "%s",\n' "${DIGEST_EXPECT}"
    printf '  "renderer_revision": "%s",\n' "${REV}"
    printf '  "template_artifact_sha256": "%s",\n' "${ARCHIVE_SHA}"
    printf '  "release_before": "%s",\n' "$([ -n "${PREV}" ] && basename "${PREV}" || true)"
    printf '  "release_after": "%s",\n' "$([ -n "${NEW}" ] && basename "${NEW}" || true)"
    printf '  "switched_at_utc": "%s",\n' "${SWITCHED_AT}"
    printf '  "build_reused": "%s",\n' "${REUSED}"
    printf '  "chromium": "%s",\n' "${CHROMIUM_RESULT}"
    printf '  "firefox": "%s",\n' "${FIREFOX_RESULT}"
    printf '  "routes_ok": "%s",\n' "${ROUTES_OK}"
    printf '  "images_ok": %s,\n' "${IMAGES_OK:-0}"
    printf '  "images_checked": %s,\n' "${IMAGES_CHECKED:-0}"
    printf '  "refresh_timer": "%s",\n' "$(systemctl is-active lords-content-refresh.timer 2>/dev/null || echo unknown)"
    printf '  "log": "%s",\n' "${LOG}"
    printf '  "evidence_dir": "%s",\n' "${W}"
    printf '  "before_screenshot": "%s",\n' "${W}/before-home.png"
    printf '  "after_screenshot": "%s",\n' "${W}/after-home.png"
    printf '  "updated_at_utc": "%s"\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '}\n'
  } > "${REPORT}.tmp" && mv -f "${REPORT}.tmp" "${REPORT}" && chmod 0644 "${REPORT}"
  case "${было}" in *e*) set -e ;; *) set +e ;; esac
  return 0
}

phase() { PHASE="$1"; report; say "=========="; }

restore_timer() {
  systemctl is-active --quiet lords-content-refresh.timer \
    || systemctl start lords-content-refresh.timer \
    || say "ВНИМАНИЕ: таймер обновления не запустился — верните вручную"
  say "обновление каталога: $(systemctl is-active lords-content-refresh.timer || true)"
}

on_exit() {
  if [ ! -s "${VERDICT}" ]; then
    [ -n "${REASON}" ] || REASON="сценарий завершился, не назвав причину"
    if [ "${SWITCHED}" = 1 ]; then verdict ROLLBACK_FAILED; else verdict ROLLED_BACK; fi
  fi
  restore_timer
  report "$(cat "${VERDICT}")"
  say "итог: $(cat "${VERDICT}") | журнал ${LOG} | отчёт ${REPORT}"
}
trap on_exit EXIT

. "${LAUNCH_LIB:-$(dirname "$0")/lords-unit-launch.sh}"

shot() {
  timeout 180 "${CH}" --no-sandbox --disable-gpu --disable-dev-shm-usage \
    --hide-scrollbars --window-size="${3:-1440}",2200 --virtual-time-budget=15000 \
    --user-data-dir="${W}/profile-$$-${RANDOM}" --screenshot="$2" "$1" >/dev/null 2>&1 || true
  if [ -s "$2" ]; then chmod 0644 "$2"; return 0; fi
  return 1
}

rollback() {
  if [ "${IN_ROLLBACK}" = 1 ]; then return 0; fi
  IN_ROLLBACK=1
  set +e
  REASON="$*"
  PHASE=откат
  say "ОТКАТ: $*"
  report ОТКАТ
  if [ -z "${PREV}" ] || [ ! -d "${PREV}" ]; then
    say "прежний релиз неизвестен или отсутствует: ${PREV:-пусто}"
    verdict ROLLBACK_FAILED; exit 1
  fi
  ln -sfn "${PREV}" "${RT}/.current.rollback" \
    || { say "временная ссылка не создана"; verdict ROLLBACK_FAILED; exit 1; }
  mv -T "${RT}/.current.rollback" "${RT}/current" \
    || { say "атомарная подмена ссылки не выполнена"; verdict ROLLBACK_FAILED; exit 1; }
  systemctl restart "${SITE}.service" || say "служба ${SITE} не перезапустилась"
  sleep 5
  local now code=""
  now="$(readlink -f "${RT}/current" || true)"
  if [ "${now}" != "${PREV}" ]; then
    say "current указывает на ${now:-пусто}, ожидался ${PREV}"
    verdict ROLLBACK_FAILED; exit 1
  fi
  if ! systemctl is-active --quiet "${SITE}.service"; then
    say "служба ${SITE} не работает после отката"
    verdict ROLLBACK_FAILED; exit 1
  fi
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "${BASE}/" || true)"
    [ "${code}" = 200 ] && break
    sleep 5
  done
  if [ "${code}" != 200 ]; then
    say "после отката публичный код ${code:-нет ответа}"
    verdict ROLLBACK_FAILED; exit 1
  fi
  NEW="${PREV}"
  say "откат подтверждён: current = $(basename "${PREV}"), служба работает, публичный код 200"
  verdict ROLLED_BACK; exit 1
}

on_fail() {
  local code=$?
  [ -n "${REASON}" ] || REASON="неожиданное завершение в фазе ${PHASE} (код ${code})"
  if [ "${SWITCHED}" = 1 ]; then rollback "${REASON}"; fi
  verdict ROLLED_BACK
  exit "${code}"
}
trap on_fail ERR
on_sig() {
  [ -n "${REASON}" ] || REASON="сигнал прерывания в фазе ${PHASE}"
  if [ "${SWITCHED}" = 1 ]; then rollback "${REASON}"; fi
  say "ОТКАЗ: сигнал прерывания до переключения; витрина не тронута"
  verdict ROLLED_BACK
  exit 1
}
trap on_sig INT TERM HUP

stop() { REASON="$*"; say "ОТКАЗ: $*"; verdict ROLLED_BACK; exit 1; }

# Два релиза одной витрины одновременно — это два писателя в одну ссылку.
exec 9>"${LOCK}"
flock -n 9 || { echo "релиз ${SITE} уже идёт: ${LOCK} занят"; exit 1; }

[ "$(id -u)" = 0 ] || stop "runner запускает root"

# ------------------------------------------------------------- предполёт --
phase предполёт
say "витрина ${SITE}, домен ${BASE}, журнал ${LOG}"

# Файл на noexec-разделе нельзя запускать напрямую: /run смонтирован noexec, и
# основной runner обязан лежать на исполняемой файловой системе.
СВОЙ="$(readlink -f "$0")"
if findmnt -no OPTIONS -T "${СВОЙ}" 2>/dev/null | grep -q noexec; then
  stop "runner лежит на noexec-разделе: ${СВОЙ}"
fi

HEAD_SHA="$(sudo -u claude git -C "${REPO}" rev-parse HEAD)"
[ "${HEAD_SHA}" = "${HEAD_EXPECT}" ] || stop "HEAD ${HEAD_SHA} вместо ${HEAD_EXPECT}"
[ -z "$(sudo -u claude git -C "${REPO}" status --porcelain)" ] || stop "дерево релиза не чистое"
DG="$(cd "${REPO}" && sudo -u claude "${PY}" -c 'import sys; sys.path.insert(0, "."); from factory.templates import digest; print(digest.compute()["template_digest"])')"
[ "${DG}" = "${DIGEST_EXPECT}" ] || stop "отпечаток дерева ${DG} вместо ${DIGEST_EXPECT}"
PIN="$(sed -n 's/^readonly EXPECT_DIGEST="\([0-9a-f]\{64\}\)".*/\1/p' "${HOST}/lords-canary-apply.sh" | head -1)"
[ "${PIN}" = "${DIGEST_EXPECT}" ] || stop "пин сценария ${PIN:-не найден} вместо ${DIGEST_EXPECT}"
(cd "${REPO}" && sudo -u claude "${PY}" -m pytest -q tests/unit/test_artifact_version_registry.py >/dev/null) \
  || stop "реестр версий артефакта не сошёлся с деревом"
REV="$(cd "${REPO}" && sudo -u claude "${PY}" "${HOST}/lords-canary-provenance.py" --verify)" \
  || stop "манифест происхождения не сошёлся"
[ "${#REV}" = 40 ] || stop "происхождение вернуло не полный SHA: ${REV}"
say "HEAD ${HEAD_SHA}, отпечаток ${DG}, ревизия оснастки ${REV}"

[ -s "/srv/site-factory/repo/var/lords/lords/catalog-cache/${SITE}.json" ] || stop "нет живого каталога ${SITE}"
PREV="$(readlink -f "${RT}/current" || true)"
[ -n "${PREV}" ] || stop "у витрины нет текущего релиза: откатываться будет некуда"
[ -d "${PREV}" ] || stop "текущий релиз ${PREV} не существует"
[ -f "${PREV}/release-manifest.json" ] || stop "у текущего релиза нет release-manifest.json"
say "точка отката: $(basename "${PREV}") (из её собственного манифеста)"

# Архив ревизии — ДО переключения и от владельца дерева.
#
# Дефект LORDS-RELEASE-ADOPT-GIT-PRIVILEGED-33: `adopt` внутри привилегированной
# фазы вызывал `git archive` в дереве, принадлежащем claude, и git отказывался
# работать с чужим каталогом. Манифест не записывался, и выкладка откатывалась
# уже после подмены ссылки. Здесь архив собирается заранее и без привилегий, а
# root только копирует готовый файл: git в привилегированном пути не участвует.
ARCHIVE="${ART_ROOT}/templates/${REV:0:12}.tar.gz"
if [ ! -f "${ARCHIVE}" ]; then
  say "собираю артефакт шаблона ${REV:0:12} от владельца дерева"
  TMPA="${REPO}/var/artifacts/${REV:0:12}.tar.gz"
  sudo -u claude mkdir -p "${REPO}/var/artifacts"
  sudo -u claude bash -c "git -C '${REPO}' archive --format=tar.gz '${REV}' > '${TMPA}'" \
    || stop "артефакт шаблона не собран"
  mkdir -p "${ART_ROOT}/templates"
  install -m 0644 -o root -g root "${TMPA}" "${ARCHIVE}" || stop "артефакт не установлен в хранилище"
fi
ARCHIVE_SHA="$(sha256sum "${ARCHIVE}" | cut -d' ' -f1)"
[ -s "${ARCHIVE}" ] || stop "артефакт шаблона пуст: ${ARCHIVE}"
say "артефакт ${ARCHIVE} готов, SHA-256 ${ARCHIVE_SHA}"

if [ ! -d "${REPO}/node_modules/@playwright/test" ]; then
  say "ставлю драйвер приёмки"
  (cd "${REPO}" && sudo -u claude npm ci --prefer-offline --no-audit --no-fund >/dev/null 2>&1) \
    || stop "драйвер приёмки не установлен"
fi
[ -x "${CH}" ] || stop "нет ${CH}"
[ -d /opt/pw-browsers/firefox-1538 ] || stop "нет движка Firefox"

PWCFG=${REPO}/var/release-acceptance.config.js
sudo -u claude tee "${PWCFG}" >/dev/null <<'PWEOF'
const { defineConfig, devices } = require('@playwright/test');
const launchOptions = { args: ['--no-sandbox', '--disable-dev-shm-usage'] };
module.exports = defineConfig({
  testDir: '../tests/e2e-release',
  timeout: 180000,
  expect: { timeout: 20000 },
  fullyParallel: false, forbidOnly: true, retries: 0, workers: 1,
  reporter: [['list'], ['json', { outputFile: 'var/artifacts/release-acceptance.json' }]],
  use: { trace: 'off', screenshot: 'only-on-failure' },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  ],
});
PWEOF

if systemctl is-active --quiet lords-content-refresh.timer; then
  systemctl stop lords-content-refresh.timer
fi

for ширина in 390 768 1440; do
  if shot "${BASE}/" "${W}/before-home-${ширина}.png" "${ширина}"; then
    SHOT_OK=1
    say "before-home-${ширина}.png $(stat -c%s "${W}/before-home-${ширина}.png") б"
  fi
done
cp -f "${W}/before-home-1440.png" "${W}/before-home.png" 2>/dev/null || true

# --------------------------------------------- сборка или повторное взятие --
phase сборка
reuse_ok=0
if [ -f "${RECEIPT}" ] && [ -d "${STAGING}" ]; then
  R="$("${PY}" - "${RECEIPT}" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(d.get("site_id", ""), d.get("template_digest", ""), d.get("content_snapshot_digest", ""),
      d.get("content_snapshot_items", 0), d.get("pages", 0), d.get("content_snapshot_path", ""))
PYEOF
)"
  read -r R_SITE R_DIGEST R_SHORT R_ITEMS R_PAGES R_SNAP <<<"${R}"
  if [ "${R_SITE}" = "${SITE}" ] && [ "${R_DIGEST}" = "${DIGEST_EXPECT}" ] && [ -f "${R_SNAP}" ]; then
    A_SHA="$(sha256sum "${R_SNAP}" | cut -d' ' -f1)"
    A_ITEMS="$("${PY}" -c '
import json, sys
raw = json.load(open(sys.argv[1], encoding="utf-8"))
items = raw.get("items") if isinstance(raw, dict) else raw
print(len(items or []))' "${R_SNAP}")"
    A_FILES="$(find "${STAGING}" -type f | wc -l)"
    A_EMPTY="$(find "${STAGING}" -type f -empty | wc -l)"
    A_PLAYERS="$(grep -rl 'video-player' "${STAGING}/title" 2>/dev/null | wc -l)"
    say "снимок ${A_SHA}"
    say "записей ${A_ITEMS}/${R_ITEMS}, файлов ${A_FILES}/${R_PAGES}, пустых ${A_EMPTY}, с плеером ${A_PLAYERS}"
    if [ "${A_SHA#${R_SHORT}}" != "${A_SHA}" ] && [ "${A_ITEMS}" = "${R_ITEMS}" ] \
       && [ "${A_FILES}" -ge "${R_PAGES}" ] && [ "${A_EMPTY}" = 0 ] && [ "${A_PLAYERS}" -gt 1000 ]; then
      reuse_ok=1; REUSED=да
      say "готовая сборка принята повторно: совпало всё сразу"
    else
      say "расхождение — собираю заново"
    fi
  else
    say "расписка не подходит (витрина ${R_SITE:-нет}, отпечаток ${R_DIGEST:0:16}) — собираю заново"
  fi
fi

render_beat() {
  say "сборка идёт $(( $1 / 60 )) мин, состояние $2, файлов в staging $(find "${STAGING}" -type f 2>/dev/null | wc -l)"
  report
}

if [ "${reuse_ok}" = 0 ]; then
  say "полная сборка витрины; это до трёх часов"
  MARK=/run/${SITE}-render.mark; : > "${MARK}"
  unit_start_confirmed "lords-canary-render@${SITE}.service" 60 \
    || stop "сборка не начата: новый процесс не появился за 60 с"
  say "сборка начата, InvocationID ${UNIT_RUN_ID}"
  if ! unit_wait "lords-canary-render@${SITE}.service" 25200 240 render_beat; then
    stop "сборка не выполнена (Result=${UNIT_RESULT:-нет}, ExecMainStatus=${UNIT_STATUS:-нет}); витрина не тронута"
  fi
  [ "${UNIT_RESULT}" = success ] || [ -z "${UNIT_RESULT}" ] \
    || stop "сборка завершилась с Result=${UNIT_RESULT}"
  [ -f "${RECEIPT}" ] || stop "нет расписки о сборке"
  [ "${RECEIPT}" -nt "${MARK}" ] || stop "расписка о сборке старее запуска"
  RD="$("${PY}" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("template_digest",""))' "${RECEIPT}")"
  [ "${RD}" = "${DIGEST_EXPECT}" ] || stop "расписка собрана на отпечатке ${RD}"
  say "сборка завершена, расписка обновлена"
fi

# ------------------------------------------------------- ворота до подмены --
phase ворота
SNAP="$("${PY}" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("content_snapshot_path") or "")' "${RECEIPT}")"
[ -f "${SNAP}" ] || stop "снимок из расписки не существует: ${SNAP:-пусто}"
if ! PYTHONPATH=${REPO} "${PY}" "${HOST}/lords-canary-gates.py" "${STAGING}" "${SNAP}" "${PREV}/site" > "${W}/gates.json"; then
  cat "${W}/gates.json" || true
  stop "ворота содержимого не пройдены; ссылка не трогалась"
fi
chmod 0644 "${W}/gates.json"
say "$(cat "${W}/gates.json")"

# ------------------------------------------------------------ переключение --
phase переключение
unit_start_confirmed "lords-canary-switch@${SITE}.service" 60 \
  || stop "переключение не начато: новый процесс не появился за 60 с"
say "переключение начато, InvocationID ${UNIT_RUN_ID}"
switch_beat() { say "переключение идёт $1 с, состояние $2"; report; }
switch_ok=1
unit_wait "lords-canary-switch@${SITE}.service" 3600 240 switch_beat || switch_ok=0
NEW="$(readlink -f "${RT}/current" || true)"
SWITCHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ "${switch_ok}" = 0 ]; then
  if [ "${NEW}" = "${PREV}" ]; then
    stop "переключение не выполнено (Result=${UNIT_RESULT:-нет}); сценарий вернул витрину сам"
  fi
  SWITCHED=1
  rollback "переключение не выполнено (Result=${UNIT_RESULT:-нет}), ссылка не на прежнем релизе"
fi
[ -n "${NEW}" ] || { SWITCHED=1; rollback "после переключения нет current"; }
[ "${NEW}" != "${PREV}" ] || stop "ссылка осталась на прежнем релизе: переключения не было"
SWITCHED=1
say "ссылка переключена: $(basename "${PREV}") → $(basename "${NEW}") в ${SWITCHED_AT}"
[ -f "${NEW}/release-manifest.json" ] || rollback "у нового релиза нет release-manifest.json"
cp -f "${NEW}/release-manifest.json" "${W}/release-manifest.json"; chmod 0644 "${W}/release-manifest.json"
say "манифест нового релиза: $(tr -d '\n ' < "${NEW}/release-manifest.json" | head -c 400)"
report

# ------------------------------------------------------------ приёмка --
phase приёмка
systemctl is-active --quiet "${SITE}.service" || rollback "служба ${SITE} не работает после переключения"

if ! sudo -u claude "${PY}" "${HOST}/lords-post-switch-verify.py" \
      --site "${SITE}" --expect-digest "${DIGEST_EXPECT}" \
      --previous-release "$(basename "${PREV}")" > "${W}/post-switch-verify.json"; then
  cat "${W}/post-switch-verify.json" || true
  rollback "lords-post-switch-verify: ROLLBACK_RECOMMENDED"
fi
chmod 0644 "${W}/post-switch-verify.json"

# Публичный домен: маршруты, коды, tenant, плеер.
ok_routes=""
for маршрут in "/" "/catalog/" "/search/" "/new/"; do
  код="$(curl -sS -o "${W}/route$(echo "${маршрут}" | tr '/' '_').html" -w '%{http_code}' --max-time 30 "${BASE}${маршрут}" || true)"
  [ "${код}" = 200 ] || rollback "публичный ${маршрут} ответил ${код:-нет ответа}"
  ok_routes="${ok_routes}${маршрут}=200 "
done
grep -q "${DOMAIN}" "${W}/route_.html" || rollback "главная не назвала свой домен"
TP="$(grep -o 'href="/title/[^"]*"' "${W}/route_.html" | head -1 | cut -d'"' -f2)"
[ -n "${TP}" ] || rollback "на публичной главной нет ссылок на произведения"
код="$(curl -sS -o "${W}/public-title.html" -w '%{http_code}' --max-time 30 "${BASE}${TP}" || true)"
[ "${код}" = 200 ] || rollback "публичная ${TP} ответила ${код}"
ok_routes="${ok_routes}${TP}=200"
ROUTES_OK="${ok_routes}"
grep -qi 'video-player\|<iframe' "${W}/public-title.html" || rollback "плеер на публичной ${TP} исчез"
say "маршруты: ${ROUTES_OK}"
say "плеер на ${TP} сохранён"

# Изображения: не меньше тридцати, с кодом и типом, и не чёрная заглушка.
IMG_JSON="${W}/images.json"
"${PY}" - "${BASE}" "${W}/route_catalog_.html" "${W}/public-title.html" "${IMG_JSON}" <<'PYEOF' || true
import json, re, sys, urllib.request
base, *страницы, out = sys.argv[1:]
адреса, видел = [], set()
for стр in страницы:
    try:
        html = open(стр, encoding="utf-8", errors="replace").read()
    except OSError:
        continue
    for src in re.findall(r'<img[^>]+src="([^"]+)"', html):
        полный = src if src.startswith("http") else base + src
        if полный not in видел:
            видел.add(полный); адреса.append(полный)
проверено, годных, беды = 0, 0, []
for адрес in адреса[:40]:
    проверено += 1
    try:
        req = urllib.request.Request(адрес, headers={"User-Agent": "lords-release-check"})
        with urllib.request.urlopen(req, timeout=20) as ответ:
            тип = ответ.headers.get("Content-Type", "")
            тело = ответ.read(200000)
        if ответ.status == 200 and тип.startswith("image/") and len(тело) > 1200:
            годных += 1
        else:
            беды.append({"url": адрес, "status": ответ.status, "type": тип, "bytes": len(тело)})
    except Exception as ошибка:
        беды.append({"url": адрес, "error": str(ошибка)[:120]})
json.dump({"checked": проверено, "ok": годных, "failures": беды[:10]},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF
if [ -f "${IMG_JSON}" ]; then
  chmod 0644 "${IMG_JSON}"
  IMAGES_CHECKED="$("${PY}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["checked"])' "${IMG_JSON}")"
  IMAGES_OK="$("${PY}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["ok"])' "${IMG_JSON}")"
fi
say "изображения: годных ${IMAGES_OK} из ${IMAGES_CHECKED} проверенных"
[ "${IMAGES_CHECKED}" -ge 30 ] || rollback "проверено только ${IMAGES_CHECKED} изображений из требуемых 30"
[ "${IMAGES_OK}" -ge 30 ] || rollback "загрузились только ${IMAGES_OK} изображений из ${IMAGES_CHECKED}"

# Штатный набор приёмки в двух движках.
run_engine() {
  (cd "${REPO}" && sudo -u claude env PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
    RELEASE_BASE="${BASE}" RELEASE_SITE="${SITE}" \
    npx playwright test --config=var/release-acceptance.config.js --project="$1" \
    > "${W}/playwright-$1.log" 2>&1)
}
if run_engine chromium; then CHROMIUM_RESULT=pass; else CHROMIUM_RESULT=fail; fi
if run_engine firefox; then FIREFOX_RESULT=pass; else FIREFOX_RESULT=fail; fi
chmod 0644 "${W}"/playwright-*.log 2>/dev/null || true
say "Chromium: ${CHROMIUM_RESULT}, Firefox: ${FIREFOX_RESULT}"
report
[ "${CHROMIUM_RESULT}" = pass ] || { tail -40 "${W}/playwright-chromium.log" || true; rollback "приёмка в Chromium не пройдена"; }
[ "${FIREFOX_RESULT}" = pass ] || { tail -40 "${W}/playwright-firefox.log" || true; rollback "приёмка в Firefox не пройдена"; }

for ширина in 390 768 1440; do
  shot "${BASE}/" "${W}/after-home-${ширина}.png" "${ширина}" \
    && say "after-home-${ширина}.png $(stat -c%s "${W}/after-home-${ширина}.png") б" || true
done
cp -f "${W}/after-home-1440.png" "${W}/after-home.png" 2>/dev/null || true
if [ "${SHOT_OK}" = 1 ] && [ ! -s "${W}/after-home.png" ]; then
  rollback "снимок «после» не получен, хотя снимок «до» снялся"
fi

phase готово
say "релиз $(basename "${NEW}"), прежний $(basename "${PREV}")"
verdict DEPLOYED_AND_VERIFIED
exit 0
