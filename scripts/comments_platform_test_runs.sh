#!/usr/bin/env bash
# Two consecutive full runs of every gate, from a clean state, with the actual
# exit codes recorded.
#
# Two runs rather than one because a suite that passes once may still be order
# dependent, may leak state between cases, or may have left a file the second
# run trips over. A single green run does not distinguish "correct" from
# "correct this time".
#
# Nothing here touches production, a staging host, DNS, TLS or systemd. The
# browser suite serves a local fixture over loopback and mocks the API; the
# database tests use pytest's tmp_path or an in-memory database.
set -uo pipefail

cd "$(dirname "$0")/.."
REPO="$PWD"
OUT="$REPO/artifacts/evidence/community-comments-platform-01/04-tests"
mkdir -p "$OUT"

LOG="$OUT/TEST_RUNS.log"
JSON="$OUT/TEST_RUNS.json"
: > "$LOG"

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
commit="$(git rev-parse HEAD)"

declare -a results=()
overall=0

run_gate() {
  local run_index="$1" name="$2"
  shift 2
  local started ended code
  started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  {
    echo "=================================================================="
    echo "run ${run_index} | gate ${name}"
    echo "command: $*"
    echo "started: ${started}"
    echo "------------------------------------------------------------------"
  } >> "$LOG"

  "$@" >> "$LOG" 2>&1
  code=$?
  ended="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  {
    echo "------------------------------------------------------------------"
    echo "exit code: ${code}"
    echo "ended: ${ended}"
    echo
  } >> "$LOG"

  results+=("{\"run\":${run_index},\"gate\":\"${name}\",\"command\":\"$*\",\"exit_code\":${code},\"started_at\":\"${started}\",\"ended_at\":\"${ended}\"}")
  if [ "$code" -ne 0 ]; then
    overall=1
    echo "FAIL  run ${run_index}  ${name}  (exit ${code})"
  else
    echo "ok    run ${run_index}  ${name}"
  fi
}

for run in 1 2; do
  echo "--- full run ${run} ---"
  # Clean state between runs: caches from run 1 must not make run 2 pass.
  rm -rf "$REPO/.pytest_cache" "$REPO/test-results"
  find "$REPO/factory/comments_platform" "$REPO/tests/unit/comments_platform" \
    -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null

  # Scoped to this module's own paths, deliberately. A run of `ruff --fix`
  # over all of factory/ during this stage auto-modified 30 files belonging to
  # the ratings contour and two other products; they were reverted, and the
  # gate is written narrowly so the mistake is not repeatable from here.
  run_gate "$run" "ruff" \
    python3 -m ruff check factory/comments_platform/ tests/unit/comments_platform/ \
    scripts/comments_platform_artifact.py scripts/comments_platform_evidence.py \
    bin/comments-owner-cookie
  run_gate "$run" "pytest-unit" \
    python3 -m pytest tests/unit/comments_platform/ -q -p no:randomly
  run_gate "$run" "artifact-checksum" \
    python3 scripts/comments_platform_artifact.py --check
  run_gate "$run" "evidence-freshness" \
    python3 scripts/comments_platform_evidence.py --check
  run_gate "$run" "playwright-widget" \
    npx playwright test --config=playwright.comments.config.js --workers=2
  run_gate "$run" "shell-syntax" \
    bash -n automation/host/animedia-comments-stage1-apply.sh
  run_gate "$run" "shell-syntax-rollback" \
    bash -n automation/host/animedia-comments-stage1-rollback.sh
done

ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

{
  printf '{\n'
  printf '  "schema_version": "COMMENTS_TEST_RUNS_V1",\n'
  printf '  "commit": "%s",\n' "$commit"
  printf '  "started_at": "%s",\n' "$started_at"
  printf '  "ended_at": "%s",\n' "$ended_at"
  printf '  "full_runs_consecutive": 2,\n'
  printf '  "clean_state_between_runs": true,\n'
  printf '  "production_touched": false,\n'
  printf '  "log": "artifacts/evidence/community-comments-platform-01/04-tests/TEST_RUNS.log",\n'
  printf '  "overall_exit_code": %s,\n' "$overall"
  printf '  "gates": [\n'
  local_first=1
  for entry in "${results[@]}"; do
    if [ "$local_first" -eq 1 ]; then local_first=0; else printf ',\n'; fi
    printf '    %s' "$entry"
  done
  printf '\n  ]\n'
  printf '}\n'
} > "$JSON"

echo
echo "log:  ${LOG#$REPO/}"
echo "json: ${JSON#$REPO/}"
echo "overall exit code: ${overall}"
exit "$overall"
