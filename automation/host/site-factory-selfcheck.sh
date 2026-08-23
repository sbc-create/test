#!/usr/bin/env bash
# Scheduled self-check of the factory checkout on this host.
#
# Read-only by design: it answers "is this checkout still the one that was
# verified?" and nothing else. It never deploys, never touches a target, and
# never writes into the repository.
set -uo pipefail

REPO="${FACTORY_REPO:-/srv/site-factory/repo}"
LOG_DIR="${SITE_FACTORY_LOG_DIR:-/var/log/site-factory}"
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

cd "$REPO" || { echo "SELFCHECK FAILED: нет каталога $REPO" >&2; exit 1; }
mkdir -p "$LOG_DIR" 2>/dev/null || true

FAILED=0
stage() {
  local name="$1"; shift
  local out code
  out="$("$@" 2>&1)"; code=$?
  if [ $code -eq 0 ]; then
    echo "PASS: $name"
  else
    echo "FAIL: $name (exit $code)"
    printf '%s\n' "$out" | tail -20
    FAILED=$((FAILED + 1))
  fi
}

echo "=== site-factory selfcheck $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "commit: $(git rev-parse HEAD 2>/dev/null || echo unknown) ($(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown))"

stage "knowledge-freeze"  "$PY" -m factory knowledge verify
stage "claude-config"     "$PY" -m factory selfcheck
stage "schemas"           "$PY" scripts/validate_schemas.py
stage "registries"        "$PY" scripts/validate_registries.py
stage "guardrails"        "$PY" -m pytest tests/operator/test_guardrails.py tests/operator/test_hookguard.py -q
stage "permission-matrix" "$PY" -m pytest tests/unit/test_permission_matrix.py -q
stage "repo-hygiene"      "$PY" -m pytest tests/unit/test_repo_hygiene.py -q

# A dirty checkout on the control host means something changed outside git.
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  echo "FAIL: рабочее дерево изменено вне git"
  git status --short | head -20
  FAILED=$((FAILED + 1))
else
  echo "PASS: рабочее дерево чистое"
fi

echo "--- итог: провалов $FAILED ---"
exit "$FAILED"
