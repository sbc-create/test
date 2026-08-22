#!/usr/bin/env bash
# Единственный разрешённый путь к CMS mutation. Snapshot до, rollback payload обязателен.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

usage() { echo "usage: cms-mutate.sh --site ID --domain D --action A --experiment EXP [--dry-run]" >&2; exit 2; }

SITE=""; DOMAIN=""; ACTION=""; EXPERIMENT=""; DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --site) SITE="$2"; shift 2;;
    --domain) DOMAIN="$2"; shift 2;;
    --action) ACTION="$2"; shift 2;;
    --experiment) EXPERIMENT="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    *) usage;;
  esac
done
[[ -n "$SITE" && -n "$DOMAIN" && -n "$ACTION" && -n "$EXPERIMENT" ]] || usage

authorize "$ACTION" "$SITE" "$DOMAIN"

# GR-006: без snapshot и rollback payload mutation не выполняется.
python3 -m seo_operator.cli cms-mutate \
  --site "$SITE" --action "$ACTION" --experiment "$EXPERIMENT" \
  $([[ $DRY_RUN -eq 1 ]] && echo --dry-run || echo --apply)
