#!/usr/bin/env bash
# Частый опрос новых серий: установка юнита и таймера.
#
#   sudo bash automation/host/install-episode-poll.sh [--dry-run]
#
# Почему отдельный юнит, а не строка в суточном прогоне
# -----------------------------------------------------
#
# Суточного цикла для новых серий мало по арифметике, а не по устройству:
# серии выходят каждый день, и любое суточное расписание даёт задержку до
# суток ещё до первого запроса к источнику. Полный обход каталога этого не
# лечит — он лечит полноту, а не скорость.
#
# Бюджет: внутри подтверждённого, а не сверх
# ------------------------------------------
#
# Подтверждённая нагрузка на источник — 6000 запросов в сутки. Этот юнит
# работает внутри неё: суточный добор снижен (покрытие кэша достигло 100 %,
# и его прежняя задача — закрыть пропуски — выполнена), освободившееся отдано
# частому опросу.
#
#   срочные   5 x 96 =   480/сут   доступно меньше заявленного
#   свежие   20 x 96 =  1920/сут   сериалы последних лет, круг с позицией
#   полный   10 x 96 =   960/сут   все сериалы, круг с позицией
#   суточный прогон    ~2100/сут
#                    ------------
#                      ~5460/сут   против подтверждённых 6000
#
# Учётные данные источника берутся ИЗ УЖЕ УСТАНОВЛЕННОГО суточного юнита —
# теми же строками LoadCredential. Сценарий не знает и не печатает ни путей
# секретов сверх того, что там уже записано, ни тем более их значений.
set -Eeuo pipefail

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

SRC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
UNIT_DIR=/etc/systemd/system
DONOR="$UNIT_DIR/nova-daily-refresh.service"
SERVICE="$UNIT_DIR/nova-episode-poll.service"
TIMER=nova-episode-poll.timer
TOOL=/srv/site-factory/repo/automation/host/nova-detail-backfill.py

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"
[ -r "$DONOR" ] || die "нет $DONOR: не из чего взять учётные данные источника"
[ -f "$TOOL" ] || die "нет $TOOL"

# Ровно те же строки, что уже разрешены владельцем для суточного прогона.
mapfile -t creds < <(grep -E '^LoadCredential=' "$DONOR" || true)
[ "${#creds[@]}" -gt 0 ] || die "в $DONOR нет строк LoadCredential"
log "учётные данные источника: ${#creds[@]} строк(и) взяты из nova-daily-refresh.service"

if [ "$dry_run" = 1 ]; then
  log "[сухой прогон] записал бы $SERVICE и включил бы $TIMER"
  printf '   бюджет: 5 срочных + 20 свежих + 10 полного круга за прогон, 96 прогонов в сутки\n'
  exit 0
fi

{
  printf '# Частый опрос новых серий. Установлен install-episode-poll.sh;\n'
  printf '# строки LoadCredential скопированы из nova-daily-refresh.service.\n'
  printf '[Unit]\nDescription=nova: частый опрос новых серий\n'
  printf 'After=network-online.target\nWants=network-online.target\n\n'
  printf '[Service]\nType=oneshot\nUser=root\n'
  printf 'WorkingDirectory=/srv/site-factory/repo\nTimeoutStartSec=800\n'
  printf '%s\n' "${creds[@]}"
  printf 'ExecStart=/usr/bin/python3 %s --budget 0 --ongoing-budget 5 --hot-budget 20 --ring-budget 10 --report /srv/site-factory/repo/var/lords/episode-poll-report.json\n' "$TOOL"
  printf '\nNoNewPrivileges=yes\nProtectSystem=full\n'
  printf 'ProtectKernelTunables=yes\nRestrictSUIDSGID=yes\n\n'
  printf '[Install]\nWantedBy=multi-user.target\n'
} > "$SERVICE"
chmod 0644 "$SERVICE"
install -m 0644 "$SRC_ROOT/automation/host/$TIMER" "$UNIT_DIR/$TIMER"
systemctl daemon-reload
systemctl enable --now "$TIMER"

log "первый прогон сейчас, чтобы отказ был виден сразу, а не через 15 минут"
if systemctl start nova-episode-poll.service; then
  log "  прогон выполнен"
else
  die "первый прогон не удался: journalctl -u nova-episode-poll.service -n 50"
fi
systemctl list-timers "$TIMER" --no-pager
echo
echo "Опрос включён. Отчёт прогона: /srv/site-factory/repo/var/lords/episode-poll-report.json"
