#!/usr/bin/env bash
# Выложить исправление доступности серий на ЧЕТЫРЕ витрины, которые не
# обслуживаются очередью ячеек.
#
#   sudo bash automation/host/apply-episode-availability-root.sh [--dry-run]
#
# Зачем нужен root. Тринадцать выложенных витрин семейств Lords, Zona и AnimeGo
# получили исправление штатной очередью (`factory cell trigger`) — она и
# выкладывает, и перезапускает. Эти четыре очередью не обслуживаются: их код
# лежит в /srv/<учётка>/app, каталог принадлежит учётной записи сайта или root,
# и сессия в него не пишет. Проверено: os.access(..., W_OK) = False у всех
# четырёх.
#
# Что именно исправлено (одинаково во всех четырёх):
#   доступность серии перестала выводиться из ОДНОГО числа `avail` и стала
#   множеством номеров. Спецвыпуск с номером 0 достижим, пропуски в нумерации
#   не скрывают последующие серии, серии сверх заявленного `eps` не прячутся.
#   Снимок без перечня `nums` ведёт себя в точности как раньше, поэтому выпуск
#   сам по себе не меняет ни одной страницы: перечень записывает фоновое
#   согласование `src/episode_sync.py` после старта.
#
# Подтверждено измерением на витринах, которые уже выложены: у `/title/skotty/`
# («Скотты», 01a0e27f-8175-7115-8972-83cce31b15d3) провайдер отдаёт РОВНО ОДНУ
# дорожку — season 1, episode 0. Страница обещала серию 1, провайдер отвечал
# noData, посетитель читал «Провайдер не отдал источник». После выпуска
# lordserial33.biz играет серию 0: readyState 4, длительность 1747 с, время
# дошло до 3.06 с.
#
# Сценарий НЕ меняет: DNS, firewall, sudoers, режим индексации, данные
# пользователей, каталоги контента и соседние сайты. Шаги независимы: провал
# одного не отменяет остальные.
set -Eeuo pipefail

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"

declare -a results=()

# Репозиторий каждой витрины и её юнит. Пути — рабочие копии этой сессии;
# каждая на своей ветке, изменения запушены.
# Имена переменных только ASCII: bash считает именем лишь [A-Za-z_][A-Za-z0-9_]*,
# и строка вида `имя=...` для него не присваивание, а вызов команды. `bash -n`
# такую строку пропускает — эта ошибка в проекте уже повторялась.
deploy_one() {
  local name="$1" repo="$2" unit="$3"
  log "$name"
  if [ ! -d "$repo" ]; then
    results+=("ОТКАЗ $name: нет рабочей копии $repo"); return 0
  fi
  # Сценарий выкладки называется по-разному: у AnimeGo это install.sh, у
  # Animedia — activate.sh. Берётся тот, что есть у ЭТОЙ витрины, а не один
  # на всех: жёсткое имя молча пропустило бы половину списка.
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
    results+=("ok    $name (сухой прогон)"); return 0
  fi
  if bash "$script"; then
    results+=("ok    $name")
  else
    results+=("ОТКАЗ $name: install.sh вернул ненулевой код")
  fi
}

deploy_one "an1mego.site (animego-02)" /home/claude/wt-an1mego-site nova-an1mego-site.service
deploy_one "animeg0.site (animego-03)" /home/claude/wt-animeg0-site nova-animeg0-site.service

# Animedia выкладывается своим сценарием: у неё код лежит в /srv/<учётка>/app и
# каталог принадлежит root.
FACTORY=/home/claude/wt-portable-site-cell-01/var/site-repos
deploy_one "animedia.icu (animedia-01)" "$FACTORY/animedia-icu" nova-animedia-icu.service
deploy_one "animedia.space (animedia-02)" "$FACTORY/animedia-space" nova-animedia-02.service

log "итог"
for line in "${results[@]}"; do printf '   %s\n' "$line"; done
if printf '%s\n' "${results[@]}" | grep -q '^ОТКАЗ'; then
  echo
  warn "часть шагов не выполнена — остальные применены, повтор безопасен"
  exit 1
fi
echo
log "готово. Проверить воспроизведение:"
echo "   node automation/host/playback-check.js https://an1mego.site stesnyashka-2 tikava"
echo "   node automation/host/playback-check.js https://animeg0.site stesnyashka-2"
echo "   node automation/host/playback-check.js https://animedia.icu stesnyashka-2"
echo "   node automation/host/playback-check.js https://animedia.space stesnyashka-2"
