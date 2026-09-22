#!/usr/bin/env bash
# Stage 1 of the shared comments module on animedia.icu — the whole root part.
#
# Rewritten after the first attempt failed. Three things went wrong, and each
# is fixed here rather than worked around:
#
#   * The visitor check probed http://127.0.0.1:9121 — the Animedia site
#     runtime. The comments API is an nginx `location`; a request that never
#     passes through nginx cannot reach it. The probe therefore saw the site's
#     own trailing-slash 308 and called it a failure. Endpoint checks now go
#     through nginx, with --resolve, and are judged by comments_endpoint_check.py
#     which follows the chain and looks at where it ends.
#
#   * The build-id check compared a header that comes from
#     template-manifest-animedia-01.json, a file the release symlink does not
#     touch. It could never change. The manifest is now updated as part of the
#     deploy (and restored on rollback), and the release is verified by
#     symlink, process cmdline, MainPID and artifact sha256 as well.
#
#   * Verification failed after four mutations and left all four in place. A
#     trap now rolls back automatically as soon as anything has been changed.
#
# It refuses to touch animedia.space, zona, lords, yummy, the ratings gateway,
# robots, canonical, sitemap, TLS or DNS. Foreign nginx warnings are recorded,
# never fixed.
set -euo pipefail

REPO=/home/claude/wt-community-comments-platform-01
STATE_DIR=/srv/site-factory/var/comments
STATE_FILE="$STATE_DIR/stage1-state.json"
BACKUP_DIR="$STATE_DIR/backups"
EVIDENCE="$STATE_DIR/stage1-apply-evidence.txt"
KEY_DIR=/etc/comments-platform/keys
RELEASE_ID="20260922T071857Z-e84ee6e-animedia-comments-stage1"
RELEASE_DIR="/srv/lords/.frontend/releases/$RELEASE_ID"
LINK=/srv/lords/.frontend/sites/animedia-01/current
MANIFEST=/srv/lords/.frontend/template-manifest-animedia-01.json
UNIT=/etc/systemd/system/comments-gateway.service
SNIPPET=/etc/nginx/snippets/animedia-comments.conf
VHOST=/etc/nginx/lords/animedia-01.conf
SITE_UNIT=nova-animedia-01.service
CHECK="$REPO/automation/host/comments_endpoint_check.py"
ROLLBACK="$REPO/automation/host/animedia-comments-stage1-rollback.sh"

# Endpoint probes go through nginx on this host, with the real SNI and Host.
RESOLVE="animedia.icu:443:127.0.0.1"
SITE=https://animedia.icu
CONTENT_ID=01a0b507-3280-7b2a-8af4-674dd73cff72

# Set the moment anything on the system has been changed. The trap reads it.
MUTATED=0
SUCCEEDED=0

say()  { printf '\n== %s\n' "$*" | tee -a "$EVIDENCE"; }
note() { printf '   %s\n' "$*" | tee -a "$EVIDENCE"; }
die()  { printf '\nREFUSED: %s\n' "$*" >&2; exit 1; }

on_exit() {
  local status=$?
  if [ "$SUCCEEDED" -eq 1 ]; then
    return
  fi
  if [ "$MUTATED" -eq 0 ]; then
    printf '\nFailed before any change was made. Nothing to roll back.\n' >&2
    exit "$status"
  fi
  printf '\n!! live verification failed after %d mutation(s) — rolling back automatically\n' \
    "$MUTATED" >&2
  if bash "$ROLLBACK" --full >>"$EVIDENCE" 2>&1; then
    printf 'AUTOMATIC ROLLBACK COMPLETED — see %s\n' "$EVIDENCE" >&2
    printf 'VERDICT=ROLLED_BACK\n' >&2
  else
    printf 'AUTOMATIC ROLLBACK ITSELF FAILED — see %s\n' "$EVIDENCE" >&2
    printf 'VERDICT=ROLLBACK_FAILED\n' >&2
  fi
  exit "${status:-1}"
}
trap on_exit EXIT

# --- 0. preconditions, before anything is touched --------------------------
#
# The root check is first, ahead of even creating a directory: running this as
# a non-root user produced two `install: Operation not permitted` lines before
# the refusal, which reads like a partial failure when it is not one.

[ "$(id -u)" -eq 0 ] || die "must run as root"

install -d -m 0755 "$STATE_DIR" "$BACKUP_DIR"
: > "$EVIDENCE"
[ -d "$RELEASE_DIR" ] || die "prepared release is missing: $RELEASE_DIR"
[ -f "$RELEASE_DIR/RELEASE.json" ] || die "release has no manifest"
[ -f "$CHECK" ] || die "endpoint checker missing: $CHECK"
[ -f "$ROLLBACK" ] || die "rollback script missing — refusing to mutate without it"
[ -L "$LINK" ] || die "expected a symlink at $LINK"
[ -f "$MANIFEST" ] || die "template manifest missing: $MANIFEST"

say "file descriptors and inotify (diagnosed before any mutation)"
note "fs.file-nr            : $(cat /proc/sys/fs/file-nr)"
note "fs.file-max           : $(cat /proc/sys/fs/file-max)"
note "inotify instances max : $(cat /proc/sys/fs/inotify/max_user_instances)"
note "inotify watches max   : $(cat /proc/sys/fs/inotify/max_user_watches)"
note "root RLIMIT_NOFILE    : $(ulimit -n)"
INST_MAX=$(cat /proc/sys/fs/inotify/max_user_instances)
if [ "$INST_MAX" -lt 256 ]; then
  note "WARNING: max_user_instances=$INST_MAX is the kernel default and is what"
  note "         produced 'Failed to allocate directory watch: Too many open files'."
  note "         This deploy proceeds, but systemd may log it again. The owner"
  note "         command to raise it is in the report; it is deliberately not"
  note "         applied here."
fi

say "indexability gate"
for path in / /catalog/ /title/master-lda-i-plameni-2/ /definitely-not-real-9d2f/; do
  headers=$(curl -sS -m 10 --resolve "$RESOLVE" -D - -o /dev/null "$SITE$path" || true)
  printf '%s' "$headers" | grep -qi '^X-Robots-Tag:.*noindex' \
    || die "$path is not noindex — BLOCKED_INDEXABILITY_GATE"
done
note "all probed routes are noindex, nofollow"

say "second-domain guard"
[ "$(readlink -f /srv/lords/.frontend/sites/animedia-02/current)" != "$RELEASE_DIR" ] \
  || die "animedia-02 already points at the Stage 1 release; it must not"
note "animedia-02 -> $(readlink /srv/lords/.frontend/sites/animedia-02/current)"

say "foreign nginx warnings (recorded, not fixed)"
nginx -t 2>&1 | grep -i 'conflicting server name' | sed 's/^/   /' | tee -a "$EVIDENCE" || true
note "These come from '.bak' files picked up by include sites-enabled/* and"
note "belong to Yummy. They are out of scope for this branch and are left alone."

# --- 1. record the state rollback will need --------------------------------

say "recording rollback state"
PID_BEFORE=$(systemctl show -p MainPID --value "$SITE_UNIT" || echo 0)
LINK_BEFORE=$(readlink "$LINK")
BUILD_BEFORE=$(python3 -c "import json;print(json.load(open('$MANIFEST'))['build_id'])")
cp -a "$MANIFEST" "$BACKUP_DIR/template-manifest-animedia-01.json.before"
[ -f "$VHOST" ] && cp -a "$VHOST" "$BACKUP_DIR/animedia-01.conf.before"

# Backups live here, outside every directory nginx globs. A '.bak' beside a
# config is loaded as a second server block — that is exactly what produces
# the conflicting-server_name warnings this host already has.
cat > "$STATE_FILE" <<JSON
{
  "recorded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "site_unit": "$SITE_UNIT",
  "pid_before": "$PID_BEFORE",
  "build_id_before": "$BUILD_BEFORE",
  "symlink_before": "$LINK_BEFORE",
  "symlink_path": "$LINK",
  "manifest_path": "$MANIFEST",
  "manifest_backup": "$BACKUP_DIR/template-manifest-animedia-01.json.before",
  "vhost_backup": "$BACKUP_DIR/animedia-01.conf.before",
  "release_applied": "$RELEASE_ID",
  "database": "$STATE_DIR/comments.sqlite",
  "database_policy": "preserved by every rollback level; never deleted"
}
JSON
note "pid before     : $PID_BEFORE"
note "build before   : $BUILD_BEFORE"
note "symlink before : $LINK_BEFORE"
note "backups        : $BACKUP_DIR (outside every nginx include glob)"

# --- 2. keys (idempotent) --------------------------------------------------

say "per-tenant keys"
install -d -m 0700 "$KEY_DIR"
for slot in animedia.subject animedia.network animedia.cohort; do
  if [ -s "$KEY_DIR/$slot" ]; then
    note "$slot already exists — left alone"
  else
    MUTATED=$((MUTATED + 1))
    openssl rand -hex 32 > "$KEY_DIR/$slot"
    chmod 0600 "$KEY_DIR/$slot"
    note "$slot created"
  fi
done

# --- 3. gateway (idempotent) ----------------------------------------------

say "comments gateway"
MUTATED=$((MUTATED + 1))
install -d -m 0750 -o lords -g lords "$STATE_DIR"
install -m 0644 "$REPO/automation/host/systemd/comments-gateway.service" "$UNIT"
systemctl daemon-reload
systemctl enable --now comments-gateway.service
sleep 2
systemctl is-active --quiet comments-gateway.service \
  || die "gateway did not start; journalctl -u comments-gateway -n 50"
curl -sS -m 10 -H 'Host: animedia.icu' http://127.0.0.1:9150/api/comments/v1/healthz \
  | grep -q '"status": "ok"' || die "gateway health check failed"
note "gateway up on 127.0.0.1:9150"

# --- 4. nginx (idempotent) -------------------------------------------------

say "nginx"
MUTATED=$((MUTATED + 1))
install -m 0644 "$REPO/automation/host/nginx/animedia-comments.conf" "$SNIPPET"
if grep -q 'animedia-comments.conf' "$VHOST"; then
  note "vhost already includes the snippet — unchanged"
else
  awk '
    /listen 443 ssl;/ { in443=1 }
    in443 && /location \/ \{/ && !done {
      print "    include /etc/nginx/snippets/animedia-comments.conf;"
      print ""
      done=1
    }
    { print }
  ' "$BACKUP_DIR/animedia-01.conf.before" > "$VHOST"
  note "include added to the 443 block of animedia.icu only"
fi
nginx -t || die "nginx config test failed"
systemctl reload nginx

# --- 5. release and mount --------------------------------------------------

say "animedia-01 release"
MUTATED=$((MUTATED + 1))
ln -sfn "../../releases/$RELEASE_ID" "$LINK"

# The public build id is read from this manifest, not from the release
# directory. Leaving it alone is what made the first attempt report an
# unchanged build while running a different artifact.
ARTIFACT_SHA=$(python3 -c "import json;print(json.load(open('$RELEASE_DIR/RELEASE.json'))['artifact_sha256'])")
python3 - "$MANIFEST" "$RELEASE_ID" "$ARTIFACT_SHA" <<'PY'
import json, sys
path, build_id, sha = sys.argv[1], sys.argv[2], sys.argv[3]
m = json.load(open(path, encoding="utf-8"))
m["build_id"] = build_id
m["artifact_sha256"] = sha
m["stage"] = "ANIMEDIA-COMMENTS-CANARY-01"
json.dump(m, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PY
note "symlink   -> $(readlink "$LINK")"
note "manifest  -> build_id $RELEASE_ID"
note "animedia-02 untouched at $(readlink /srv/lords/.frontend/sites/animedia-02/current)"

install -d -m 0755 /etc/systemd/system/"$SITE_UNIT".d
cat > /etc/systemd/system/"$SITE_UNIT".d/comments.conf <<'DROPIN'
[Service]
Environment=ANIMEDIA_COMMENTS_MOUNT=1
DROPIN
systemctl daemon-reload
systemctl restart "$SITE_UNIT"
sleep 3
systemctl is-active --quiet "$SITE_UNIT" || die "$SITE_UNIT did not come back"

# --- 6. verify what is actually running ------------------------------------

say "release verification"
PID_AFTER=$(systemctl show -p MainPID --value "$SITE_UNIT")
RUNNING_CMD=$(tr '\0' ' ' < "/proc/$PID_AFTER/cmdline" 2>/dev/null || echo "")
BUILD_AFTER=$(curl -sS -m 10 --resolve "$RESOLVE" -D - -o /dev/null "$SITE/" \
  | awk 'tolower($1)=="x-site-factory-build-id:"{print $2}' | tr -d '\r')
SHA_AFTER=$(curl -sS -m 10 --resolve "$RESOLVE" -D - -o /dev/null "$SITE/" \
  | awk 'tolower($1)=="x-site-factory-artifact-sha256:"{print $2}' | tr -d '\r')

note "pid        : $PID_BEFORE -> $PID_AFTER"
note "cmdline    : $RUNNING_CMD"
note "build id   : $BUILD_BEFORE -> $BUILD_AFTER"
note "artifact   : $SHA_AFTER (release manifest says $ARTIFACT_SHA)"

[ "$PID_AFTER" != "$PID_BEFORE" ] || die "the service did not actually restart"
case "$RUNNING_CMD" in
  *"$RELEASE_ID"*) note "the running process executes the prepared release" ;;
  *) die "the running process is not the prepared release: $RUNNING_CMD" ;;
esac
[ "$BUILD_AFTER" = "$RELEASE_ID" ] \
  || die "public build id ($BUILD_AFTER) does not match the release ($RELEASE_ID)"
[ "$SHA_AFTER" = "$ARTIFACT_SHA" ] \
  || die "public artifact sha ($SHA_AFTER) does not match the release manifest"

# --- 7. live verification --------------------------------------------------

say "live verification"
fail=0

for path in / /catalog/ /title/master-lda-i-plameni-2/ /definitely-not-real-9d2f/; do
  headers=$(curl -sS -m 10 --resolve "$RESOLVE" -D - -o /dev/null "$SITE$path" || true)
  code=$(printf '%s' "$headers" | head -1 | awk '{print $2}')
  if printf '%s' "$headers" | grep -qi '^X-Robots-Tag:.*noindex'; then
    note "noindex ok   $path ($code)"
  else
    note "NOINDEX LOST $path ($code)"; fail=1
  fi
  case "$code" in 5*) note "5xx on $path"; fail=1;; esac
done

# The check that got this wrong last time. Through nginx, chain followed,
# judged on where it ends and on whether any hop was the gateway.
VISITOR_URL="$SITE/api/comments/v1/threads?resource_type=title&canonical_content_id=$CONTENT_ID"
if python3 "$CHECK" "$VISITOR_URL" --resolve "$RESOLVE" --expect closed-visitor \
     | tee -a "$EVIDENCE" | grep -q '"ok": true'; then
  note "ordinary visitor: refused at the end of the chain — correct"
else
  note "ORDINARY VISITOR WAS NOT REFUSED"; fail=1
fi

# And POST, because a read refusal that still accepts writes is worthless.
if python3 "$CHECK" "$SITE/api/comments/v1/comments" --resolve "$RESOLVE" \
     --method POST --expect closed-visitor | tee -a "$EVIDENCE" | grep -q '"ok": true'; then
  note "ordinary visitor: write refused — correct"
else
  note "ORDINARY VISITOR COULD WRITE"; fail=1
fi

space=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' -H 'Host: animedia.space' \
  http://127.0.0.1:9122/ || true)
note "animedia.space answers $space on its own port, release unchanged"

if [ "$fail" -ne 0 ]; then
  echo "live verification failed" >&2
  exit 2   # the trap rolls back
fi

SUCCEEDED=1
say "done"
cat <<SUMMARY | tee -a "$EVIDENCE"
PID_BEFORE=$PID_BEFORE
PID_AFTER=$PID_AFTER
BUILD_BEFORE=$BUILD_BEFORE
BUILD_AFTER=$BUILD_AFTER
ARTIFACT_SHA256=$SHA_AFTER
STATE_FILE=$STATE_FILE
EVIDENCE=$EVIDENCE
DATABASE_PRESERVED=$STATE_DIR/comments.sqlite

Next: issue yourself an owner cohort cookie with
  $REPO/bin/comments-owner-cookie animedia.icu
and follow docs/comments_platform/OWNER_TEST.md
SUMMARY
