#!/usr/bin/env bash
# Замена секрета, который получает служба через LoadCredential.
#
#   sudo bash automation/host/rotate-credential.sh --path <файл> --unit <служба>
#   sudo bash automation/host/rotate-credential.sh --path <файл> --unit <служба> --from-file <файл>
#
# Почему отдельный сценарий, а не «положить файл руками»
# ------------------------------------------------------
#
# Секрет, переданный АРГУМЕНТОМ команды, попадает в три места сразу: в вывод
# `ps`, в историю оболочки и — если команда шла через sudo — в `auth.log`,
# который читают по другим правилам, чем каталог секретов. Именно так секреты и
# утекают: не взломом, а строкой в журнале, которую никто не собирался писать.
#
# Здесь значение не бывает аргументом ни при каких условиях: либо ввод без эха,
# либо готовый файл по пути. Оно не печатается, не логируется и не сравнивается
# вслух — сценарий отвечает только «совпало/не совпало» отпечатками.
#
# Прежнее значение сохраняется рядом с отметкой времени и правами 0600: без
# него нельзя проверить, что старый ключ ОТКЛОНЯЕТСЯ, а не просто заменён.
# Журналы при этом не трогаются: сокрытие утечки — не часть замены.
set -Eeuo pipefail
umask 077

path=""
unit=""
source_file=""
while [ $# -gt 0 ]; do
  case "$1" in
    --path) path="${2:-}"; shift ;;
    --unit) unit="${2:-}"; shift ;;
    --from-file) source_file="${2:-}"; shift ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$path" ] || { echo "нужен --path" >&2; exit 2; }
[ -n "$unit" ] || { echo "нужен --unit" >&2; exit 2; }

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" = 0 ] || die "нужен root"
systemctl cat "$unit" >/dev/null 2>&1 || die "службы $unit нет"
systemctl cat "$unit" | grep -q "LoadCredential=.*:${path}\$\|LoadCredential=.*:${path}[[:space:]]" \
  || die "служба $unit не получает секрет по пути $path — замена не туда"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="${path}.replaced-${stamp}"

if [ -n "$source_file" ]; then
  [ -r "$source_file" ] || die "не читается $source_file"
  tmp="$(mktemp "$(dirname "$path")/.cred.XXXXXX")"
  tr -d '\r\n' < "$source_file" > "$tmp"
else
  echo "Вставьте новое значение и нажмите Enter. Оно не отображается,"
  echo "не попадает в историю команд и не бывает аргументом."
  IFS= read -rs value || die "ввод прерван"
  echo
  tmp="$(mktemp "$(dirname "$path")/.cred.XXXXXX")"
  printf '%s' "$value" | tr -d '\r\n' > "$tmp"
  unset value
fi

[ -s "$tmp" ] || { rm -f "$tmp"; die "пустое значение — ничего не менялось"; }

# Отпечатки, а не значения: по ним видно, что ключ действительно сменился, и
# ни одно из значений при этом не показано.
new_fp="$(sha256sum "$tmp" | cut -c1-16)"
if [ -f "$path" ]; then
  old_fp="$(sha256sum "$path" | cut -c1-16)"
  if [ "$old_fp" = "$new_fp" ]; then
    rm -f "$tmp"
    die "новое значение совпадает с прежним — это не замена"
  fi
  cp -p "$path" "$archive"
  chmod 0600 "$archive"
  log "прежнее значение сохранено: $archive (отпечаток ${old_fp})"
fi

chown root:root "$tmp"
chmod 0600 "$tmp"
mv "$tmp" "$path"
log "новое значение записано в $path (отпечаток ${new_fp})"

log "перезапуск $unit — credential читается при старте"
systemctl restart "$unit"
systemctl is-active --quiet "$unit" || die "служба не поднялась после замены"
log "служба активна"

cat <<ГОТОВО

Замена выполнена. Значение нигде не выведено.

Осталось проверить ДЕЙСТВИЕМ, а не тем, что файл изменился:
  — старый ключ отклоняется:  повторить операцию модератора со старым
    значением из ${archive};
  — новый ключ работает:      выполнить операцию модератора с новым.

Журналы не трогались. Утечка в auth.log остаётся в журнале намеренно:
удалять её — скрывать событие, а не устранять его.
ГОТОВО
