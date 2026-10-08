#!/usr/bin/env bash
# Регулярный прогон SEO-модуля: одна команда владельца.
#
#   sudo bash automation/host/install-seo-regular.sh [--dry-run]
#
# Что ставится
# ------------
#
#   seo-regular-check.timer    каждые 6 часов, 05/11/17/23:25 UTC — короткая проверка
#   seo-regular-daily.timer    05:40 UTC (08:40 МСК) — анализ и ОДИН отчёт владельцу
#   seo-regular-weekly.timer   понедельник 05:32 UTC — пересмотр приоритетов
#   analytics-cabinet.timer    перенос сбора аналитики 06:10 -> 05:00 UTC
#   webmaster-inventory.service  однократное чтение Вебмастера (только GET)
#   editor-run.timer           фоновый редактор: 03/09/15/21:15 UTC, до 2 материалов
#
# Почему нужна эта команда. Таймеры живут в /etc/systemd/system, а у сессии
# агента нет root: ставить их сама она не может и не должна.
#
# Что команда НЕ делает: не меняет ни одного сайта, nginx, режима индексации,
# очереди и реестра; не выдаёт службам секретов (они читают снимки
# analytics-cabinet). Существующие службы не трогаются, кроме времени
# analytics-cabinet.timer — его служба и ExecStart не меняются.
#
# Откат:
#   sudo systemctl disable --now seo-regular-check.timer seo-regular-daily.timer seo-regular-weekly.timer
#   sudo install -m 0644 <копия .before-seo-regular> /etc/systemd/system/analytics-cabinet.timer
#   sudo systemctl daemon-reload
set -Eeuo pipefail

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SRC="$HERE/seo-regular"
DEST=/etc/systemd/system
STATE="$REPO_ROOT/var/seo-regular"
UNITS=(seo-regular-check.service seo-regular-check.timer
       seo-regular-daily.service seo-regular-daily.timer
       seo-regular-weekly.service seo-regular-weekly.timer
       seo-regular-hourly.service seo-regular-hourly.timer
       webmaster-inventory.service)
EDITOR_UNITS=(editor-run.service editor-run.timer)
TIMERS=(seo-regular-check.timer seo-regular-daily.timer seo-regular-weekly.timer seo-regular-hourly.timer)

for unit in "${UNITS[@]}"; do
  [ -f "$SRC/$unit" ] || { echo "нет $SRC/$unit" >&2; exit 66; }
  case "$unit" in
    *.service)
      # Юнит исполняет код того дерева, что записано в нём. Ставить из другого
      # дерева — значит молча запускать чужую ветку.
      grep -qx "WorkingDirectory=$REPO_ROOT" "$SRC/$unit" || {
        echo "$unit: WorkingDirectory не равен $REPO_ROOT — установка остановлена" >&2
        exit 65; } ;;
  esac
done

run() {
  if [ "$dry_run" -eq 1 ]; then echo "[dry-run] $*"; else echo "+ $*"; "$@"; fi
}

if [ "$dry_run" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
  echo "нужен root: sudo bash $0" >&2
  exit 1
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
# Каталог состояния должен существовать ДО первого запуска: ReadWritePaths на
# несуществующий путь роняет юнит на подготовке пространства имён.
run install -d -o claude -g claude -m 0755 "$STATE"
for unit in "${UNITS[@]}"; do
  run install -m 0644 "$SRC/$unit" "$DEST/$unit"
done
if [ -f "$DEST/analytics-cabinet.timer" ]; then
  run cp -p "$DEST/analytics-cabinet.timer" "$DEST/analytics-cabinet.timer.before-seo-regular-$stamp"
fi
run install -m 0644 "$HERE/analytics-cabinet.timer" "$DEST/analytics-cabinet.timer"
run systemctl daemon-reload
run systemctl restart analytics-cabinet.timer
run systemctl enable --now "${TIMERS[@]}"
for unit in "${EDITOR_UNITS[@]}"; do
  run install -m 0644 "$HERE/editor/$unit" "$DEST/$unit"
done
run systemctl daemon-reload
run systemctl enable --now editor-run.timer
# Однократное ЧТЕНИЕ Вебмастера: почему у доменов нет данных. Наружу ничего не пишет.
run systemctl start webmaster-inventory.service
run systemctl list-timers --no-pager analytics-cabinet.timer "${TIMERS[@]}"

echo
echo "Проверка без root (сессия агента):"
echo "  ls -l --time-style=full-iso /var/lib/systemd/timers/stamp-seo-regular-*"
echo "  python3 -m seo_operator.cli regular status"
echo "  cat $REPO_ROOT/var/analytics/webmaster-inventory.json"
echo "  python3 -m seo_operator.cli editor-run-status"
