#!/usr/bin/env bash
# Вызвать на узле K2 выпуск кода витрин — обёртка над host-сценарием.
#
# Зачем обёртка. Сам сценарий живёт на узле (`/home/k2deploy/stage/`), и
# отсюда он доставляется и вызывается.
#
# Про права. Раньше здесь было написано, что полный режим требует root. Это
# перестало быть верным: измерено 2026-10-17 — учётная запись доставки состоит
# в группе КАЖДОЙ витрины, каталоги `/srv/<учётка>` и `.../releases` имеют
# режим `drwxrwsr-x` (групповая запись и setgid), а перезапуск юнита витрины
# прямо перечислен в `sudo -n -l`. Единственное, чего доставке не хватает
# против root, — `chown`; владельцем файлов выпуска остаётся доставка, группа
# достаётся витрине от setgid, и служба читает код по группе. Host-сценарий
# проверяет все три условия ДО первой записи и отказывается, если хоть одно не
# выполнено.
#
# Имена переменных только ASCII.
#
# Запуск:
#   k2-release-code.sh --dry-run <site_id> [site_id ...]
#   k2-release-code.sh --release <site_id> [site_id ...]
#   k2-release-code.sh --verify  <site_id> [site_id ...]
#   k2-release-code.sh --deliver                 только доставить сценарий
#
# --verify ничего не меняет: спрашивает у витрины подробный healthz по
# петле и сверяет путь исполняемого файла с каталогом, на который
# указывает `current`. Ответ «200 на порту» этого не доказывает: порт
# мог занять сосед, а служба — остаться на прежнем коде.
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
  --dry-run|--release|--verify) : ;;
  *) echo "[x] неизвестный режим $mode" >&2; exit 2 ;;
esac

sites="$*"
[ -n "$sites" ] || { echo "нужен хотя бы один site_id" >&2; exit 2; }
deliver || { echo "[x] доставка не удалась" >&2; exit 1; }

# Обзор не останавливается на первой неудаче: вопрос «какие витрины исполняют
# не тот выпуск» имеет смысл только целиком. Мутаций в этом режиме нет.
if [ "$mode" = "--verify" ]; then
  ok=0
  bad=0
  for site in $sites; do
    out="$(ansible -i "$inventory" "$host_ref" -m raw \
          -a "bash $script_dst $site --verify" 2>&1)"
    printf '%s\n' "$out" | grep -vE "^\[WARNING\]|interpreter_discovery|^$" \
      | grep -E "исполняется|НЕ ТОТ ВЫПУСК|не разобран|не прочитан|на порту|ШТАМП|штамп|цифра кода" \
      | sed 's/^/    /'
    if printf '%s' "$out" | grep -q "исполняется"; then
      ok=$((ok + 1))
    else
      bad=$((bad + 1))
    fi
  done
  echo "исполняют выложенный выпуск: $ok; расходятся: $bad"
  [ "$bad" = 0 ] || exit 1
  exit 0
fi

# Настоящий выпуск идёт по одной витрине и ОСТАНАВЛИВАЕТСЯ на первой неудаче:
# восемь одинаковых отказов подряд — это восемь раз один и тот же отказ, а
# разбираться нужно с первым.
if [ "$mode" = "--release" ]; then
  done_ok=0
  for site in $sites; do
    echo "=== $site"
    out="$(ansible -i "$inventory" "$host_ref" -m raw \
          -a "bash $script_dst $site" 2>&1)"
    printf '%s\n' "$out" | grep -vE "^\[WARNING\]|interpreter_discovery" | sed 's/^/    /'
    if printf '%s' "$out" | grep -qE "выпуск .* принят|выложена та же голова"; then
      done_ok=$((done_ok + 1))
    else
      echo "[x] $site: выпуск не принят — останавливаюсь"
      exit 1
    fi
  done
  echo "выпущено витрин: $done_ok"
  exit 0
fi

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
  echo "настоящий выпуск: bash automation/local/k2-release-code.sh --release $sites"
fi
[ "$bad" = 0 ] || exit 1
