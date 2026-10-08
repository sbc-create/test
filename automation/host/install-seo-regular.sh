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
#   editor-run.timer           фоновый редактор: проверка каждые 5 мин без модели;
#                              модель — не чаще раза в час и только при работе, ≤ 2 материалов
#   editor-run-manual.service  ручной запуск редактора владельцем (trigger=systemd-manual)
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
EDITOR_UNITS=(editor-run.service editor-run-manual.service editor-run.timer)
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

for unit in "${EDITOR_UNITS[@]}"; do
  [ -f "$HERE/editor/$unit" ] || { echo "нет $HERE/editor/$unit" >&2; exit 66; }
  case "$unit" in
    *.service)
      grep -qx "WorkingDirectory=$REPO_ROOT" "$HERE/editor/$unit" || {
        echo "$unit: WorkingDirectory не равен $REPO_ROOT — установка остановлена" >&2; exit 65; }
      grep -qx "User=claude" "$HERE/editor/$unit" || { echo "$unit: служба не от claude" >&2; exit 65; } ;;
  esac
done
grep -q "^REPO=$REPO_ROOT\$" "$HERE/editor/editor-run.sh" || {
  echo "editor-run.sh: REPO не равен $REPO_ROOT" >&2; exit 65; }

# --- Предварительная проверка: ничего не пишет и секретов не выводит --------
preflight_fail=0
check() {  # check <описание> <команда...>
  local what="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "  ok   $what"; else echo "  FAIL $what"; preflight_fail=1; fi
}
as_claude() {
  if [ "$(id -un)" = claude ]; then "$@"; else sudo -u claude -H "$@"; fi
}
CLAUDE_BIN=/home/claude/.local/bin/claude
echo "предварительная проверка:"
check "пользователь claude существует" id claude
check "python3 службы: /usr/bin/python3" test -x /usr/bin/python3
check "CLI Claude исполняем для claude ($CLAUDE_BIN)" as_claude test -x "$CLAUDE_BIN"
check "CLI Claude отвечает на --version" as_claude "$CLAUDE_BIN" --version
# Только наличие и права: содержимое не читается и не выводится.
check "учётные данные модели есть у claude (~/.claude/.credentials.json, непустой)" as_claude test -s /home/claude/.claude/.credentials.json
check "учётные данные доступны только владельцу (режим 600)" \
  bash -c '[ "$(stat -c %a /home/claude/.claude/.credentials.json)" = 600 ]'
check "мост MCP отвечает на 127.0.0.1:9000" \
  bash -c 'exec 3<>/dev/tcp/127.0.0.1/9000'
check "задание редактора на месте" test -s "$REPO_ROOT/docs/editor/EDITOR_RUN_PROMPT.md"
check "помощник источников на месте" test -s "$REPO_ROOT/automation/local/source_fetch.py"
check "Shikimori в inventory" grep -q "host: shikimori.io" "$REPO_ROOT/inventory/network-allowlist.yaml"
if [ "$preflight_fail" -ne 0 ]; then
  echo "предварительная проверка не пройдена — установка остановлена, ничего не записано" >&2
  exit 70
fi

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
run install -d -o claude -g claude -m 0755 "$REPO_ROOT/var/editor-runs"
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
echo "ручной полный запуск редактора (помечается systemd-manual):"
echo "  sudo systemctl start editor-run-manual.service"
