#!/usr/bin/env bash
# Stage 1 of the shared comments module on animedia.icu — the whole root part,
# as one reviewable script.
#
# WHAT IT DOES, in order, stopping at the first failure:
#
#   1. refuses to run unless it is root and the preconditions hold
#   2. records the state it is about to change, so rollback has something exact
#   3. creates per-tenant keys if they are absent (never overwrites existing ones)
#   4. installs the comments gateway unit and starts it
#   5. installs the nginx snippet and includes it in the animedia.icu vhost only
#   6. repoints animedia-01 at the prepared release and restarts it
#   7. verifies: ordinary visitor sees no comments, noindex intact, no 5xx
#
# WHAT IT REFUSES TO DO:
#
#   * touch animedia.space, zona, lords or yummy
#   * touch the ratings gateway, its unit, its snippet or its database
#   * change robots, canonical, sitemap, TLS or DNS
#   * proceed if animedia.icu is indexable
#
# Rollback: animedia-comments-stage1-rollback.sh, which reads the state file
# this script writes.
set -euo pipefail

STATE_DIR=/srv/site-factory/var/comments
STATE_FILE="$STATE_DIR/stage1-state.json"
KEY_DIR=/etc/comments-platform/keys
REPO=/home/claude/wt-community-comments-platform-01
RELEASE_ID="20260922T071857Z-e84ee6e-animedia-comments-stage1"
RELEASE_DIR="/srv/lords/.frontend/releases/$RELEASE_ID"
LINK=/srv/lords/.frontend/sites/animedia-01/current
UNIT=/etc/systemd/system/comments-gateway.service
SNIPPET=/etc/nginx/snippets/animedia-comments.conf
VHOST=/etc/nginx/lords/animedia-01.conf
SITE_UNIT=nova-animedia-01.service
ORIGIN=http://127.0.0.1:9121
HOSTHDR="Host: animedia.icu"

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nREFUSED: %s\n' "$*" >&2; exit 1; }

# --- 1. preconditions ------------------------------------------------------

[ "$(id -u)" -eq 0 ] || die "must run as root"
[ -d "$RELEASE_DIR" ] || die "prepared release is missing: $RELEASE_DIR"
[ -f "$RELEASE_DIR/RELEASE.json" ] || die "release has no manifest"
[ -f "$REPO/automation/host/systemd/comments-gateway.service" ] || die "unit source missing"
[ -f "$REPO/automation/host/nginx/animedia-comments.conf" ] || die "snippet source missing"
[ -L "$LINK" ] || die "expected a symlink at $LINK"

say "indexability gate"
for path in / /catalog/ /title/master-lda-i-plameni-2/ /nope-xyz/; do
  headers=$(curl -sS -m 10 -D - -o /dev/null -H "$HOSTHDR" "$ORIGIN$path" || true)
  echo "$headers" | grep -qi '^X-Robots-Tag:.*noindex' \
    || die "$path is not noindex — refusing to proceed (BLOCKED_INDEXABILITY_GATE)"
done
echo "all probed routes are noindex"

say "second-domain guard"
[ "$(readlink -f /srv/lords/.frontend/sites/animedia-02/current)" != "$RELEASE_DIR" ] \
  || die "animedia-02 already points at the Stage 1 release; it must not"

# --- 2. record what is about to change -------------------------------------

install -d -m 0755 "$STATE_DIR"
PID_BEFORE=$(systemctl show -p MainPID --value "$SITE_UNIT" || echo 0)
LINK_BEFORE=$(readlink "$LINK")
BUILD_BEFORE=$(curl -sS -m 10 -D - -o /dev/null -H "$HOSTHDR" "$ORIGIN/" \
  | awk 'tolower($1)=="x-site-factory-build-id:"{print $2}' | tr -d '\r')

cat > "$STATE_FILE" <<JSON
{
  "recorded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "site_unit": "$SITE_UNIT",
  "pid_before": "$PID_BEFORE",
  "build_id_before": "$BUILD_BEFORE",
  "symlink_before": "$LINK_BEFORE",
  "symlink_path": "$LINK",
  "release_applied": "$RELEASE_ID",
  "unit_installed": "$UNIT",
  "snippet_installed": "$SNIPPET",
  "vhost_touched": "$VHOST"
}
JSON
echo "rollback state written to $STATE_FILE"
echo "  pid before      : $PID_BEFORE"
echo "  build id before : $BUILD_BEFORE"
echo "  symlink before  : $LINK_BEFORE"

# --- 3. keys ---------------------------------------------------------------

say "per-tenant keys"
install -d -m 0700 "$KEY_DIR"
for slot in animedia.subject animedia.network animedia.cohort; do
  if [ -s "$KEY_DIR/$slot" ]; then
    echo "  $slot already exists — left alone"
  else
    openssl rand -hex 32 > "$KEY_DIR/$slot"
    chmod 0600 "$KEY_DIR/$slot"
    echo "  $slot created"
  fi
done

# --- 4. comments gateway ---------------------------------------------------

say "comments gateway"
install -d -m 0750 -o lords -g lords "$STATE_DIR"
install -m 0644 "$REPO/automation/host/systemd/comments-gateway.service" "$UNIT"
systemctl daemon-reload
systemctl enable --now comments-gateway.service
sleep 2
systemctl is-active --quiet comments-gateway.service \
  || die "comments gateway did not start; journalctl -u comments-gateway -n 50"
curl -sS -m 10 -H "$HOSTHDR" http://127.0.0.1:9150/api/comments/v1/healthz \
  | grep -q '"status": "ok"' || die "gateway health check failed"
echo "gateway is up on 127.0.0.1:9150"

# --- 5. nginx --------------------------------------------------------------

say "nginx"
install -m 0644 "$REPO/automation/host/nginx/animedia-comments.conf" "$SNIPPET"
if grep -q 'animedia-comments.conf' "$VHOST"; then
  echo "  vhost already includes the snippet"
else
  cp -a "$VHOST" "$VHOST.before-comments-stage1"
  # Only inside the 443 server block of animedia.icu. One include, one vhost.
  awk '
    /listen 443 ssl;/ { in443=1 }
    in443 && /location \/ \{/ && !done {
      print "    include /etc/nginx/snippets/animedia-comments.conf;"
      print ""
      done=1
    }
    { print }
  ' "$VHOST.before-comments-stage1" > "$VHOST"
  echo "  include added (backup at $VHOST.before-comments-stage1)"
fi
nginx -t || die "nginx config test failed — restore $VHOST.before-comments-stage1"
systemctl reload nginx

# --- 6. the site release ---------------------------------------------------

say "animedia-01 release"
ln -sfn "../../releases/$RELEASE_ID" "$LINK"
echo "  symlink -> $(readlink "$LINK")"
echo "  animedia-02 stays at: $(readlink /srv/lords/.frontend/sites/animedia-02/current)"

# The mount switch. Without it the release is inert and the page is unchanged.
install -d -m 0755 /etc/systemd/system/"$SITE_UNIT".d
cat > /etc/systemd/system/"$SITE_UNIT".d/comments.conf <<'DROPIN'
[Service]
Environment=ANIMEDIA_COMMENTS_MOUNT=1
DROPIN
systemctl daemon-reload
systemctl restart "$SITE_UNIT"
sleep 3
systemctl is-active --quiet "$SITE_UNIT" || die "$SITE_UNIT did not come back"

PID_AFTER=$(systemctl show -p MainPID --value "$SITE_UNIT")
BUILD_AFTER=$(curl -sS -m 10 -D - -o /dev/null -H "$HOSTHDR" "$ORIGIN/" \
  | awk 'tolower($1)=="x-site-factory-build-id:"{print $2}' | tr -d '\r')
echo "  pid $PID_BEFORE -> $PID_AFTER"
echo "  build $BUILD_BEFORE -> $BUILD_AFTER"

# --- 7. verify -------------------------------------------------------------

say "verification"
fail=0

for path in / /catalog/ /title/master-lda-i-plameni-2/ /nope-xyz/; do
  headers=$(curl -sS -m 10 -D - -o /dev/null -H "$HOSTHDR" "$ORIGIN$path" || true)
  code=$(printf '%s' "$headers" | head -1 | awk '{print $2}')
  if printf '%s' "$headers" | grep -qi '^X-Robots-Tag:.*noindex'; then
    echo "  noindex ok   $path ($code)"
  else
    echo "  NOINDEX LOST $path ($code)"; fail=1
  fi
  case "$code" in 5*) echo "  5xx on $path"; fail=1;; esac
done

# An ordinary visitor: the mount point may be in the HTML, but the API must
# refuse and no comment may be readable.
visitor=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' -H "$HOSTHDR" \
  "$ORIGIN/api/comments/v1/threads?resource_type=title&canonical_content_id=01a0b507-3280-7b2a-8af4-674dd73cff72" || true)
if [ "$visitor" = "503" ]; then
  echo "  ordinary visitor refused (503) — correct"
else
  echo "  ORDINARY VISITOR GOT $visitor — expected 503"; fail=1
fi

# animedia.space must be untouched.
space=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' -H 'Host: animedia.space' \
  http://127.0.0.1:9122/ || true)
echo "  animedia.space still answers $space on its own port (unchanged release)"

if [ "$fail" -ne 0 ]; then
  echo
  echo "VERIFICATION FAILED — run animedia-comments-stage1-rollback.sh"
  exit 2
fi

say "done"
cat <<SUMMARY
PID_BEFORE=$PID_BEFORE
PID_AFTER=$PID_AFTER
BUILD_BEFORE=$BUILD_BEFORE
BUILD_AFTER=$BUILD_AFTER
STATE_FILE=$STATE_FILE

Next: issue yourself an owner cohort cookie with
  $REPO/bin/comments-owner-cookie animedia.icu
and follow docs/comments_platform/OWNER_TEST.md
SUMMARY
