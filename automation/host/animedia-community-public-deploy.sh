#!/usr/bin/env bash
# Включить публичные комментарии и оценки на animedia.icu.
#
# Одна команда владельца. Всё, что можно было проверить без root, проверено:
# 984 модульных теста и 40 сценариев обычного посетителя и модератора по
# настоящему HTTP на отдельном порту (automation/host/community_public_shadow_verify.py).
# Здесь остаётся то, что требует root: переставить ссылку и перезапустить юнит.
#
# Скрипт трогает только animedia-01. animedia.space (animedia-02), Zona, Lords
# и Yummy не упоминаются нигде, кроме проверки, что они не изменились.
set -euo pipefail

RELEASE_ID="20260922T223000Z-community-public-01"
RELEASE_DIR="/srv/lords/.frontend/releases/$RELEASE_ID"
LINK=/srv/lords/.frontend/sites/animedia-01/current
UNIT=nova-animedia-01.service
STORE=/srv/lords/animedia-01/data/animedia-community.json
RESOLVE="animedia.icu:443:127.0.0.1"
SITE=https://animedia.icu
TITLE=/title/master-lda-i-plameni-2/
STATE=/srv/site-factory/var/comments/community-public-state.json

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nREFUSED: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "нужен root: переставить ссылку и перезапустить юнит"
[ -d "$RELEASE_DIR" ] || die "релиз не найден: $RELEASE_DIR"
[ -L "$LINK" ] || die "ожидалась символическая ссылка: $LINK"

say "состояние до"
BEFORE=$(readlink "$LINK")
BASE_DECLARED=$(basename "$(readlink -f "$LINK")")
BASE_OF_RELEASE=$(python3 -c "
import json;print(json.load(open('$RELEASE_DIR/RELEASE.json'))['rebased_onto']['build_id'])")
printf '   ссылка сейчас : %s\n' "$BEFORE"
printf '   релиз собран от: %s\n' "$BASE_OF_RELEASE"
[ "$BASE_DECLARED" = "$BASE_OF_RELEASE" ] || die \
  "релиз собран от $BASE_OF_RELEASE, а витрина объявляет $BASE_DECLARED — пересоберите адаптер"

# Данные посетителей — оценки и сообщения — переживают выкладку и откат.
say "резервная копия данных сообщества"
mkdir -p "$(dirname "$STATE")"
if [ -f "$STORE" ]; then
  cp -a "$STORE" "$STORE.before-community-public.$(date -u +%Y%m%dT%H%M%SZ)"
  printf '   скопировано: %s\n' "$STORE"
else
  printf '   файла ещё нет — копировать нечего\n'
fi
SPACE_BEFORE=$(readlink /srv/lords/.frontend/sites/animedia-02/current)
printf '{"release_before":"%s","release_applied":"%s","unit":"%s","animedia_02_before":"%s"}\n' \
  "$BEFORE" "$RELEASE_ID" "$UNIT" "$SPACE_BEFORE" > "$STATE"

откат() {
  printf '\n!! проверка не прошла — откат только этой выкладки\n' >&2
  ln -sfn "$BEFORE" "$LINK"
  systemctl restart "$UNIT" || true
  sleep 3
  printf 'ROLLED_BACK -> %s (данные посетителей не тронуты)\n' "$BEFORE" >&2
  exit 2
}

say "переключение"
ln -sfn "../../releases/$RELEASE_ID" "$LINK"
systemctl restart "$UNIT"
sleep 3
systemctl is-active --quiet "$UNIT" || откат

say "живая проверка"
ошибок=0
проверить() {
  if [ "$2" = "да" ]; then printf '   ok   %s\n' "$1"
  else printf '   FAIL %s\n' "$1"; ошибок=$((ошибок + 1)); fi
}

СТР=$(curl -sS -m 15 --resolve "$RESOLVE" "$SITE$TITLE" || true)
ЗАГ=$(curl -sS -m 15 --resolve "$RESOLVE" -D - -o /dev/null "$SITE$TITLE" || true)

case "$СТР" in *'data-b07-player="1"'*) проверить "плеер на месте" да;;
  *) проверить "плеер на месте" нет;; esac
case "$СТР" in *'data-community="on"'*) проверить "раздел сообщества включён" да;;
  *) проверить "раздел сообщества включён" нет;; esac
case "$СТР" in *'name="csrf"'*) проверить "CSRF-токен в формах" да;;
  *) проверить "CSRF-токен в формах" нет;; esac
case "$ЗАГ" in *[Nn]oindex*) проверить "noindex сохранён" да;;
  *) проверить "noindex сохранён" нет;; esac
case "$ЗАГ" in *"$RELEASE_ID"*) проверить "выложен именно этот релиз" да;;
  *) проверить "выложен именно этот релиз" нет;; esac
for путь in / /catalog/; do
  код=$(curl -sS -m 15 --resolve "$RESOLVE" -o /dev/null -w '%{http_code}' "$SITE$путь" || true)
  [ "$код" = "200" ] && проверить "$путь отвечает 200" да || проверить "$путь отвечает 200" нет
done
СЕЙЧАС=$(readlink /srv/lords/.frontend/sites/animedia-02/current)
[ "$СЕЙЧАС" = "$SPACE_BEFORE" ] && проверить "animedia.space не изменён" да \
  || проверить "animedia.space не изменён" нет

[ "$ошибок" -eq 0 ] || откат

say "готово"
cat <<SUM
RELEASE=$RELEASE_ID
BEFORE=$BEFORE
STATE=$STATE
Откат вручную: ln -sfn "$BEFORE" $LINK && systemctl restart $UNIT
Модератор: задайте ANIMEDIA_COMMUNITY_MODERATOR_KEY в юните и поставьте себе
куку amd_mod с тем же значением; очередь появится на странице произведения.
Данные посетителей (оценки и сообщения) лежат в $STORE и выкладкой не трогаются.
SUM
