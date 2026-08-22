#!/usr/bin/env bash
# Production deploy. Требует production_authorized, точного совпадения build ID,
# backup, health check и автоматического rollback при провале.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

SITE=""; DOMAIN=""; HOST=""; BUILD=""; BRANCH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --site) SITE="$2"; shift 2;;
    --domain) DOMAIN="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    --build) BUILD="$2"; shift 2;;
    --branch) BRANCH="$2"; shift 2;;
    *) echo "unknown arg $1" >&2; exit 2;;
  esac
done
[[ -n "$SITE" && -n "$DOMAIN" && -n "$HOST" && -n "$BUILD" && -n "$BRANCH" ]] || {
  echo "usage: deploy.sh --site ID --domain D --host H --build B --branch BR" >&2; exit 2; }

authorize "deploy" "$SITE" "$DOMAIN" "$HOST"

python3 - "$SITE" "$BUILD" "$BRANCH" <<'PY'
import sys, yaml, pathlib
site, build, branch = sys.argv[1:4]
m = yaml.safe_load(pathlib.Path(f"inventory/authorization/{site}.authorization.yaml").read_text(encoding="utf-8"))
if m.get("authorized_build_id") != build:
    sys.exit(f"BLOCKED_AUTHORIZATION: build mismatch {m.get('authorized_build_id')} != {build}")
if m.get("authorized_branch") != branch:
    sys.exit(f"BLOCKED_AUTHORIZATION: branch mismatch {m.get('authorized_branch')} != {branch}")
print("deploy manifest match ok")
PY

echo "NOT_IMPLEMENTED: реальный deploy-транспорт предоставляет development-контур." >&2
exit 4
