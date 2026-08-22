#!/bin/bash
# SessionStart hook: prepare the environment so an SEO session can run the
# schema validator, linter, and tests immediately, without setup steps.
#
# Runs synchronously so nothing races against a half-installed venv.
# Idempotent: re-running reuses the existing virtualenv.
set -euo pipefail

# Only provision automatically in Claude Code on the web. Set
# SEO_SESSION_FORCE_SETUP=1 to run it locally on purpose.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ] && [ "${SEO_SESSION_FORCE_SETUP:-}" != "1" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

VENV=".venv"

if [ ! -x "${VENV}/bin/python" ]; then
  echo "Creating virtualenv at ${VENV}"
  python3 -m venv "${VENV}"
fi

echo "Installing pinned dependencies"
"${VENV}/bin/pip" install --quiet --upgrade pip
"${VENV}/bin/pip" install --quiet -r requirements.txt
# PyYAML backs the workflow-parsing stage of scripts/verify.sh.
"${VENV}/bin/pip" install --quiet pyyaml

# Persist for the rest of the session so `python`, `pytest` and `ruff` resolve
# to the virtualenv without every command needing the .venv/bin prefix.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$(pwd)/${VENV}\""
    echo "export PATH=\"$(pwd)/${VENV}/bin:\$PATH\""
  } >> "${CLAUDE_ENV_FILE}"
fi

echo "Environment ready. Run ./scripts/verify.sh to check the repository."
