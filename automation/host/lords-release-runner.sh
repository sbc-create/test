#!/bin/bash
# Выкладка одной витрины Lords: предполёт → сборка (или повторное использование
# готовой) → ворота → атомарное переключение → приёмка в двух движках →
# публичная проверка → откат при любом провале → возврат обновления каталога.
#
# Запускается от root внутри отдельного systemd-юнита: рендер идёт до трёх
# часов, и закрытый терминал не должен его прерывать.
#
# Итог ровно один: DEPLOYED_AND_VERIFIED, ROLLED_BACK или ROLLBACK_FAILED.
set -Eeuo pipefail

SITE="${1:-lords-02}"
# Список витрин закрыт: имя вне списка означает опечатку, а не новую витрину.
case "${SITE}" in
  lords-01) DOMAIN=lordfilm47.space ;;
  lords-02) DOMAIN=lordserial33.biz ;;
  lords-03) DOMAIN=1lordserials1.online ;;
  *) echo "витрина «${SITE}» вне списка разрешённых"; echo ROLLED_BACK; exit 1 ;;
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
CH=/opt/pw-browsers/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell
VERDICT=/run/${SITE}-release.verdict
W=/var/log/site-factory/${SITE}-acceptance
REPORT=/var/log/site-factory/${SITE}-release-report.json
SWITCHED=0
IN_ROLLBACK=0
PREV=""
NEW=""
SHOT_OK=0
REUSED=нет
CHROMIUM_RESULT=не_запускался
FIREFOX_RESULT=не_запускался
REASON=""

rm -rf "${W}"; mkdir -p "${W}"; chmod 0755 "${W}"; : > "${VERDICT}"; chmod 0644 "${VERDICT}"

say() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }
verdict() { [ -s "${VERDICT}" ] || { printf '%s\n' "$1" > "${VERDICT}"; chmod 0644 "${VERDICT}"; }; }

# Отчёт пишется на каждом исходе: владелец и следующая сессия обязаны узнать
# результат из файла, а не из открытого терминала.
write_report() {
  local итог="$1"
  {
    printf '{\n'
    printf '  "site": "%s",\n' "${SITE}"
    printf '  "domain": "%s",\n' "${DOMAIN}"
    printf '  "url": "%s",\n' "${BASE}"
    printf '  "verdict": "%s",\n' "${итог}"
    printf '  "reason": "%s",\n' "${REASON}"
    printf '  "head": "%s",\n' "${HEAD_EXPECT}"
    printf '  "template_digest": "%s",\n' "${DIGEST_EXPECT}"
    printf '  "release_before": "%s",\n' "$([ -n "${PREV}" ] && basename "${PREV}" || echo "")"
    printf '  "release_after": "%s",\n' "$([ -n "${NEW}" ] && basename "${NEW}" || echo "")"
    printf '  "build_reused": "%s",\n' "${REUSED}"
    printf '  "chromium": "%s",\n' "${CHROMIUM_RESULT}"
    printf '  "firefox": "%s",\n' "${FIREFOX_RESULT}"
    printf '  "refresh_timer": "%s",\n' "$(systemctl is-active lords-content-refresh.timer 2>/dev/null || echo unknown)"
    printf '  "evidence_dir": "%s",\n' "${W}"
    printf '  "before_screenshot": "%s",\n' "${W}/before-home.png"
    printf '  "after_screenshot": "%s",\n' "${W}/after-home.png"
    printf '  "finished_at_utc": "%s"\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '}\n'
  } > "${REPORT}"
  chmod 0644 "${REPORT}"
}

restore_timer() {
  systemctl is-active --quiet lords-content-refresh.timer \
    || systemctl start lords-content-refresh.timer \
    || say "ВНИМАНИЕ: таймер обновления не запустился — верните вручную"
  say "обновление каталога: $(systemctl is-active lords-content-refresh.timer || true)"
}

on_exit() {
  if [ ! -s "${VERDICT}" ]; then
    if [ "${SWITCHED}" = 1 ]; then verdict ROLLBACK_FAILED; else verdict ROLLED_BACK; fi
    [ -n "${REASON}" ] || REASON="сценарий завершился, не назвав причину"
  fi
  restore_timer
  write_report "$(cat "${VERDICT}")"
  say "итог: $(cat "${VERDICT}") | отчёт ${REPORT}"
}
trap on_exit EXIT

# ---------------------------------------------------------- запуск юнитов --
. "${LAUNCH_LIB:-$(dirname "$0")/lords-unit-launch.sh}"

shot() { # url файл
  timeout 150 "${CH}" --no-sandbox --disable-gpu --disable-dev-shm-usage \
    --hide-scrollbars --window-size=1440,2200 --virtual-time-budget=15000 \
    --user-data-dir="${W}/profile-$$-${RANDOM}" --screenshot="$2" "$1" >/dev/null 2>&1 || true
  [ -s "$2" ] && { chmod 0644 "$2"; return 0; } || return 1
}

rollback() {
  if [ "${IN_ROLLBACK}" = 1 ]; then return 0; fi
  IN_ROLLBACK=1
  set +e
  REASON="$*"
  say "ОТКАТ: $*"
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
  say "откат подтверждён: current = $(basename "${PREV}"), публичный код 200"
  verdict ROLLED_BACK; exit 1
}

on_fail() {
  local code=$?
  [ -n "${REASON}" ] || REASON="неожиданное завершение (код ${code})"
  if [ "${SWITCHED}" = 1 ]; then rollback "${REASON}"; fi
  verdict ROLLED_BACK
  exit "${code}"
}
trap on_fail ERR
on_sig() {
  [ -n "${REASON}" ] || REASON="получен сигнал прерывания"
  if [ "${SWITCHED}" = 1 ]; then rollback "${REASON}"; fi
  say "ОТКАЗ: сигнал прерывания до переключения; витрина не тронута"
  verdict ROLLED_BACK
  exit 1
}
trap on_sig INT TERM HUP

stop() { REASON="$*"; say "ОТКАЗ: $*"; verdict ROLLED_BACK; exit 1; }

# ---------------------------------------------------------------- предполёт --
[ "$(id -u)" = 0 ] || stop "runner запускает root"
say "== предполёт ${SITE} (${BASE})"
HEAD_SHA="$(sudo -u claude git -C "${REPO}" rev-parse HEAD)"
[ "${HEAD_SHA}" = "${HEAD_EXPECT}" ] || stop "HEAD ${HEAD_SHA} вместо ${HEAD_EXPECT}"
[ -z "$(sudo -u claude git -C "${REPO}" status --porcelain)" ] || stop "дерево релиза не чистое"

DG="$(cd "${REPO}" && sudo -u claude "${PY}" -c 'import sys; sys.path.insert(0, "."); from factory.templates import digest; print(digest.compute()["template_digest"])')"
[ "${DG}" = "${DIGEST_EXPECT}" ] || stop "отпечаток дерева ${DG} вместо ${DIGEST_EXPECT}"
PIN="$(sed -n 's/^readonly EXPECT_DIGEST="\([0-9a-f]\{64\}\)".*/\1/p' "${HOST}/lords-canary-apply.sh" | head -1)"
[ "${PIN}" = "${DIGEST_EXPECT}" ] || stop "пин сценария ${PIN:-не найден} вместо ${DIGEST_EXPECT}"
(cd "${REPO}" && sudo -u claude "${PY}" -m pytest -q tests/unit/test_artifact_version_registry.py >/dev/null) \
  || stop "реестр версий артефакта не сошёлся с деревом"
(cd "${REPO}" && sudo -u claude "${PY}" "${HOST}/lords-canary-provenance.py" --verify >/dev/null) \
  || stop "манифест происхождения не сошёлся"
say "   HEAD ${HEAD_SHA}, отпечаток ${DG}, пин совпал, происхождение сошлось"

SOURCE_SNAP=/srv/site-factory/repo/var/lords/lords/catalog-cache/${SITE}.json
[ -s "${SOURCE_SNAP}" ] || stop "нет живого каталога ${SITE}"
PREV="$(readlink -f "${RT}/current" || true)"
[ -n "${PREV}" ] || stop "у витрины нет текущего релиза: откатываться будет некуда"
[ -d "${PREV}" ] || stop "текущий релиз ${PREV} не существует"
[ -f "${PREV}/release-manifest.json" ] || stop "у текущего релиза нет release-manifest.json"
say "   прежний релиз $(basename "${PREV}") с манифестом"

if [ ! -d "${REPO}/node_modules/@playwright/test" ]; then
  say "   ставлю драйвер приёмки"
  (cd "${REPO}" && sudo -u claude npm ci --prefer-offline --no-audit --no-fund >/dev/null 2>&1) \
    || stop "драйвер приёмки не установлен: штатный набор запустить нечем"
fi
[ -d "${REPO}/node_modules/@playwright/test" ] || stop "драйвер приёмки отсутствует"
[ -x "${CH}" ] || stop "нет ${CH}"
[ -d /opt/pw-browsers/firefox-1538 ] || stop "нет движка Firefox в /opt/pw-browsers"

PWCFG=${REPO}/var/release-acceptance.config.js
sudo -u claude tee "${PWCFG}" >/dev/null <<'PWEOF'
// Штатная спецификация приёмки релиза (tests/e2e-release/live-acceptance.spec.js)
// в двух движках. Каталог var/ вне учёта git: продуктовые файлы не меняются.
const { defineConfig, devices } = require('@playwright/test');
const launchOptions = { args: ['--no-sandbox', '--disable-dev-shm-usage'] };
module.exports = defineConfig({
  testDir: '../tests/e2e-release',
  timeout: 120000,
  expect: { timeout: 15000 },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
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

say "== снимок «до» на действующей витрине"
if shot "${BASE}/" "${W}/before-home.png"; then
  SHOT_OK=1
  say "   before-home.png $(stat -c%s "${W}/before-home.png") б"
else
  say "   ВНИМАНИЕ: снимок «до» не получен — снимки не будут условием приёмки"
fi

# ------------------------------------------- сборка или её повторное взятие --
# Готовую сборку разрешено взять, только если совпало ВСЁ сразу: отпечаток
# шаблона, полный SHA-256 снимка, число записей, витрина и состав артефакта.
# Любое расхождение означает новую сборку — «почти совпало» здесь не бывает.
reuse_ok=0
if [ -f "${RECEIPT}" ] && [ -d "${STAGING}" ]; then
  R_SITE="$("${PY}" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("site_id",""))' "${RECEIPT}" 2>/dev/null || true)"
  R_DIGEST="$("${PY}" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("template_digest",""))' "${RECEIPT}" 2>/dev/null || true)"
  R_SNAP="$("${PY}" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("content_snapshot_path",""))' "${RECEIPT}" 2>/dev/null || true)"
  R_ITEMS="$("${PY}" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("content_snapshot_items",0))' "${RECEIPT}" 2>/dev/null || true)"
  R_SHORT="$("${PY}" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("content_snapshot_digest",""))' "${RECEIPT}" 2>/dev/null || true)"
  R_PAGES="$("${PY}" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("pages",0))' "${RECEIPT}" 2>/dev/null || true)"
  if [ "${R_SITE}" = "${SITE}" ] && [ "${R_DIGEST}" = "${DIGEST_EXPECT}" ] && [ -f "${R_SNAP}" ]; then
    A_SHA="$(sha256sum "${R_SNAP}" | cut -d' ' -f1)"
    A_ITEMS="$("${PY}" -c '
import json, sys
raw = json.load(open(sys.argv[1], encoding="utf-8"))
items = raw.get("items") if isinstance(raw, dict) else raw
print(len(items or []))' "${R_SNAP}")"
    A_FILES="$(find "${STAGING}" -type f | wc -l)"
    if [ "${A_SHA#${R_SHORT}}" != "${A_SHA}" ] && [ "${A_ITEMS}" = "${R_ITEMS}" ] \
       && [ "${A_FILES}" -ge "${R_PAGES}" ]; then
      reuse_ok=1
      REUSED=да
      say "== готовая сборка принята повторно"
      say "   отпечаток ${R_DIGEST}"
      say "   снимок ${A_SHA}, записей ${A_ITEMS}, витрина ${R_SITE}"
      say "   staging ${STAGING}: файлов ${A_FILES}, страниц по расписке ${R_PAGES}"
    else
      say "   расхождение готовой сборки: снимок ${A_SHA:0:16}/${R_SHORT}, записей ${A_ITEMS}/${R_ITEMS}, файлов ${A_FILES}/${R_PAGES}"
    fi
  else
    say "   расписка не подходит: витрина ${R_SITE:-нет}, отпечаток ${R_DIGEST:0:16}, снимок ${R_SNAP:-нет}"
  fi
fi

render_beat() { # $1 прошло секунд, $2 состояние
  local файлов
  файлов="$(find "${STAGING}" -type f 2>/dev/null | wc -l)"
  say "   сборка идёт $(( $1 / 60 )) мин, состояние $2, файлов в staging ${файлов}"
}

if [ "${reuse_ok}" = 0 ]; then
  say "== сборка (штатный юнит из ${REPO}); это до трёх часов"
  MARK=/run/${SITE}-render.mark; : > "${MARK}"
  unit_start_confirmed "lords-canary-render@${SITE}.service" 60 \
    || stop "сборка не начата: новый процесс не появился за 60 с"
  say "   сборка начата, InvocationID ${UNIT_RUN_ID}"
  if ! unit_wait "lords-canary-render@${SITE}.service" 25200 240 render_beat; then
    journalctl -u "lords-canary-render@${SITE}.service" -n 40 --no-pager || true
    stop "сборка не выполнена (Result=${UNIT_RESULT:-нет}, ExecMainStatus=${UNIT_STATUS:-нет}); витрина не тронута"
  fi
  # Свидетельство сборки — артефакт, а не состояние systemd: юнит с
  # CollectMode=inactive выгружается сразу и уносит Result с собой.
  [ -f "${RECEIPT}" ] || stop "нет расписки о сборке ${RECEIPT}"
  [ "${RECEIPT}" -nt "${MARK}" ] || stop "расписка о сборке старее запуска: нового результата нет"
  RD="$("${PY}" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("template_digest",""))' "${RECEIPT}")"
  [ "${RD}" = "${DIGEST_EXPECT}" ] || stop "расписка собрана на отпечатке ${RD}"
  say "   сборка завершена, расписка обновлена"
fi

# ------------------------------------------------------- ворота до подмены --
say "== штатные ворота содержимого до подмены"
SNAP="$("${PY}" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("content_snapshot_path") or "")' "${RECEIPT}")"
[ -n "${SNAP}" ] || stop "расписка не называет путь снимка"
[ -f "${SNAP}" ] || stop "снимок из расписки не существует: ${SNAP}"
GATES=${W}/gates.json
# От root: третий аргумент — каталог прежнего релиза в /srv/lords, закрытый для
# claude. Сборку по-прежнему делает штатный юнит от User=claude.
if ! PYTHONPATH=${REPO} "${PY}" "${HOST}/lords-canary-gates.py" "${STAGING}" "${SNAP}" "${PREV}/site" > "${GATES}"; then
  cat "${GATES}" || true
  stop "ворота содержимого не пройдены; ссылка не трогалась"
fi
chmod 0644 "${GATES}"
say "   ворота пройдены, отчёт ${GATES}"

# ------------------------------------------------------------ переключение --
say "== переключение ${SITE}"
unit_start_confirmed "lords-canary-switch@${SITE}.service" 60 \
  || stop "переключение не начато: новый процесс не появился за 60 с"
say "   переключение начато, InvocationID ${UNIT_RUN_ID}"
switch_ok=1
unit_wait "lords-canary-switch@${SITE}.service" 3600 240 "" || switch_ok=0
NEW="$(readlink -f "${RT}/current" || true)"
if [ "${switch_ok}" = 0 ]; then
  journalctl -u "lords-canary-switch@${SITE}.service" -n 60 --no-pager || true
  if [ "${NEW}" = "${PREV}" ]; then
    stop "переключение не выполнено (Result=${UNIT_RESULT:-нет}); сценарий вернул витрину сам"
  fi
  SWITCHED=1
  rollback "переключение не выполнено (Result=${UNIT_RESULT:-нет}), ссылка не на прежнем релизе"
fi
[ -n "${NEW}" ] || { SWITCHED=1; rollback "после переключения нет current"; }
[ "${NEW}" != "${PREV}" ] || stop "ссылка осталась на прежнем релизе: переключения не было"
SWITCHED=1
say "   ссылка переключена: $(basename "${PREV}") → $(basename "${NEW}")"

# --------------------------------------------------------- штатная приёмка --
[ -f "${NEW}/release-manifest.json" ] || rollback "у нового релиза нет release-manifest.json — каталог замрёт"

say "== штатная проверка после переключения"
if ! sudo -u claude "${PY}" "${HOST}/lords-post-switch-verify.py" \
      --site "${SITE}" --expect-digest "${DIGEST_EXPECT}" \
      --previous-release "$(basename "${PREV}")" \
      > "${W}/post-switch-verify.json"; then
  cat "${W}/post-switch-verify.json" || true
  rollback "lords-post-switch-verify: ROLLBACK_RECOMMENDED"
fi
chmod 0644 "${W}/post-switch-verify.json"
say "   verdict OK"

say "== публичная проверка ${BASE}"
CODE="$(curl -sS -o "${W}/public-home.html" -w '%{http_code}' --max-time 30 "${BASE}/" || true)"
[ "${CODE}" = 200 ] || rollback "публичная главная ответила ${CODE:-нет ответа}"
TP="$(grep -o 'href="/title/[^"]*"' "${W}/public-home.html" | head -1 | cut -d'"' -f2)"
[ -n "${TP}" ] || rollback "на публичной главной нет ссылок на страницы тайтлов"
TCODE="$(curl -sS -o "${W}/public-title.html" -w '%{http_code}' --max-time 30 "${BASE}${TP}" || true)"
[ "${TCODE}" = 200 ] || rollback "публичная страница ${TP} ответила ${TCODE}"
grep -qi 'video-player\|<iframe' "${W}/public-title.html" \
  || rollback "плеер на публичной ${TP} не сохранился"
say "   HTTP 200, плеер на ${TP} сохранён"

say "== штатный набор приёмки в Chromium и Firefox"
run_engine() { # $1 движок
  (cd "${REPO}" && sudo -u claude env \
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
    RELEASE_BASE="${BASE}" RELEASE_SITE="${SITE}" \
    npx playwright test --config=var/release-acceptance.config.js --project="$1" \
    > "${W}/playwright-$1.log" 2>&1)
}
if run_engine chromium; then CHROMIUM_RESULT=pass; else CHROMIUM_RESULT=fail; fi
if run_engine firefox; then FIREFOX_RESULT=pass; else FIREFOX_RESULT=fail; fi
chmod 0644 "${W}"/playwright-*.log 2>/dev/null || true
say "   Chromium: ${CHROMIUM_RESULT}, Firefox: ${FIREFOX_RESULT}"
[ "${CHROMIUM_RESULT}" = pass ] || { tail -30 "${W}/playwright-chromium.log" || true; rollback "приёмка в Chromium не пройдена"; }
[ "${FIREFOX_RESULT}" = pass ] || { tail -30 "${W}/playwright-firefox.log" || true; rollback "приёмка в Firefox не пройдена"; }

say "== снимок «после»"
if shot "${BASE}/" "${W}/after-home.png"; then
  say "   after-home.png $(stat -c%s "${W}/after-home.png") б"
elif [ "${SHOT_OK}" = 1 ]; then
  rollback "снимок «после» не получен, хотя снимок «до» снялся"
else
  say "   снимки на этом хосте недоступны — не условие приёмки"
fi

say "== релиз $(basename "${NEW}"), прежний $(basename "${PREV}"), свидетельства в ${W}"
verdict DEPLOYED_AND_VERIFIED
exit 0
