#!/usr/bin/env bash
# Undo Stage 1 on animedia.icu, reading the state the apply script recorded.
#
# Every step is guarded, so running this twice is a no-op rather than an error.
# The apply script calls it automatically the moment live verification fails;
# an operator can also run it by hand at any time.
#
# Four levels, cheapest first. Without arguments it runs 1 and 2 — stop
# comments, leave the site release alone. `--full` also restores the previous
# release, the template manifest, the vhost and removes the gateway.
#
#   1. kill switch: comments refuse immediately, the page is untouched
#   2. unmount: the drop-in goes, the title page loses its container
#   3. release and manifest: both return to what apply recorded
#   4. remove: gateway unit and nginx include go away
#
# THE DATABASE IS NEVER DELETED, at any level. Comments written during the
# pilot are the owner's. A rollback that destroys them cannot be undone, and
# nothing here needs them gone. The path is printed at the end so it is a
# stated fact rather than an assumption.
#
# It never touches animedia.space, zona, lords, yummy, the ratings gateway,
# DNS, TLS, robots, canonical or sitemap.
set -euo pipefail

REPO=/home/claude/wt-community-comments-platform-01
STATE_DIR=/srv/site-factory/var/comments
STATE_FILE="$STATE_DIR/stage1-state.json"
BACKUP_DIR="$STATE_DIR/backups"
DB="$STATE_DIR/comments.sqlite"
VHOST=/etc/nginx/lords/animedia-01.conf
SNIPPET=/etc/nginx/snippets/animedia-comments.conf
UNIT=/etc/systemd/system/comments-gateway.service
SITE_UNIT=nova-animedia-01.service
MANIFEST=/srv/lords/.frontend/template-manifest-animedia-01.json
CHECK="$REPO/automation/host/comments_endpoint_check.py"
HYGIENE="$REPO/automation/host/nginx_backup_hygiene.sh"
RESOLVE="animedia.icu:443:127.0.0.1"
SITE=https://animedia.icu

FULL=0
[ "${1:-}" = "--full" ] && FULL=1

say()  { printf '\n== %s\n' "$*"; }
note() { printf '   %s\n' "$*"; }
die()  { printf '\nREFUSED: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "must run as root"

# Same rules as apply: a backup never lives inside a directory nginx globs.
# Rollback enforces it too, so a stray cannot survive by being created during a
# failed apply and then left behind by the rollback that cleans up after it.
[ -f "$HYGIENE" ] || die "nginx backup hygiene rules missing: $HYGIENE"
# shellcheck source=automation/host/nginx_backup_hygiene.sh
. "$HYGIENE"

if [ ! -f "$STATE_FILE" ]; then
  # Nothing was recorded, so nothing was applied by this harness. Removing what
  # is not there is still safe, but restoring a release is not: without the
  # recorded previous target there is nothing to restore it to.
  note "no state file at $STATE_FILE — treating this as 'nothing to roll back'"
  note "database, if any, is at $DB and is left alone"
  exit 0
fi

read_state() {
  python3 -c "import json;print(json.load(open('$STATE_FILE')).get('$1',''))" 2>/dev/null || true
}

LINK=$(read_state symlink_path)
LINK_BEFORE=$(read_state symlink_before)
BUILD_BEFORE=$(read_state build_id_before)
PID_BEFORE=$(read_state pid_before)
MANIFEST_BACKUP=$(read_state manifest_backup)
VHOST_BACKUP=$(read_state vhost_backup)

note "recorded previous release : $LINK_BEFORE"
note "recorded previous build   : $BUILD_BEFORE"
note "recorded previous pid     : $PID_BEFORE"

# --- level 1: stop comments now --------------------------------------------

say "level 1 — kill switch"
if systemctl list-unit-files comments-gateway.service >/dev/null 2>&1 \
   && systemctl is-active --quiet comments-gateway.service; then
  install -d -m 0755 /etc/systemd/system/comments-gateway.service.d
  cat > /etc/systemd/system/comments-gateway.service.d/killswitch.conf <<'DROPIN'
[Service]
Environment=COMMENTS_KILL_SWITCH=1
DROPIN
  systemctl daemon-reload
  systemctl restart comments-gateway.service || true
  note "comments now refuse every request; the site is untouched"
else
  note "gateway is not running — nothing to switch off"
fi

# --- level 2: unmount the widget -------------------------------------------

say "level 2 — unmount from the title page"
if [ -f /etc/systemd/system/"$SITE_UNIT".d/comments.conf ]; then
  rm -f /etc/systemd/system/"$SITE_UNIT".d/comments.conf
  rmdir --ignore-fail-on-non-empty /etc/systemd/system/"$SITE_UNIT".d 2>/dev/null || true
  systemctl daemon-reload
  systemctl restart "$SITE_UNIT" || true
  sleep 3
  note "ANIMEDIA_COMMENTS_MOUNT removed; the release is inert again"
else
  note "no mount drop-in present — already unmounted"
fi

if [ "$FULL" -eq 0 ]; then
  say "stopped after level 2"
  note "Comments are off and the page output is unmodified."
  note "The site may still be running the Stage 1 release, which is inert"
  note "without the mount switch. Run with --full to restore the previous one."
  note "Database preserved at $DB"
  exit 0
fi

# --- level 3: previous release and manifest --------------------------------

say "level 3 — previous release and template manifest"
if [ -n "$LINK_BEFORE" ] && [ -L "$LINK" ]; then
  if [ "$(readlink "$LINK")" = "$LINK_BEFORE" ]; then
    note "symlink already at the recorded previous release"
  else
    ln -sfn "$LINK_BEFORE" "$LINK"
    note "symlink -> $(readlink "$LINK")"
  fi
else
  note "no previous symlink recorded or no symlink present — left alone"
fi

# The public build id lives in this file, not in the release directory. Leaving
# it behind would leave the site announcing a release it is no longer running.
if [ -n "$MANIFEST_BACKUP" ] && [ -f "$MANIFEST_BACKUP" ]; then
  cp -a "$MANIFEST_BACKUP" "$MANIFEST"
  note "template-manifest restored from $MANIFEST_BACKUP"
else
  note "no template-manifest backup recorded — left as is"
fi

systemctl restart "$SITE_UNIT" || true
sleep 3
BUILD_NOW=$(curl -sS -m 10 --resolve "$RESOLVE" -D - -o /dev/null "$SITE/" \
  | awk 'tolower($1)=="x-site-factory-build-id:"{print $2}' | tr -d '\r' || true)
note "build now: ${BUILD_NOW:-unknown} (recorded before: $BUILD_BEFORE)"
if [ -n "$BUILD_BEFORE" ] && [ "$BUILD_NOW" != "$BUILD_BEFORE" ]; then
  note "WARNING: build id does not match what was recorded"
fi

# --- level 4: remove the gateway and the nginx include ---------------------

say "level 4 — remove gateway and nginx include"
if systemctl list-unit-files comments-gateway.service >/dev/null 2>&1; then
  systemctl disable --now comments-gateway.service 2>/dev/null || true
fi
rm -f "$UNIT"
rm -rf /etc/systemd/system/comments-gateway.service.d
systemctl daemon-reload

if [ -n "$VHOST_BACKUP" ] && [ -f "$VHOST_BACKUP" ]; then
  # A backup that lives inside /etc/nginx is itself loaded by an include glob,
  # so restoring from one would mean the rollback depended on the defect it is
  # supposed to undo. Refuse rather than quietly use it: the include line can
  # still be removed by the sed branch below, which needs no backup at all.
  case "$(readlink -f "$VHOST_BACKUP")" in
    /etc/nginx/*)
      note "REFUSED: recorded vhost backup is inside /etc/nginx ($VHOST_BACKUP)"
      note "falling back to removing the include line in place"
      sed -i '/animedia-comments.conf/d' "$VHOST"
      note "include line removed without using the misplaced backup"
      ;;
    *)
      cp -a "$VHOST_BACKUP" "$VHOST"
      note "vhost restored from $VHOST_BACKUP (kept outside every nginx include glob)"
      ;;
  esac
elif grep -q 'animedia-comments.conf' "$VHOST" 2>/dev/null; then
  sed -i '/animedia-comments.conf/d' "$VHOST"
  note "include line removed (no backup was recorded)"
else
  note "vhost has no comments include — already clean"
fi
rm -f "$SNIPPET"

# Leave nginx's include directories the way they should have been all along.
# Quarantined files are moved into $BACKUP_DIR, never deleted.
while IFS= read -r moved; do
  [ -n "$moved" ] || continue
  note "quarantined into $moved (preserved, not deleted)"
done <<EOF
$(nginx_quarantine)
EOF
if ! LEFT=$(nginx_assert_clean); then
  note "WARNING: a harness file remains inside an nginx include directory: $LEFT"
fi

nginx -t && systemctl reload nginx

# --- verification ----------------------------------------------------------

say "verification"
for path in / /catalog/ /title/master-lda-i-plameni-2/ /definitely-not-real-9d2f/; do
  headers=$(curl -sS -m 10 --resolve "$RESOLVE" -D - -o /dev/null "$SITE$path" || true)
  code=$(printf '%s' "$headers" | head -1 | awk '{print $2}')
  noindex=no
  printf '%s' "$headers" | grep -qi '^X-Robots-Tag:.*noindex' && noindex=yes
  note "$path -> $code noindex=$noindex"
done

# A 308 here is the site's own trailing-slash rule and is fine; what must hold
# is that no hop was answered by the comments gateway and the chain ends
# closed. Comparing a single status code cannot tell those apart, which is how
# the first attempt reported a problem that was not there.
if python3 "$CHECK" "$SITE/api/comments/v1/healthz" --resolve "$RESOLVE" \
     --expect no-gateway | grep -q '"ok": true'; then
  note "no comments gateway on /api/comments/ — rollback confirmed"
else
  note "WARNING: something still answers on /api/comments/"
  python3 "$CHECK" "$SITE/api/comments/v1/healthz" --resolve "$RESOLVE" --expect no-gateway || true
fi

note "animedia-02 -> $(readlink /srv/lords/.frontend/sites/animedia-02/current)"

say "ROLLED_BACK"
note "Database preserved at $DB — no rollback level deletes it."
note "Backups kept in $BACKUP_DIR"
