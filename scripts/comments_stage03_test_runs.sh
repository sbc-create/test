#!/usr/bin/env bash
# COMMUNITY-COMMENTS-03 B11: two consecutive comments suite runs + ratings
# Stage06 regression. Records the real exit code of every run.
set -u

cd "$(dirname "$0")/.." || exit 2
OUT="artifacts/evidence/community-comments-03/08-tests"
mkdir -p "$OUT"
LOG="$OUT/TEST_RUNS.log"
: > "$LOG"

run() {
  local label="$1"
  shift
  echo "=== ${label} ===" >> "$LOG"
  echo "command: $*" >> "$LOG"
  "$@" >> "$LOG" 2>&1
  local code=$?
  echo "${label}_EXIT=${code}" >> "$LOG"
  echo >> "$LOG"
  return $code
}

run COMMENTS_RUN_1 python3 -m pytest tests/unit/community/ -k comment -q
R1=$?
run COMMENTS_RUN_2 python3 -m pytest tests/unit/community/ -k comment -q
R2=$?
run RATINGS_STAGE06 python3 -m pytest \
  tests/unit/community/test_community_ratings_stage06.py \
  tests/unit/community/test_community_ratings_stage6.py -q
R3=$?

echo "SUMMARY COMMENTS_RUN_1=${R1} COMMENTS_RUN_2=${R2} RATINGS_STAGE06=${R3}" >> "$LOG"
tail -30 "$LOG"
if [ "$R1" -eq 0 ] && [ "$R2" -eq 0 ] && [ "$R3" -eq 0 ]; then
  exit 0
fi
exit 1
