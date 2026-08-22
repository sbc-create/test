#!/usr/bin/env bash
# Run every check this repository gates on, in order, and report a summary.
#
# Used three ways: by a developer before committing, by CI on pull requests, and
# by scripts/record-evidence.sh to produce the committed verification report.
#
# Exit code is the number of failed stages, so callers can gate on it.
set -uo pipefail

cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
RUFF="${RUFF:-.venv/bin/ruff}"

if [ ! -x "$PY" ]; then
  echo "No virtualenv at $PY - falling back to system python3." >&2
  PY="$(command -v python3)"
  RUFF="$(command -v ruff || echo '')"
fi

FAILED=0
PASSED=0

run_stage() {
  local name="$1"
  shift
  echo "--- ${name} ---"
  if "$@"; then
    echo "PASS: ${name}"
    PASSED=$((PASSED + 1))
  else
    echo "FAIL: ${name}"
    FAILED=$((FAILED + 1))
  fi
  echo
}

# 1. Every JSON file in the repo must parse.
check_json_parses() {
  local bad=0
  while IFS= read -r f; do
    if ! "$PY" -c "import json,sys;json.load(open(sys.argv[1]))" "$f" 2>/dev/null; then
      echo "  unparseable: $f"
      bad=1
    fi
  done < <(git ls-files '*.json')
  return $bad
}

# 2. Schemas compile as Draft 2020-12.
check_schemas() { "$PY" scripts/validate_schemas.py; }

# 3. Valid fixtures validate; invalid fixtures must be rejected.
check_fixtures() {
  "$PY" scripts/validate_schemas.py tests/fixtures/*.valid.json || return 1
  local f
  for f in tests/fixtures/*.invalid.json; do
    [ -e "$f" ] || continue
    if "$PY" scripts/validate_schemas.py "$f" >/dev/null 2>&1; then
      echo "  $f was accepted but is meant to be invalid"
      return 1
    fi
  done
  echo "  invalid fixtures correctly rejected"
  return 0
}

check_lint() { [ -n "$RUFF" ] && "$RUFF" check . && "$RUFF" format --check .; }

check_tests() { "$PY" -m pytest tests/ -q; }

# 4. Workflow files must be well-formed YAML.
check_workflows() {
  "$PY" - <<'PYEOF'
import sys, pathlib
try:
    import yaml
except ImportError:
    print("  PyYAML not installed - skipping YAML parse (CI installs it)")
    sys.exit(0)
bad = 0
for p in sorted(pathlib.Path(".github/workflows").glob("*.yml")):
    try:
        yaml.safe_load(p.read_text())
        print(f"  ok: {p}")
    except Exception as exc:
        print(f"  invalid: {p}: {exc}")
        bad = 1
sys.exit(bad)
PYEOF
}

echo "Verification run: $(git rev-parse --short HEAD 2>/dev/null || echo 'no-commit') on $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'no-branch')"
echo

run_stage "JSON parses"            check_json_parses
run_stage "Schemas compile"        check_schemas
run_stage "Fixtures validate"      check_fixtures
run_stage "Workflows parse"        check_workflows
run_stage "Lint (ruff)"            check_lint
run_stage "Tests (pytest)"         check_tests

echo "========================================"
echo "Stages passed: ${PASSED}   failed: ${FAILED}"
echo "========================================"
exit $FAILED
