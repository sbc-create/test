#!/usr/bin/env bash
# Backup of the control host's own state, with a restore that is proven, not assumed.
#
# This is the host-level counterpart of the per-site backup contract in
# `backup_policy` — it covers what the site packages do not: factory runtime
# state, host configuration, and the git history itself. It does not replace
# `automation/ansible/backup-site.yml`, which backs up a deployed site on a target.
#
# The repository rule applies here too: the existence of an archive is not proof
# of a restore. Every archive is extracted into a temporary directory and every
# file is compared by SHA-256 before the run is recorded as verified.
set -uo pipefail

REPO="${FACTORY_REPO:-/srv/site-factory/repo}"
BACKUP_DIR="${SITE_FACTORY_BACKUP_DIR:-/srv/backups}"
LOG_DIR="${SITE_FACTORY_LOG_DIR:-/var/log/site-factory}"
KEEP="${SITE_FACTORY_BACKUP_KEEP:-14}"
# Never prune below this many verified backups, whatever the retention says.
KEEP_FLOOR=3

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { echo "BACKUP FAILED: $*" >&2; exit 1; }

mkdir -p "$BACKUP_DIR" "$LOG_DIR" || fail "не удалось создать каталоги"

ARCHIVE="$BACKUP_DIR/host-$STAMP.tar.gz"
# The git bundle is a rolling mirror, not a dated copy: this repository's
# history is ~300 MB, and one bundle per run would fill a 70 GB disk in two
# weeks. Two generations are kept so there is never a moment without one.
BUNDLE="$BACKUP_DIR/repo-latest.bundle"
BUNDLE_PREV="$BACKUP_DIR/repo-previous.bundle"
RECORD="$BACKUP_DIR/host-$STAMP.verified.json"

# ---------------------------------------------------------------------------
# 1. Collect. Secrets are excluded by pattern, not by hoping none are present.
# ---------------------------------------------------------------------------
STAGE="$WORK/stage"
mkdir -p "$STAGE"

collect() {
  local src="$1" dest="$2"
  [ -e "$src" ] || return 0
  mkdir -p "$(dirname "$STAGE/$dest")"
  rsync -a --quiet \
        --exclude='*.pem' --exclude='*.key' --exclude='.env' --exclude='.env.*' \
        --exclude='secrets/' --exclude='*staging-auth*' --exclude='node_modules/' \
        --exclude='.venv/' --exclude='__pycache__/' \
        --exclude='*.password' --exclude='db/' \
        "$src" "$STAGE/$dest" || fail "rsync $src"
}

collect "$REPO/var/"            "factory-var/"
collect /etc/site-factory/      "etc-site-factory/"
collect /etc/nginx/sites-available/ "etc-nginx-sites/"
collect /srv/sites/             "srv-sites/"

mkdir -p "$STAGE/host-facts"
{
  echo "# generated $STAMP — no secrets"
  echo "## systemd site-factory units"; systemctl list-unit-files 'site-factory*' --no-pager 2>/dev/null
  echo "## ufw"; ufw status verbose 2>/dev/null || echo "(нет прав на ufw)"
  echo "## packages"; dpkg -l | awk '/^ii/{print $2"="$3}'
} > "$STAGE/host-facts/inventory.txt" 2>/dev/null

# git bundle: the repository history, recoverable without GitHub.
if [ -d "$REPO/.git" ]; then
  git -C "$REPO" bundle create "$WORK/repo.bundle" --all >/dev/null 2>&1 || fail "git bundle"
  git -C "$REPO" bundle verify "$WORK/repo.bundle" >/dev/null 2>&1 || fail "git bundle не проходит проверку"
  # Replace only after the new bundle verified, and keep the previous one:
  # a failed run must never leave the host without a recoverable history.
  [ -f "$BUNDLE" ] && mv -f "$BUNDLE" "$BUNDLE_PREV"
  mv -f "$WORK/repo.bundle" "$BUNDLE"
  chmod 0640 "$BUNDLE"
fi

# ---------------------------------------------------------------------------
# 2. Archive with a manifest of checksums taken from the source, before packing.
# ---------------------------------------------------------------------------
( cd "$STAGE" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum ) > "$WORK/manifest.sha256" \
  || fail "не удалось посчитать контрольные суммы"
FILE_COUNT="$(wc -l < "$WORK/manifest.sha256")"

tar -czf "$ARCHIVE" -C "$STAGE" . || fail "не удалось создать архив"
chmod 0640 "$ARCHIVE"

# ---------------------------------------------------------------------------
# 3. Prove the restore. Extract elsewhere and compare every checksum.
# ---------------------------------------------------------------------------
RESTORE="$WORK/restore"
mkdir -p "$RESTORE"
tar -xzf "$ARCHIVE" -C "$RESTORE" || fail "архив не распаковывается"

MISMATCH="$(cd "$RESTORE" && sha256sum --quiet -c "$WORK/manifest.sha256" 2>&1 | head -20)"
if [ -n "$MISMATCH" ]; then
  fail "восстановление не совпало с источником: $MISMATCH"
fi

RESTORED_COUNT="$(cd "$RESTORE" && find . -type f | wc -l)"
if [ "$RESTORED_COUNT" -lt "$FILE_COUNT" ]; then
  fail "в восстановленном наборе $RESTORED_COUNT файлов против $FILE_COUNT в источнике"
fi

# ---------------------------------------------------------------------------
# 4. Record. Only now is the backup allowed to count as verified.
# ---------------------------------------------------------------------------
python3 - "$RECORD" "$ARCHIVE" "$BUNDLE" "$FILE_COUNT" "$STAMP" <<'PYEOF'
import hashlib, json, os, sys
record, archive, bundle, count, stamp = sys.argv[1:6]
def sha(p):
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
json.dump({
    "backup": "control-host",
    "created_at": stamp,
    "archive": archive,
    "archive_sha256": sha(archive),
    "archive_bytes": os.path.getsize(archive),
    "git_bundle": bundle if os.path.exists(bundle) else None,
    "git_bundle_sha256": sha(bundle),
    "files": int(count),
    "restore_verified": True,
    "restore_method": "extract to temp dir + sha256sum -c against source manifest",
}, open(record, "w"), ensure_ascii=False, indent=2)
PYEOF
chmod 0640 "$RECORD"

# ---------------------------------------------------------------------------
# 5. Retention. Prunes only fully verified triples, never below the floor.
# ---------------------------------------------------------------------------
mapfile -t VERIFIED < <(find "$BACKUP_DIR" -maxdepth 1 -name 'host-*.verified.json' | sort)
TOTAL=${#VERIFIED[@]}
if [ "$TOTAL" -gt "$KEEP" ] && [ "$TOTAL" -gt "$KEEP_FLOOR" ]; then
  DROP=$(( TOTAL - KEEP ))
  [ $(( TOTAL - DROP )) -lt $KEEP_FLOOR ] && DROP=$(( TOTAL - KEEP_FLOOR ))
  for (( i = 0; i < DROP; i++ )); do
    base="$(basename "${VERIFIED[$i]}" .verified.json)"
    rm -f "$BACKUP_DIR/$base.tar.gz" "${VERIFIED[$i]}"
    echo "retention: удалён $base"
  done
fi

echo "OK: $ARCHIVE ($FILE_COUNT файлов) — восстановление подтверждено, запись $RECORD"
