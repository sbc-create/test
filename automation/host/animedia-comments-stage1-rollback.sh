#!/usr/bin/env bash
# Undo Stage 1 on animedia.icu, reading the state the apply script recorded.
#
# Four levels, cheapest first. By default it runs level 1 and 2 — the ones that
# stop comments without moving the site release — because that is what an
# incident usually needs. `--full` also restores the previous release and
# removes the gateway.
#
#   1. kill switch: comments refuse immediately, the page is untouched
#   2. unmount: the drop-in goes, the title page loses its container
#   3. release: the symlink returns to the recorded previous release
#   4. remove: gateway unit and nginx include go away
#
# It does not drop the comments database. Data written during the pilot is the
# owner's; a rollback that destroys it cannot be undone, and nothing here needs
# it gone.
#
# It never touches animedia.space, the ratings gateway, DNS, TLS or robots.
set -euo pipefail

STATE_FILE=/srv/site-factory/var/comments/stage1-state.json
VHOST=/etc/nginx/lords/animedia-01.conf
SNIPPET=/etc/nginx/snippets/animedia-comments.conf
UNIT=/etc/systemd/system/comments-gateway.service
SITE_UNIT=nova-animedia-01.service
HOSTHDR="Host: animedia.icu"
ORIGIN=http://127.0.0.1:9121

FULL=0
[ "${1:-}" = "--full" ] && FULL=1

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nREFUSED: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "must run as root"
[ -f "$STATE_FILE" ] || die "no state file at $STATE_FILE — nothing recorded to roll back to"

read_state() { python3 -c "import json,sys;print(json.load(open('$STATE_FILE')).get('$1',''))"; }

LINK=$(read_state symlink_path)
LINK_BEFORE=$(read_state symlink_before)
BUILD_BEFORE=$(read_state build_id_before)
PID_BEFORE=$(read_state pid_before)

echo "recorded previous release : $LINK_BEFORE"
echo "recorded previous build   : $BUILD_BEFORE"
echo "recorded previous pid     : $PID_BEFORE"

# --- level 1: stop comments now --------------------------------------------

say "level 1 — kill switch"
if systemctl is-active --quiet comments-gateway.service; then
  install -d -m 0755 /etc/systemd/system/comments-gateway.service.d
  cat > /etc/systemd/system/comments-gateway.service.d/killswitch.conf <<'DROPIN'
[Service]
Environment=COMMENTS_KILL_SWITCH=1
DROPIN
  systemctl daemon-reload
  systemctl restart comments-gateway.service
  echo "  comments now refuse every request (503); the site is untouched"
else
  echo "  gateway is not running — nothing to switch off"
fi

# --- level 2: unmount the widget -------------------------------------------

say "level 2 — unmount from the title page"
if [ -f /etc/systemd/system/"$SITE_UNIT".d/comments.conf ]; then
  rm -f /etc/systemd/system/"$SITE_UNIT".d/comments.conf
  rmdir --ignore-fail-on-non-empty /etc/systemd/system/"$SITE_UNIT".d
  systemctl daemon-reload
  systemctl restart "$SITE_UNIT"
  sleep 3
  echo "  ANIMEDIA_COMMENTS_MOUNT removed; the release is inert again"
else
  echo "  no mount drop-in present"
fi

if [ "$FULL" -eq 0 ]; then
  say "stopped after level 2"
  echo "Comments are off and the page is back to its unmodified output."
  echo "The site is still running the Stage 1 release, which is inert without"
  echo "the mount switch. Run with --full to restore the previous release and"
  echo "remove the gateway."
  exit 0
fi

# --- level 3: previous release ---------------------------------------------

say "level 3 — previous release"
[ -n "$LINK_BEFORE" ] || die "no previous symlink recorded"
ln -sfn "$LINK_BEFORE" "$LINK"
systemctl restart "$SITE_UNIT"
sleep 3
BUILD_NOW=$(curl -sS -m 10 -D - -o /dev/null -H "$HOSTHDR" "$ORIGIN/" \
  | awk 'tolower($1)=="x-site-factory-build-id:"{print $2}' | tr -d '\r')
echo "  symlink -> $(readlink "$LINK")"
echo "  build now: $BUILD_NOW (recorded before: $BUILD_BEFORE)"
[ "$BUILD_NOW" = "$BUILD_BEFORE" ] || echo "  WARNING: build id does not match what was recorded"

# --- level 4: remove the gateway and the nginx include ---------------------

say "level 4 — remove gateway and nginx include"
systemctl disable --now comments-gateway.service 2>/dev/null || true
rm -f "$UNIT"
rm -rf /etc/systemd/system/comments-gateway.service.d
systemctl daemon-reload

if [ -f "$VHOST.before-comments-stage1" ]; then
  cp -a "$VHOST.before-comments-stage1" "$VHOST"
  echo "  vhost restored from backup"
else
  sed -i '/animedia-comments.conf/d' "$VHOST"
  echo "  include line removed (no backup was present)"
fi
rm -f "$SNIPPET"
nginx -t && systemctl reload nginx

say "verification"
for path in / /catalog/ /title/master-lda-i-plameni-2/ /nope-xyz/; do
  headers=$(curl -sS -m 10 -D - -o /dev/null -H "$HOSTHDR" "$ORIGIN$path" || true)
  code=$(printf '%s' "$headers" | head -1 | awk '{print $2}')
  noindex=no
  printf '%s' "$headers" | grep -qi '^X-Robots-Tag:.*noindex' && noindex=yes
  echo "  $path -> $code noindex=$noindex"
done
api=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' -H "$HOSTHDR" \
  "$ORIGIN/api/comments/v1/healthz" || true)
echo "  /api/comments/ now answers $api (404 expected once the include is gone)"

say "ROLLED_BACK"
echo "The comments database at /srv/site-factory/var/comments was left in place."
