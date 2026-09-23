#!/usr/bin/env bash
# Завершить активацию animedia.icu: выдать витрине модератора и перезапустить.
#
# Что осталось после приёмки релиза community-public-03 и почему нужен root:
#
#   1. В юните нет ANIMEDIA_COMMUNITY_MODERATOR_KEY. Пустой ключ означает, что
#      модератора нет вовсе (а не что им является любой) — значит ни одно
#      сообщение на премодерации одобрить нельзя, и лента копит неразобранное.
#      Ключ кладётся в drop-in юнита, доступный только root.
#   2. Заголовок X-Site-Factory-Build-Id читается процессом при старте. Манифест
#      уже приведён к исполняемому релизу, а заголовок догонит только после
#      перезапуска.
#
# Всё, что этот скрипт меняет, он умеет вернуть. Снимок прежней конфигурации
# снимается ДО первой правки, а восстановление висит на trap: ошибка записи,
# daemon-reload, перезапуска, готовности, build-id или приёмки возвращает
# прежний drop-in (или его отсутствие) и прежнее состояние службы.
#
# Чего скрипт не делает никогда: не перевыпускает существующий ключ, не удаляет
# drop-in, которого не создавал, не трогает данные посетителей и не переключает
# релиз — приёмка вызывается в режиме, который уже принятый релиз не двигает.
#
# Все имена переменных ASCII: кириллическое имя bash разбирает как команду, и
# `bash -n` это пропускает.
set -euo pipefail

UNIT=nova-animedia-01.service
RELEASE_ID="20260923T074500Z-community-one-vote-06"

: "${ETC_SYSTEMD:=/etc/systemd/system}"
: "${KEYFILE:=/etc/animedia/community-moderator.key}"
: "${STATE_DIR:=/srv/site-factory/var/comments}"
: "${SYSTEMCTL:=systemctl}"
: "${CURL:=curl}"
: "${REQUIRE_ROOT:=1}"
: "${READY_TIMEOUT:=60}"
: "${DEPLOY:=/home/claude/wt-community-comments-platform-01/automation/host/animedia-community-public-deploy.sh}"
: "${VERIFY:=/home/claude/wt-community-comments-platform-01/automation/host/animedia_verify_moderation.py}"

DROPIN_DIR="$ETC_SYSTEMD/$UNIT.d"
DROPIN="$DROPIN_DIR/community-moderator.conf"
STATE="$STATE_DIR/community-public-state.json"
SITE=https://animedia.icu
RESOLVE="animedia.icu:443:127.0.0.1"

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nREFUSED: %s\n' "$*" >&2; exit 1; }

if [ "$REQUIRE_ROOT" = "1" ] && [ "$(id -u)" -ne 0 ]; then
  die "нужен root: drop-in юнита и перезапуск"
fi
[ -x "$DEPLOY" ] || [ -f "$DEPLOY" ] || die "скрипт приёмки не найден: $DEPLOY"

# --- снимок прежнего состояния, до единой правки ---------------------------

say "снимок прежней конфигурации"
SNAP=$(mktemp -d)
DROPIN_EXISTED=0
DROPIN_DIR_EXISTED=0
if [ -d "$DROPIN_DIR" ]; then DROPIN_DIR_EXISTED=1; fi
if [ -f "$DROPIN" ]; then
  DROPIN_EXISTED=1
  cp -a "$DROPIN" "$SNAP/dropin"
  printf '   drop-in существовал, содержимое сохранено\n'
else
  printf '   drop-in отсутствовал\n'
fi
KEY_EXISTED=0
if [ -s "$KEYFILE" ]; then KEY_EXISTED=1; fi
ROLLBACK_BEFORE=""
if [ -f "$STATE" ]; then
  ROLLBACK_BEFORE=$(python3 -c "import json;print(json.load(open('$STATE'))['release_before'])" 2>/dev/null || echo "")
  printf '   точка отката релиза: %s\n' "$ROLLBACK_BEFORE"
fi
printf '   служба сейчас: %s\n' "$("$SYSTEMCTL" is-active "$UNIT" 2>/dev/null || echo unknown)"

MUTATED=0
SUCCEEDED=0

http_ready() {
  local code
  code=$("$CURL" -sS -m 10 --resolve "$RESOLVE" -o /dev/null -w '%{http_code}' \
    "$SITE/" 2>/dev/null || echo 000)
  [ "$code" = "200" ]
}

# Ограниченное ожидание вместо `sleep 3`: три секунды — это догадка о скорости
# запуска, а не признак готовности. Здесь ждём ровно до готовности и не дольше
# READY_TIMEOUT.
wait_ready() {
  local waited=0
  while [ "$waited" -lt "$READY_TIMEOUT" ]; do
    if "$SYSTEMCTL" is-active --quiet "$UNIT" && http_ready; then
      printf '   витрина готова через %s с\n' "$waited"
      return 0
    fi
    sleep 1
    waited=$((waited + 1))
  done
  printf '   витрина не пришла в готовность за %s с\n' "$READY_TIMEOUT" >&2
  return 1
}

restore() {
  printf '\n!! восстановление прежней конфигурации модератора\n' >&2
  if [ "$DROPIN_EXISTED" -eq 1 ]; then
    # Drop-in существовал: возвращается его содержимое. Безусловное удаление
    # стёрло бы чужую настройку, которой этот скрипт не владеет.
    cp -a "$SNAP/dropin" "$DROPIN"
    printf '   прежний drop-in возвращён\n' >&2
  else
    rm -f "$DROPIN"
    if [ "$DROPIN_DIR_EXISTED" -eq 0 ]; then
      rmdir --ignore-fail-on-non-empty "$DROPIN_DIR" 2>/dev/null || true
    fi
    printf '   созданный drop-in удалён\n' >&2
  fi
  # Ключ не удаляется никогда: он мог существовать до запуска, а выданная по
  # нему кука пережила бы этот откат.
  "$SYSTEMCTL" daemon-reload || true
  "$SYSTEMCTL" restart "$UNIT" || true
  wait_ready || printf '   ВНИМАНИЕ: витрина не подтвердила готовность после отката\n' >&2
}

on_exit() {
  local status=$?
  # Снимок удаляется ПОСЛЕ восстановления, а не до него: в нём лежит копия
  # прежнего drop-in, и убрать её раньше — значит остаться без того самого
  # содержимого, ради которого снимок и делался.
  if [ "$SUCCEEDED" -eq 1 ]; then
    rm -rf "$SNAP" 2>/dev/null || true
    return 0
  fi
  if [ "$MUTATED" -eq 0 ]; then
    printf '\nничего не менялось, восстанавливать нечего\n' >&2
    rm -rf "$SNAP" 2>/dev/null || true
    exit "$status"
  fi
  restore
  rm -rf "$SNAP" 2>/dev/null || true
  printf 'MODERATOR_ENABLE_FAILED\n' >&2
  exit "${status:-1}"
}
trap on_exit EXIT

# --- ключ ------------------------------------------------------------------

say "ключ модератора"
if [ "$KEY_EXISTED" -eq 1 ]; then
  printf '   существующий ключ оставлен как есть (%s)\n' "$KEYFILE"
else
  install -d -m 0700 "$(dirname "$KEYFILE")"
  ( umask 077; openssl rand -hex 32 > "$KEYFILE" )
  chmod 0600 "$KEYFILE"
  printf '   ключ создан: %s\n' "$KEYFILE"
fi
KEY=$(cat "$KEYFILE")
[ -n "$KEY" ] || die "ключ пуст — не буду включать модератора без ключа"

# --- drop-in ---------------------------------------------------------------

say "drop-in юнита"
install -d -m 0755 "$DROPIN_DIR"
MUTATED=1
printf '[Service]\nEnvironment=ANIMEDIA_COMMUNITY_MODERATOR_KEY=%s\n' "$KEY" > "$DROPIN" \
  || die "не удалось записать $DROPIN"
chmod 0600 "$DROPIN"
grep -q 'ANIMEDIA_COMMUNITY_MODERATOR_KEY=' "$DROPIN" || die "drop-in записан не полностью"
printf '   записан %s\n' "$DROPIN"

"$SYSTEMCTL" daemon-reload || die "daemon-reload не выполнен"
"$SYSTEMCTL" restart "$UNIT" || die "перезапуск не выполнен"
wait_ready || die "витрина не пришла в готовность"

# --- build-id --------------------------------------------------------------

say "объявленный релиз"
BUILD=$("$CURL" -sS -m 15 --resolve "$RESOLVE" -D - -o /dev/null "$SITE/" 2>/dev/null \
  | awk 'tolower($1)=="x-site-factory-build-id:"{print $2}' | tr -d '\r' || echo "")
printf '   заголовок build-id: %s\n' "${BUILD:-пусто}"
# Несовпадение — отказ, а не предупреждение: витрина, объявляющая не тот релиз,
# который исполняет, делает любой последующий отчёт непроверяемым.
[ "$BUILD" = "$RELEASE_ID" ] || die "заголовок build-id ($BUILD) не совпал с $RELEASE_ID"

# --- приёмка ---------------------------------------------------------------

say "приёмка на перезапущенной витрине"
ACCEPT_OUT="$SNAP/accept.txt"
if ! bash "$DEPLOY" > "$ACCEPT_OUT" 2>&1; then
  sed 's/^/   /' "$ACCEPT_OUT" >&2
  die "приёмка не пройдена"
fi
sed 's/^/   /' "$ACCEPT_OUT"

# Приёмка не должна двигать уже принятый релиз и переписывать точку отката.
grep -q '^SWITCHED=0' "$ACCEPT_OUT" || die "приёмка переключила релиз, хотя он уже принят"
if [ -n "$ROLLBACK_BEFORE" ]; then
  ROLLBACK_AFTER=$(python3 -c "import json;print(json.load(open('$STATE'))['release_before'])" 2>/dev/null || echo "")
  [ "$ROLLBACK_AFTER" = "$ROLLBACK_BEFORE" ] \
    || die "точка отката переписана: была $ROLLBACK_BEFORE, стала $ROLLBACK_AFTER"
  printf '   точка отката не тронута\n'
fi

# --- проверка модерации тремя ролями ---------------------------------------
#
# Включить модератора и не проверить, что он может одобрить, — значит отчитаться
# о работе, которой никто не видел. Ключ читается здесь же, под root, и никуда
# не печатается. Тестовое сообщение убирается за собой.
say "проверка модерации на живой витрине"
if [ -f "$VERIFY" ]; then
  if ! python3 "$VERIFY"; then
    die "проверка модерации не пройдена"
  fi
else
  printf '   ВНИМАНИЕ: %s не найден, модерация не проверена\n' "$VERIFY" >&2
fi

SUCCEEDED=1
cat <<SUM

Модератор включён.

Значение куки amd_mod лежит в $KEYFILE (root, 0600). Поставьте себе на
animedia.icu куку amd_mod с этим значением — на странице произведения появится
очередь «На проверке» с кнопками «Одобрить» и «Отклонить».

Откат только этой правки (комментарии и оценки продолжат работать публично,
исчезнет только возможность модерировать):
SUM
if [ "$DROPIN_EXISTED" -eq 1 ]; then
  printf '  восстановите прежнее содержимое %s и перезапустите %s\n' "$DROPIN" "$UNIT"
else
  printf '  rm -f %s && %s daemon-reload && %s restart %s\n' \
    "$DROPIN" "$SYSTEMCTL" "$SYSTEMCTL" "$UNIT"
fi
