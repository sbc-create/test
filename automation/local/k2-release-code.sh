#!/usr/bin/env bash
# Вызвать на узле K2 выпуск кода витрин — обёртка над host-сценарием.
#
# Зачем обёртка. Сам сценарий живёт на узле (`/home/k2deploy/stage/`), и его
# полный режим требует root. Отсюда делаются две вещи, которые root не требуют:
# доставка сценария и СУХОЙ прогон — он сверяет опись, бандл, плеер и голову
# выложенного выпуска, ничего не меняя. Полный режим печатается готовой
# строкой для владельца, а не выполняется украдкой.
#
# Имена переменных только ASCII.
#
# Запуск:
#   k2-release-code.sh --dry-run <site_id> [site_id ...]
#   k2-release-code.sh --deliver                 только доставить сценарий
set -uo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
inventory="$repo_root/var/ansible/hosts.yml"
host_ref="k2-zomro-01"
stage="/home/k2deploy/stage"
script_src="$repo_root/automation/host/k2-release-code.sh"
script_dst="$stage/k2-release-code.sh"

deliver() {
  ansible -i "$inventory" "$host_ref" -m copy \
    -a "src=$script_src dest=$script_dst mode=0755" >/dev/null || return 1
  echo "сценарий доставлен: $script_dst"
}

mode="${1:?нужен --dry-run или --deliver}"
shift || true

case "$mode" in
  --deliver)
    deliver || { echo "[x] доставка не удалась" >&2; exit 1; }
    exit 0
    ;;
  --dry-run) : ;;
  *) echo "[x] неизвестный режим $mode" >&2; exit 2 ;;
esac

sites="$*"
[ -n "$sites" ] || { echo "нужен хотя бы один site_id" >&2; exit 2; }
deliver || { echo "[x] доставка не удалась" >&2; exit 1; }

ok=0
bad=0
for site in $sites; do
  out="$(ansible -i "$inventory" "$host_ref" -m raw \
        -a "bash $script_dst $site --dry-run" 2>&1)"
  if printf '%s' "$out" | grep -q "ничего не менялось"; then
    line="$(printf '%s' "$out" | grep "сухой прогон" | head -1)"
    echo "$site: ${line#*сухой прогон: }"
    ok=$((ok + 1))
  elif printf '%s' "$out" | grep -q "выложена та же голова"; then
    echo "$site: выложена та же голова — выпуск не нужен"
    ok=$((ok + 1))
  else
    echo "[x] $site:"
    printf '%s\n' "$out" | tail -4 | sed 's/^/    /'
    bad=$((bad + 1))
  fi
done

echo "сверено витрин: $ok; отказов: $bad"
if [ "$ok" -gt 0 ]; then
  echo
  echo "полный режим требует root НА УЗЛЕ. Команда владельцу, по витрине:"
  for site in $sites; do
    echo "  sudo $script_dst $site"
  done
fi
[ "$bad" = 0 ] || exit 1
