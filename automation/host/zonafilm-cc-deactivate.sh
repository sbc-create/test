#!/usr/bin/env bash
# Откат активации zona-02 (zonafilm.cc). Данные витрины не удаляются.
#
# Останов службы и снятие vhost — обязательная часть, а не рекомендация:
# репетиция показала, что на освободившемся порту общий загрузчик уходит не в
# отказ, а в releases/legacy/current, и zonafilm.cc отдавал бы чужую
# легаси-витрину. Снять нужно оба, и в этом порядке.
#
# Сертификат не отзывается: он выпущен на имя владельца, и отзыв — отдельное
# решение. Запись DNS не трогается по той же причине.

set -euo pipefail

UNIT="nova-zona-02.service"
VHOST="/etc/nginx/lords/zona-02.conf"
UNIT_DST="/etc/systemd/system/$UNIT"

[ "$(id -u)" -eq 0 ] || { echo "нужен root" >&2; exit 1; }

if [ -f "$VHOST" ]; then
  rm -f "$VHOST"
  nginx -t
  systemctl reload nginx
  echo "снят vhost $VHOST, nginx перечитан"
else
  echo "vhost уже снят"
fi

if systemctl list-unit-files "$UNIT" >/dev/null 2>&1 && [ -f "$UNIT_DST" ]; then
  systemctl stop "$UNIT" || true
  systemctl disable "$UNIT" || true
  rm -f "$UNIT_DST"
  systemctl daemon-reload
  echo "остановлен, выключен и снят $UNIT"
else
  echo "юнит уже снят"
fi

echo
echo "Данные витрины оставлены: /srv/lords/.frontend/sites/zona-02/data"
echo "Повторная активация занимает секунды: sudo bash $(dirname "$0")/zonafilm-cc-activate.sh --apply"
