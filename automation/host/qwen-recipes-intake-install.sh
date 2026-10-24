#!/usr/bin/env bash
# Установка таймера приёма поставок Qwen для bestreciept.site и myfood.mobi (только эти два сайта).
#   sudo bash /home/claude/wt-template-food-daily/automation/host/qwen-recipes-intake-install.sh [--dry-run]
#   sudo bash /home/claude/wt-template-food-daily/automation/host/qwen-recipes-intake-install.sh --remove
# Ставит qwen-recipes-intake.service/.timer (проход каждые 30 минут от пользователя claude, пишет только
# в var/qwen-recipes), выполняет первый проход и показывает его итог. Другие юниты не трогает.
set -euo pipefail
SRC=/home/claude/wt-template-food-daily/automation/host/systemd
DST=/etc/systemd/system
UNITS=(qwen-recipes-intake.service qwen-recipes-intake.timer)
DRY=0; REMOVE=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --remove) REMOVE=1 ;;
    *) echo "неизвестный аргумент: $a" >&2; exit 2 ;;
  esac
done
run() { if [[ $DRY == 1 ]]; then echo "   [сухой прогон] $*"; else "$@"; fi; }
[[ $DRY == 1 || $EUID == 0 ]] || { echo "нужен root: sudo bash $0" >&2; exit 1; }
if [[ $REMOVE == 1 ]]; then
  run systemctl disable --now qwen-recipes-intake.timer || true
  for u in "${UNITS[@]}"; do run rm -f "$DST/$u"; done
  run systemctl daemon-reload
  echo "==> таймер приёма Qwen снят"; exit 0
fi
for u in "${UNITS[@]}"; do
  [[ -f "$SRC/$u" ]] || { echo "нет $SRC/$u" >&2; exit 1; }
  run install -m 0644 -o root -g root "$SRC/$u" "$DST/$u"
done
run systemd-analyze verify "$DST/qwen-recipes-intake.service" "$DST/qwen-recipes-intake.timer"
run systemctl daemon-reload
run systemctl enable --now qwen-recipes-intake.timer
run systemctl start qwen-recipes-intake.service   # первый проход сразу
if [[ $DRY == 0 ]]; then
  systemctl --no-pager --lines=0 status qwen-recipes-intake.service || true
  systemctl list-timers --no-pager qwen-recipes-intake.timer
  python3 -c 'import json; s=json.load(open("/home/claude/wt-template-food-daily/var/qwen-recipes/runs.json")); print("последний проход:", s.get("last_pass"))'
fi
echo "==> готово: проход приёма Qwen каждые 30 минут; снять: --remove"
