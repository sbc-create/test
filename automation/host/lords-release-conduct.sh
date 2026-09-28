#!/bin/bash
# Последовательная выкладка витрин Lords: сначала канарейка, затем остальные.
#
# Провал одной витрины не трогает две другие: каждая имеет собственный релиз,
# манифест, точку отката и публичную проверку. Но канарейка — условие: если она
# не прошла, распространение не начинается вовсе.
set -Eeuo pipefail

CANARY="${CANARY:-lords-02}"
REST_SITES="${REST_SITES:-lords-01 lords-03}"
RUNNER="${RUNNER:-/run/lords-release-runner.sh}"
SUMMARY=/var/log/site-factory/lords-release-summary.json
STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG=/var/log/site-factory/lords-release-conduct-${STAMP}.log

: > "${LOG}"; chmod 0644 "${LOG}"
exec > >(tee -a "${LOG}") 2>&1

summary_items=""

write_summary() {
  {
    printf '{\n  "started_at_utc": "%s",\n' "${STAMP}"
    printf '  "updated_at_utc": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '  "conduct_log": "%s",\n' "${LOG}"
    printf '  "sites": {%s\n  }\n}\n' "${summary_items}"
  } > "${SUMMARY}.tmp" && mv -f "${SUMMARY}.tmp" "${SUMMARY}" && chmod 0644 "${SUMMARY}"
}

deploy_site() {
  local site="$1" verdict_text=""
  echo "=== выкладка ${site} ==="
  # Файл лежит на noexec-разделе: запуск только через интерпретатор.
  /bin/bash "${RUNNER}" "${site}" || true
  verdict_text="$(cat "/run/${site}-release.verdict" 2>/dev/null || echo "НЕТ_ИТОГА")"
  [ -n "${summary_items}" ] && summary_items="${summary_items},"
  summary_items="${summary_items}\n    \"${site}\": {\"verdict\": \"${verdict_text}\", \"report\": \"/var/log/site-factory/${site}-release-report.json\"}"
  write_summary
  echo "=== ${site}: ${verdict_text} ==="
  [ "${verdict_text}" = DEPLOYED_AND_VERIFIED ]
}

write_summary
if ! deploy_site "${CANARY}"; then
  echo "канарейка ${CANARY} не прошла — распространение не начинается"
  write_summary
  exit 1
fi

for site in ${REST_SITES}; do
  deploy_site "${site}" || echo "витрина ${site} не выложена; остальные не тронуты"
done

write_summary
echo "свод: ${SUMMARY}"
