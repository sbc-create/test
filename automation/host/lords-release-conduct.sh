#!/bin/bash
# Последовательная выкладка витрин Lords: сначала канарейка, затем остальные.
#
# Провал одной витрины не трогает две другие: каждая имеет собственный релиз,
# манифест, точку отката и публичную проверку. Но канарейка — условие: если она
# не прошла, распространение не начинается вовсе.
set -Eeuo pipefail

CANARY="${CANARY:-lords-02}"
ОСТАЛЬНЫЕ="${ОСТАЛЬНЫЕ:-lords-01 lords-03}"
RUNNER="${RUNNER:-/run/lords-release-runner.sh}"
SUMMARY=/var/log/site-factory/lords-release-summary.json
STAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG=/var/log/site-factory/lords-release-conduct-${STAMP}.log

: > "${LOG}"; chmod 0644 "${LOG}"
exec > >(tee -a "${LOG}") 2>&1

итоги=""

свод() {
  {
    printf '{\n  "started_at_utc": "%s",\n' "${STAMP}"
    printf '  "updated_at_utc": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '  "conduct_log": "%s",\n' "${LOG}"
    printf '  "sites": {%s\n  }\n}\n' "${итоги}"
  } > "${SUMMARY}.tmp" && mv -f "${SUMMARY}.tmp" "${SUMMARY}" && chmod 0644 "${SUMMARY}"
}

выложить() {
  local сайт="$1" итог=""
  echo "=== выкладка ${сайт} ==="
  # Файл лежит на noexec-разделе: запуск только через интерпретатор.
  /bin/bash "${RUNNER}" "${сайт}" || true
  итог="$(cat "/run/${сайт}-release.verdict" 2>/dev/null || echo НЕТ_ИТОГА)"
  [ -n "${итоги}" ] && итоги="${итоги},"
  итоги="${итоги}\n    \"${сайт}\": {\"verdict\": \"${итог}\", \"report\": \"/var/log/site-factory/${сайт}-release-report.json\"}"
  свод
  echo "=== ${сайт}: ${итог} ==="
  [ "${итог}" = DEPLOYED_AND_VERIFIED ]
}

свод
if ! выложить "${CANARY}"; then
  echo "канарейка ${CANARY} не прошла — распространение не начинается"
  свод
  exit 1
fi

for сайт in ${ОСТАЛЬНЫЕ}; do
  выложить "${сайт}" || echo "витрина ${сайт} не выложена; остальные не тронуты"
done

свод
echo "свод: ${SUMMARY}"
