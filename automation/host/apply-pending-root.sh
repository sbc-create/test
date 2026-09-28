#!/usr/bin/env bash
# Всё накопившееся, что требует root, одной командой.
#
#   sudo bash automation/host/apply-pending-root.sh [--dry-run]
#
# Что УЖЕ сделано и сюда больше не входит (проверено 2026-09-28 12:30):
# исполнитель обновлён, площадка animego-04 запущена, счётчик an1meg0.site
# 113121466 заведён с девятью целями, домен выложен и принят публично;
# дополнения каталога an1meg0.site доставлены штатным исполнителем, root
# для них не понадобился — /top/ отдаёт 99 карточек, как у соседей.
#
# Что осталось и что каждый шаг разблокирует:
#
#   1. семантика Topvisor       Девять новых проектов стоят с нулём групп и
#                               нулём запросов. Причина найдена и исправлена в
#                               коде: `topvisor apply` выходил по пустому плану,
#                               не дойдя до второй фазы. Служба читает ключ через
#                               LoadCredential; сессии каталог секрета закрыт и
#                               отвечает ровно это: «Нет доступа к каталогу с
#                               user-id: процесс не в группе, которой выдан
#                               файл». Методы add/keywords_2/* бесплатны;
#                               платные маршруты клиент не выполняет ни при
#                               каком флаге.
#
#   2. расписание Yummy         Контентный контур Yummy собран и опубликован
#                               вручную 2026-09-28 (7386 записей, свежайшая
#                               публикация 27.09). Ничто его не запускает: с
#                               10.09 импорт не выполнялся, и проекция протухла
#                               на 424 часа. Таймер ставит это на расписание —
#                               через двадцать минут после ночного прохода
#                               поставщика.
#
# Каждый шаг проверяется и не трогает соседей при отказе. Шаги независимы:
# провал одного не отменяет остальных, итог печатается в конце.
#
# Чего сценарий НЕ делает: не меняет sudoers, firewall, SSH, DNS и индексацию;
# не трогает чужие витрины; не открывает наружу ни одного порта; не выводит
# секретов.
set -Eeuo pipefail

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

SRC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"

declare -a results=()
step_ok()   { results+=("ok    $1"); }
step_fail() { results+=("ОТКАЗ $1: $2"); warn "$1: $2"; }

# ---------------------------------------------------------------------------
# 1. Семантика Topvisor
# ---------------------------------------------------------------------------
topvisor_step() {
  local name="семантика Topvisor"
  log "$name"
  if [ "$dry_run" = 1 ]; then
    if systemctl cat topvisor-connect.service >/dev/null 2>&1; then
      echo "   [сухой прогон] systemctl start --wait topvisor-connect.service"
      step_ok "$name (сухой прогон)"
    else
      step_fail "$name" "юнита topvisor-connect.service нет — сначала install-units.sh"
    fi
    return 0
  fi
  if ! systemctl cat topvisor-connect.service >/dev/null 2>&1; then
    step_fail "$name" "юнита topvisor-connect.service нет"
    return 0
  fi
  if systemctl start --wait topvisor-connect.service; then
    step_ok "$name"
  else
    step_fail "$name" "служба вернула ненулевой код, отчёт: var/topvisor/connect-latest.txt"
  fi
}
topvisor_step

# ---------------------------------------------------------------------------
# 2. Расписание обновления контентного контура Yummy
# ---------------------------------------------------------------------------
yummy_step() {
  local name="расписание обновления каталога Yummy"
  local src="${SRC_ROOT}/automation/host"
  log "$name"
  if [ ! -f "${src}/yummy-content-refresh.service" ]; then
    step_fail "$name" "юнита нет в репозитории"
    return 0
  fi
  if [ "$dry_run" = 1 ]; then
    echo "   [сухой прогон] install yummy-content-refresh.{service,timer} -> /etc/systemd/system/"
    echo "   [сухой прогон] systemctl daemon-reload && systemctl enable --now yummy-content-refresh.timer"
    step_ok "$name (сухой прогон)"
    return 0
  fi
  install -m 0644 "${src}/yummy-content-refresh.service" \
    /etc/systemd/system/yummy-content-refresh.service
  install -m 0644 "${src}/yummy-content-refresh.timer" \
    /etc/systemd/system/yummy-content-refresh.timer
  systemctl daemon-reload
  if systemctl enable --now yummy-content-refresh.timer; then
    step_ok "$name"
  else
    step_fail "$name" "таймер не включён"
  fi
}
yummy_step

# ---------------------------------------------------------------------------
# Итог
# ---------------------------------------------------------------------------
log "итог"
for line in "${results[@]}"; do printf '   %s\n' "$line"; done
if printf '%s\n' "${results[@]}" | grep -q '^ОТКАЗ'; then
  echo
  warn "часть шагов не выполнена — остальные применены, повтор безопасен"
  exit 1
fi
echo
log "готово. Проверить: семантику в var/topvisor/check-after-connect.txt и свежесть /srv/lords/.frontend/yummy-07-catalog.json"
