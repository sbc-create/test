#!/usr/bin/env bash
# Одно действие, снимающее три доказанных блокировки переноса.
#
#   sudo bash automation/host/unblock-transfer.sh [--dry-run]
#
# Три установщика уже существуют и проверены по отдельности; здесь они собраны
# в один прогон в единственно правильном порядке и с проверкой результата
# после каждого. Порознь они блокируют друг друга: без обновлённого
# исполнителя перенос Yummy отказывает, без юнита zonafilm.cc её нельзя
# перенести, без исправленного drop-in суточное обновление не запускается.
#
# Что именно меняется и что это разблокирует
# ------------------------------------------
#
#   1. исполнитель      контракт данных ищет репозиторий сам
#                       -> первый выпуск Yummy перестаёт требовать
#                          yummy-biz-details.json, которого у семейства нет
#   2. юниты по реестру только недостающие; сейчас это два файла zonafilm.cc
#                       -> zonafilm.cc можно перенести в своё размещение
#   3. пути издателя    ReadWritePaths=-<путь>
#                       -> 226/NAMESPACE снят, суточное обновление стартует
#
# Службы не включаются и не запускаются: это работа исполнителя. Суточное
# обновление здесь тоже не запускается — сначала проверка, что drop-in принят.
set -Eeuo pipefail

dry_run=""
launch=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run="--dry-run" ;;
    --with-launch) launch="${2:-}"; shift ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALLED=/usr/local/lib/site-factory-cell
DROPIN_DIR=/etc/systemd/system/nova-daily-refresh.service.d

log()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32m[ок]\033[0m %s\n' "$*"; }
bad()  { printf '   \033[31m[нет]\033[0m %s\n' "$*"; }

[ -n "$dry_run" ] || [ "$(id -u)" = 0 ] || { echo "нужен root" >&2; exit 1; }

log "шаг 1: исполнитель с контрактом, который находит репозиторий"
bash "$REPO/automation/host/install-cell-executor.sh" ${dry_run:+--dry-run} || true
if [ -z "$dry_run" ]; then
  if grep -qs 'registry as _registry' "$INSTALLED/factory/cell/privileged.py"; then
    ok "контракт данных ищет репозиторий сам"
  else
    bad "правка не доехала — дальше идти нельзя, перенос Yummy снова откажет"
    exit 3
  fi
fi

log "шаг 2: недостающие юниты ячеек"
python3 "$REPO/automation/host/install-cell-units.py" ${dry_run:+--dry-run}
if [ -z "$dry_run" ]; then
  if [ -f /etc/systemd/system/nova-zonafilm-cc.service ] &&
     [ -f /etc/systemd/system/nova-zonafilm-cc-candidate.service ]; then
    ok "юниты zonafilm.cc на месте"
  else
    bad "юнитов zonafilm.cc нет"
    exit 3
  fi
fi

log "шаг 3: пути издателя, переживающие отсутствующий каталог"
bash "$REPO/automation/host/install-publisher-cell-paths.sh" ${dry_run:+--dry-run}
if [ -z "$dry_run" ]; then
  dashed="$(grep -hc '^ReadWritePaths=-' "$DROPIN_DIR"/*.conf 2>/dev/null | paste -sd+ | bc || echo 0)"
  if [ "${dashed:-0}" -ge 1 ]; then
    ok "путей с дефисом: $dashed"
  else
    bad "в drop-in нет ни одного пути с дефисом: 226/NAMESPACE вернётся"
    exit 3
  fi
fi

if [ -n "$launch" ]; then
  log "шаг 4: подключение нового домена $launch к хосту"
  bash "$REPO/automation/host/launch-new-site.sh" --site "$launch" $dry_run
fi

log "итог"
if [ -n "$dry_run" ]; then
  echo "   сухой прогон: ничего не менялось"
  exit 0
fi
cat <<'TAIL'
   Три блокировки сняты. Дальше — без root:

     python3 -m factory cell trigger --site yummy-biz --confirm-activation …
     python3 -m factory cell trigger --site zona-02  --confirm-activation …

   Суточное обновление запускается ОТДЕЛЬНОЙ командой, после того как я
   проверю, что переносы прошли:

     sudo systemctl start nova-daily-refresh.service
TAIL
