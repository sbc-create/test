#!/usr/bin/env bash
# Завершить активацию animedia.icu: выдать витрине модератора и перезапустить.
#
# Что осталось после приёмки релиза community-public-03 и почему нужен root:
#
#   1. В юните нет ANIMEDIA_COMMUNITY_MODERATOR_KEY. Пустой ключ означает, что
#      модератора нет вовсе (а не что им является любой) — значит ни одно
#      сообщение на премодерации одобрить нельзя, и лента будет копить
#      неразобранное. Ключ кладётся в drop-in юнита, доступный только root.
#   2. Заголовок X-Site-Factory-Build-Id читается процессом при старте. Манифест
#      уже приведён к исполняемому релизу, но заголовок догонит только после
#      перезапуска.
#
# Скрипт трогает только animedia-01. Данные посетителей не читаются и не
# изменяются. Все имена переменных ASCII: кириллическое имя bash разбирает как
# команду, и `bash -n` это пропускает.
set -euo pipefail

UNIT=nova-animedia-01.service
DROPIN_DIR="/etc/systemd/system/$UNIT.d"
DROPIN="$DROPIN_DIR/community-moderator.conf"
KEYFILE=/etc/animedia/community-moderator.key
RELEASE_ID="20260923T001500Z-community-public-03"
DEPLOY="/home/claude/wt-community-comments-platform-01/automation/host/animedia-community-public-deploy.sh"

die() { printf '\nREFUSED: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "нужен root: drop-in юнита и перезапуск"

# Идемпотентно: существующий ключ не перевыпускается, иначе у владельца
# внезапно перестала бы работать уже выданная кука.
if [ -s "$KEYFILE" ]; then
  printf 'ключ модератора уже существует, оставлен как есть: %s\n' "$KEYFILE"
else
  install -d -m 0700 "$(dirname "$KEYFILE")"
  umask 077
  openssl rand -hex 32 > "$KEYFILE"
  chmod 0600 "$KEYFILE"
  printf 'ключ модератора создан: %s\n' "$KEYFILE"
fi
KEY=$(cat "$KEYFILE")

install -d -m 0755 "$DROPIN_DIR"
printf '[Service]\nEnvironment=ANIMEDIA_COMMUNITY_MODERATOR_KEY=%s\n' "$KEY" > "$DROPIN"
chmod 0600 "$DROPIN"
systemctl daemon-reload
systemctl restart "$UNIT"
sleep 3
systemctl is-active --quiet "$UNIT" || die "витрина не поднялась — откат: rm -f $DROPIN && systemctl daemon-reload && systemctl restart $UNIT"

BUILD=$(curl -sS -m 15 --resolve animedia.icu:443:127.0.0.1 -D - -o /dev/null \
  https://animedia.icu/ | awk 'tolower($1)=="x-site-factory-build-id:"{print $2}' | tr -d '\r')
printf 'заголовок build-id теперь: %s\n' "$BUILD"
[ "$BUILD" = "$RELEASE_ID" ] || printf 'ВНИМАНИЕ: заголовок не совпал с %s\n' "$RELEASE_ID"

printf '\nприёмка ещё раз, уже на перезапущенной витрине:\n'
bash "$DEPLOY"

cat <<SUM

Готово. Чтобы стать модератором, поставьте себе куку на animedia.icu:
  amd_mod=$KEY
Очередь «На проверке» появится на странице произведения; там же кнопки
«Одобрить» и «Отклонить».

Откат только этой правки (комментарии и оценки продолжат работать публично,
исчезнет только возможность модерировать):
  rm -f $DROPIN && systemctl daemon-reload && systemctl restart $UNIT
SUM
