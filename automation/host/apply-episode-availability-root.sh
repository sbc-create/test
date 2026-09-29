#!/usr/bin/env bash
# Выложить исправление доступности серий на ЧЕТЫРЕ витрины, которые не
# обслуживаются очередью ячеек.
#
#   sudo bash automation/host/apply-episode-availability-root.sh [--dry-run]
#
# Зачем нужен root. Восемь витрин Lords, Zona и AnimeGo получают исправление
# штатной очередью (`factory cell trigger`) — она и выкладывает, и
# перезапускает. Эти четыре очередью не обслуживаются: их код лежит в
# /srv/<учётка>/app, каталог принадлежит учётной записи сайта или root, и
# сессия в него не пишет (проверено: os.access(..., W_OK) = False у всех).
#
# Что было в прошлый раз, 2026-09-29 около 07:03. Прогон сделал две витрины из
# четырёх: an1mego.site и animeg0.site перезапустились и работают на
# исправлении. animedia.space получил файлы, но остался на прежнем процессе —
# служба не перезапускалась с 15:54 предыдущего дня, то есть исполняла старый
# код из памяти. animedia.icu не получил и файлов. Поэтому здесь добавлены
# явный перезапуск и ПРОВЕРКА результата: молчаливый успех сценария больше не
# считается выкладкой.
#
# Имена юнитов исправлены. Прежняя версия называла nova-animedia-02.service —
# этот юнит запускает ОБЩИЙ загрузчик /srv/lords/.frontend/lords-frontend.py,
# а витрину из своего каталога поднимают nova-animedia-icu.service и
# nova-animedia-space.service. Перезапуск не того юнита выглядел бы успехом.
#
# Что именно выкладывается: доступность серии — множество номеров вместо
# одного числа `avail`; спецвыпуск с номером 0 достижим; проверенные номера
# живут в `<снимок>.nums.json` и переживают суточную доставку; потерянные
# сезоны восстанавливаются из плейлиста там, где нумерация сходится.
#
# Сценарий НЕ меняет: DNS, firewall, sudoers, режим индексации, данные
# пользователей, каталоги контента и соседние сайты. Шаги независимы.
set -Eeuo pipefail

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"

REPORT=/var/log/episode-availability-rollout.json
declare -a results=()

# Имена переменных только ASCII: bash считает именем лишь [A-Za-z_][A-Za-z0-9_]*,
# и строка вида `имя=...` для него не присваивание, а вызов команды.
deploy_one() {
  local name="$1" repo="$2" unit="$3" port="$4"
  log "$name"
  if [ ! -d "$repo" ]; then
    results+=("ОТКАЗ $name: нет рабочей копии $repo"); return 0
  fi
  local script=""
  for candidate in install.sh activate.sh; do
    [ -f "$repo/deploy/$candidate" ] && { script="$repo/deploy/$candidate"; break; }
  done
  if [ -z "$script" ]; then
    results+=("ОТКАЗ $name: в $repo/deploy нет ни install.sh, ни activate.sh"); return 0
  fi

  if [ "$dry_run" = 1 ]; then
    echo "   [сухой прогон] bash $script"
    echo "   [сухой прогон] systemctl restart $unit"
    echo "   [сухой прогон] проверка сборки на 127.0.0.1:$port"
    results+=("ok    $name (сухой прогон)"); return 0
  fi

  local before after
  before=$(curl -s -m 8 "http://127.0.0.1:$port/" 2>/dev/null \
           | grep -o 'data-build-id="[^"]*"' | head -1 || true)
  if ! bash "$script"; then
    results+=("ОТКАЗ $name: $(basename "$script") вернул ненулевой код"); return 0
  fi
  # Перезапуск отдельно и всегда: сценарий выкладки мог только разложить файлы,
  # а рантайм читает их при старте. Ровно так animedia.space и осталась на
  # старом коде при новых файлах.
  systemctl restart "$unit" || {
    results+=("ОТКАЗ $name: $unit не перезапустился"); return 0; }
  sleep 6
  after=$(curl -s -m 15 "http://127.0.0.1:$port/" 2>/dev/null \
          | grep -o 'data-build-id="[^"]*"' | head -1 || true)
  if [ -z "$after" ]; then
    results+=("ОТКАЗ $name: после перезапуска витрина не ответила на :$port"); return 0
  fi
  if [ "$before" = "$after" ]; then
    results+=("ВНИМАНИЕ $name: сборка не изменилась ($after) — проверьте, тот ли каталог")
    return 0
  fi
  results+=("ok    $name: $before -> $after")
}

FACTORY=/home/claude/wt-portable-site-cell-01/var/site-repos
deploy_one "an1mego.site (animego-02)"   /home/claude/wt-an1mego-site  nova-an1mego-site.service  9150
deploy_one "animeg0.site (animego-03)"   /home/claude/wt-animeg0-site  nova-animeg0-site.service  9151
deploy_one "animedia.icu (animedia-01)"  "$FACTORY/animedia-icu"       nova-animedia-icu.service   9121
deploy_one "animedia.space (animedia-02)" "$FACTORY/animedia-space"    nova-animedia-space.service 9122

log "итог"
for line in "${results[@]}"; do printf '   %s\n' "$line"; done
if [ "$dry_run" = 0 ]; then
  printf '{"at": "%s", "results": [' "$(date -Is)" > "$REPORT"
  sep=""
  for line in "${results[@]}"; do
    printf '%s"%s"' "$sep" "$(printf '%s' "$line" | sed 's/"/\\"/g')" >> "$REPORT"
    sep=", "
  done
  printf ']}\n' >> "$REPORT"
  echo
  log "итог записан в $REPORT — его читает сессия, журнала ей не видно"
fi
if printf '%s\n' "${results[@]}" | grep -q '^ОТКАЗ'; then
  echo
  warn "часть шагов не выполнена — остальные применены, повтор безопасен"
  exit 1
fi
