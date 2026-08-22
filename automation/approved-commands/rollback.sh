#!/usr/bin/env bash
# Откат по сохранённому rollback payload. Всегда разрешён при валидном manifest —
# откат безопаснее бездействия.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

SITE=""; DOMAIN=""; EXPERIMENT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --site) SITE="$2"; shift 2;;
    --domain) DOMAIN="$2"; shift 2;;
    --experiment) EXPERIMENT="$2"; shift 2;;
    *) echo "usage: rollback.sh --site ID --domain D --experiment EXP" >&2; exit 2;;
  esac
done
[[ -n "$SITE" && -n "$DOMAIN" && -n "$EXPERIMENT" ]] || { echo "missing args" >&2; exit 2; }

authorize "rollback" "$SITE" "$DOMAIN"
python3 -m seo_operator.cli experiment rollback --site "$SITE" --id "$EXPERIMENT"
