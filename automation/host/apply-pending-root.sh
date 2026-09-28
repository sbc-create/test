#!/usr/bin/env bash
# Всё накопившееся, что требует root, одной командой.
#
#   sudo bash automation/host/apply-pending-root.sh [--dry-run]
#
# Что входит и что это разблокирует
# ---------------------------------
#
#   1. обновление исполнителя   Установленная копия пакета лежит под root и
#                               обновляется только этим шагом. Сейчас в ней нет
#                               трёх вещей: ячейки animego-04 в реестре (без неё
#                               выпуск an1meg0.site отвергается как «нет такой
#                               ячейки»), приёмки по метке выпуска (заголовок
#                               называет ревизию шаблона, и исправный кандидат
#                               zona-02 откатывался с build_matches: false) и
#                               пробы лаунчера перед подачей заявки.
#
#   2. запуск площадки animego-04  Ровно тот же сценарий, что владелец уже
#                               выполнял для lords-05, yummy-07 и yummy-08:
#                               юниты ячейки, nginx, сертификат, сборщик
#                               недельного снимка. Разблокирует an1meg0.site,
#                               у которого сейчас нет ни /srv/an1meg0-site, ни
#                               server_name в nginx, а HTTPS отдаёт чужой
#                               сертификат.
#
#   3. семантика Topvisor       Служба topvisor-connect читает ключ через
#                               systemd LoadCredential; сессия агента к каталогу
#                               секрета не допущена и получает ровно это:
#                               «Нет доступа к каталогу с user-id: процесс не в
#                               группе, которой выдан файл». Запуск разблокирует
#                               группы и запросы у девяти новых проектов, где
#                               сейчас по нулю. Методы add/keywords_2/groups и
#                               add/keywords_2/keywords объявлены БЕСПЛАТНЫМИ;
#                               платные маршруты (проверка позиций, аудит)
#                               клиент не выполняет ни при каком флаге.
#
#   4. счётчик an1meg0.site     Единственный из десяти доменов, у которого
#                               счётчика нет вовсе: в реестре аналитики он
#                               `planned`, counter_id null. Счётчик заводит
#                               служба analytics-connect@ — токен Метрики она
#                               читает через LoadCredential, сессии он
#                               недоступен. Служба сначала ИЩЕТ счётчик этого
#                               домена и переиспользует найденный, поэтому
#                               повторный запуск дубля не создаёт. Вместе со
#                               счётчиком заводятся девять целей.
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
NEW_SITE=animego-04

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"

declare -a results=()
step_ok()   { results+=("ok    $1"); }
step_fail() { results+=("ОТКАЗ $1: $2"); warn "$1: $2"; }

run_step() {
  local name="$1"; shift
  log "$name"
  if [ "$dry_run" = 1 ]; then
    if "$@" --dry-run; then step_ok "$name (сухой прогон)"; else step_fail "$name" "сухой прогон отказал"; fi
  elif "$@"; then
    step_ok "$name"
  else
    step_fail "$name" "сценарий вернул ненулевой код"
  fi
}

# ---------------------------------------------------------------------------
# 1. Исполнитель заявок на выпуск
# ---------------------------------------------------------------------------
run_step "обновление исполнителя" bash "${SRC_ROOT}/automation/host/install-cell-executor.sh"

# ---------------------------------------------------------------------------
# 2. Площадка an1meg0.site
# ---------------------------------------------------------------------------
run_step "запуск площадки ${NEW_SITE}" bash "${SRC_ROOT}/automation/host/launch-new-site.sh" --site "$NEW_SITE"

# ---------------------------------------------------------------------------
# 3. Семантика Topvisor
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
# 4. Счётчик Метрики для an1meg0.site
# ---------------------------------------------------------------------------
metrika_step() {
  local name="счётчик Метрики an1meg0.site"
  local unit="analytics-connect@an1meg0.site.service"
  log "$name"
  if ! systemctl cat "analytics-connect@.service" >/dev/null 2>&1; then
    step_fail "$name" "шаблона analytics-connect@.service нет"
    return 0
  fi
  if [ "$dry_run" = 1 ]; then
    echo "   [сухой прогон] systemctl start --wait ${unit}"
    step_ok "$name (сухой прогон)"
    return 0
  fi
  if systemctl start --wait "$unit"; then
    step_ok "$name"
  else
    step_fail "$name" "служба вернула ненулевой код, отчёт: var/analytics/connect-an1meg0.site.json"
  fi
}
metrika_step

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
log "готово. Дальше без root: python3 -m factory cell trigger --site ${NEW_SITE} --confirm-activation"
