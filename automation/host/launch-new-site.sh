#!/usr/bin/env bash
# Подключение НОВОГО домена к хосту: юниты ячейки и nginx. Одна команда.
#
#   sudo bash automation/host/launch-new-site.sh --site zona-03 [--dry-run]
#
# Что делает и в каком порядке
# ---------------------------
#
#   1. юниты ячейки по реестру (только недостающие; существующие не трогает)
#   2. nginx: upstream + конфигурация домена, с проверкой перед перезагрузкой
#
# Чего НЕ делает: не выпускает сайт и не включает службы. Выпуск идёт через
# очередь исполнителя, и до него хранилище витрины пусто — служба, поднятая
# здесь, отказалась бы «нет снимка каталога».
#
# Сертификат отдельным шагом ПОСЛЕ этой команды: блок 443 со ссылкой на
# несуществующий сертификат не даст nginx перезагрузиться вовсе, и ошибка
# нового домена уронила бы соседние.
set -Eeuo pipefail

site=""
dry_run=""
while [ $# -gt 0 ]; do
  case "$1" in
    --site) site="${2:-}"; shift ;;
    --dry-run) dry_run="--dry-run" ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$site" ] || { echo "нужен --site" >&2; exit 2; }

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
ok()  { printf '   \033[32m[ок]\033[0m %s\n' "$*"; }
bad() { printf '   \033[31m[нет]\033[0m %s\n' "$*"; }

[ -n "$dry_run" ] || [ "$(id -u)" = 0 ] || { echo "нужен root" >&2; exit 1; }

unit="$(python3 - "$site" <<'PY'
import json, sys
from pathlib import Path
корень = Path(__file__).resolve() if False else None
д = json.loads(Path("config/site-cells.json").read_text(encoding="utf-8"))
for c in д.get("cells") or []:
    if c["site_id"] == sys.argv[1]:
        print((c.get("runtime") or {}).get("unit") or "")
        break
PY
)"
[ -n "$unit" ] || { echo "в реестре нет юнита для $site" >&2; exit 2; }

log "шаг 1: юниты ячейки"
python3 "$REPO/automation/host/install-cell-units.py" $dry_run
if [ -z "$dry_run" ]; then
  if [ -f "/etc/systemd/system/$unit" ]; then ok "$unit на месте"; else bad "$unit не появился"; exit 3; fi
fi

log "шаг 2: nginx для домена"
bash "$REPO/automation/host/install-site-nginx.sh" --site "$site" $dry_run

log "итог"
if [ -n "$dry_run" ]; then
  echo "   сухой прогон: ничего не менялось"
  exit 0
fi
cat <<'TAIL'
   Дальше без root — выпуск через очередь:

     python3 -m factory cell trigger --site <site_id> --ci-run <прогон> --confirm-activation

   Сертификат и блок 443 — отдельным шагом после первой публичной проверки по
   HTTP: так ошибка нового домена не задевает соседние.
TAIL
