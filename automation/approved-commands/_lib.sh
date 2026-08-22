#!/usr/bin/env bash
# Общая проверка авторизации для всех утверждённых обёрток.
# Ни одна обёртка не выполняет действие без точного совпадения manifest.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFEST_DIR="$REPO_ROOT/inventory/authorization"

die() { echo "BLOCKED_AUTHORIZATION: $*" >&2; exit 3; }

# authorize <action> <site_id> <domain> [host]
authorize() {
  local action="$1" site="$2" domain="$3" host="${4:-}"
  local manifest="$MANIFEST_DIR/${site}.authorization.yaml"

  [[ -f "$manifest" ]] || die "нет manifest для site=$site"

  python3 - "$manifest" "$action" "$site" "$domain" "$host" <<'PY'
import sys, datetime, yaml
manifest_path, action, site, domain, host = sys.argv[1:6]
with open(manifest_path, encoding="utf-8") as fh:
    m = yaml.safe_load(fh)

def fail(msg):
    print(f"BLOCKED_AUTHORIZATION: {msg}", file=sys.stderr)
    sys.exit(3)

if m.get("site_id") != site:
    fail(f"site mismatch: manifest={m.get('site_id')} requested={site}")
if m.get("domain") != domain:
    fail(f"domain mismatch: manifest={m.get('domain')} requested={domain}")
if host and host not in (m.get("hosts") or []):
    fail(f"host {host} не в списке разрешённых")

allowed = m.get("allowed_actions") or []
if action not in allowed:
    fail(f"action '{action}' не разрешён (разрешены: {allowed})")

expires = m.get("authorization_expires_at")
if not expires:
    fail("нет authorization_expires_at")
if datetime.date.fromisoformat(str(expires)) < datetime.date.today():
    fail(f"авторизация истекла {expires}")

if m.get("environment") == "production" and not m.get("production_authorized"):
    fail("production_authorized != true")

if action in (m.get("requires_backup_for") or []) and not m.get("backup_verified"):
    fail(f"action '{action}' требует проверенного backup")

print(f"AUTHORIZED action={action} site={site} domain={domain} expires={expires}")
PY
}
