#!/usr/bin/env bash
# Where an nginx backup may live, and what to do with one that is in the wrong
# place. Sourced by the Stage 1 apply and rollback scripts so the rule has one
# definition rather than two that drift.
#
# The rule exists because of a real outage shape on this host:
#
#   include /etc/nginx/sites-enabled/*;      <- no extension filter at all
#   include /etc/nginx/lords/*.conf;         <- filtered, but only by suffix
#
# A backup written beside the config it backs up is therefore loaded as a
# second server block. That is what produced the `conflicting server name`
# warnings already present here, and an earlier version of the Stage 1 apply
# script added to the pile with animedia-01.conf.before-comments-stage1.
#
# Two functions, two different jobs:
#
#   nginx_backup_path  — the only way to name a backup. It refuses to return a
#                        path inside /etc/nginx, so writing one there is not a
#                        discipline to remember but a thing that cannot happen.
#   nginx_quarantine   — moves a stray that is already there into the backup
#                        store under a name that cannot collide. It never
#                        deletes: a stray is somebody's rollback copy, and the
#                        problem with it is its location, not its content.
#
# Callers must define BACKUP_DIR and a die() that exits non-zero.

# Directories whose contents nginx loads by glob. Kept as a list so a new one
# is added in a single place.
NGINX_GLOB_DIRS=${NGINX_GLOB_DIRS:-"/etc/nginx/lords /etc/nginx/sites-enabled /etc/nginx/snippets /etc/nginx/conf.d"}

# Names this harness has ever used for a backup or a scratch copy. Anything
# matching these inside a glob directory is ours to move.
NGINX_STRAY_PATTERNS=${NGINX_STRAY_PATTERNS:-'*comments-stage1* *.before-comments* *.prev'}

nginx_backup_path() {
  local name="$1" resolved
  [ -n "${BACKUP_DIR:-}" ] || die "BACKUP_DIR is not set"
  case "$name" in
    */*|"") die "a backup name must be a bare filename, got: $name" ;;
  esac
  # readlink -f on the directory, not the file: the file need not exist yet.
  resolved=$(readlink -f "$BACKUP_DIR")
  case "$resolved/" in
    /etc/nginx/*)
      die "BACKUP_DIR resolves inside /etc/nginx ($resolved) — refusing to write $name" ;;
  esac
  printf '%s/%s' "$resolved" "$name"
}

_nginx_find_strays() {
  local dirs=() pats=() d p expr=()
  read -r -a dirs <<<"$NGINX_GLOB_DIRS"
  read -r -a pats <<<"$NGINX_STRAY_PATTERNS"
  for d in "${dirs[@]}"; do [ -d "$d" ] || continue; done
  # Build `\( -name A -o -name B ... \)`. The grouping matters: without it the
  # implicit -print binds to the last pattern only and the rest match silently.
  expr+=( '(' )
  for p in "${pats[@]}"; do
    [ "${#expr[@]}" -eq 1 ] || expr+=( -o )
    expr+=( -name "$p" )
  done
  expr+=( ')' )
  local existing=()
  for d in "${dirs[@]}"; do [ -d "$d" ] && existing+=( "$d" ); done
  [ "${#existing[@]}" -gt 0 ] || return 0
  find "${existing[@]}" -maxdepth 1 -type f "${expr[@]}" 2>/dev/null | sort
}

# Prints each quarantined destination on its own line.
nginx_quarantine() {
  local stray base stamp dest n
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  while IFS= read -r stray; do
    [ -n "$stray" ] || continue
    base=$(basename "$stray")
    dest=$(nginx_backup_path "$base.quarantined.$stamp")
    n=0
    while [ -e "$dest" ]; do
      n=$((n + 1))
      dest=$(nginx_backup_path "$base.quarantined.$stamp.$n")
    done
    mv -n "$stray" "$dest" || die "could not quarantine $stray -> $dest"
    [ -e "$stray" ] && die "quarantine left the original in place: $stray"
    [ -e "$dest" ]  || die "quarantine produced no file at $dest"
    printf '%s\n' "$dest"
  done <<EOF
$(_nginx_find_strays)
EOF
}

# Non-zero, and prints what it found, if anything is still in the wrong place.
nginx_assert_clean() {
  local left
  left=$(_nginx_find_strays)
  [ -z "$left" ] || { printf '%s\n' "$left"; return 1; }
  return 0
}
