#!/usr/bin/env bash
# Включить публичные комментарии и оценки на animedia.icu.
#
# ВСЕ имена переменных и функций здесь — ASCII, и это не стиль. Bash разбирает
# `ошибок=0` не как присваивание, а как ИМЯ КОМАНДЫ: имя переменной обязано
# быть [A-Za-z_][A-Za-z0-9_]*. Владелец получил ровно это —
# "line 83: ошибок=0: command not found" — уже ПОСЛЕ переключения ссылки,
# поэтому витрина осталась на новом релизе непроверенной. `bash -n` такую
# строку пропускает: как команда она синтаксически законна. Ловит только
# исполнение, поэтому рядом лежит репетиция (community_deploy_rehearsal.sh).
#
# Скрипт трогает только animedia-01. animedia.space (animedia-02), Zona, Lords
# и Yummy не упоминаются нигде, кроме проверки, что они не изменились.
set -euo pipefail

RELEASE_ID="20260923T090000Z-community-one-vote-07"

# Пути и команды вынесены в переменные с боевыми значениями по умолчанию:
# иначе скрипт нельзя прогнать ни в какой репетиции, а непрогоняемый скрипт
# и привёз этот сбой.
: "${FRONTEND_ROOT:=/srv/lords/.frontend}"
: "${STATE_DIR:=/srv/site-factory/var/comments}"
: "${SITE_DATA:=/srv/lords/animedia-01/data}"
: "${SYSTEMCTL:=systemctl}"
: "${CURL:=curl}"
: "${REQUIRE_ROOT:=1}"

RELEASE_DIR="$FRONTEND_ROOT/releases/$RELEASE_ID"
LINK="$FRONTEND_ROOT/sites/animedia-01/current"
LINK_SPACE="$FRONTEND_ROOT/sites/animedia-02/current"
STORE="$SITE_DATA/animedia-community.json"
STATE="$STATE_DIR/community-public-state.json"
# Публичный build-id читается ОТСЮДА, а не из каталога релиза. Оставить его
# нетронутым — значит заставить витрину объявлять релиз, который она не
# исполняет; ровно это и вышло при первом запуске.
MANIFEST="$FRONTEND_ROOT/template-manifest-animedia-01.json"
# Копия манифеста лежит рядом с ним, а не в каталоге состояния: каталог
# состояния принадлежит root, и приёмка без root спотыкалась именно об это.
MANIFEST_BACKUP="$MANIFEST.before-community-public"
UNIT=nova-animedia-01.service
RESOLVE="animedia.icu:443:127.0.0.1"
SITE=https://animedia.icu
TITLE=/title/master-lda-i-plameni-2/

say()  { printf '\n== %s\n' "$*"; }
die()  { printf '\nREFUSED: %s\n' "$*" >&2; exit 1; }

errors=0
check() {
  if [ "$2" = "yes" ]; then
    printf '   ok   %s\n' "$1"
  else
    printf '   FAIL %s\n' "$1"
    errors=$((errors + 1))
  fi
}

if [ "$REQUIRE_ROOT" = "1" ] && [ "$(id -u)" -ne 0 ]; then
  die "нужен root: переставить ссылку и перезапустить юнит"
fi
[ -d "$RELEASE_DIR" ] || die "релиз не найден: $RELEASE_DIR"

# Бракованный релиз не выкладывается, даже если на него указали руками.
# Метку ставит тот, кто нашёл дефект; снимать её выкладкой — не её дело.
if [ -f "$RELEASE_DIR/DO_NOT_DEPLOY.txt" ]; then
  sed 's/^/   /' "$RELEASE_DIR/DO_NOT_DEPLOY.txt" >&2
  die "релиз помечен как бракованный: $RELEASE_DIR/DO_NOT_DEPLOY.txt"
fi
[ -L "$LINK" ] || die "ожидалась символическая ссылка: $LINK"

say "состояние до"
CURRENT=$(basename "$(readlink -f "$LINK")")
SPACE_BEFORE=$(readlink "$LINK_SPACE" 2>/dev/null || echo "")
printf '   ссылка сейчас : %s\n' "$CURRENT"

SWITCHED=0
if [ "$CURRENT" = "$RELEASE_ID" ]; then
  # Уже выложен. Это не повод выйти: первый запуск умер ПОСЛЕ переключения и
  # ДО живой проверки, значит приёмка не выполнена. Повторный запуск её
  # доводит — не трогая ни витрину, ни записанную точку отката, ни резервную
  # копию данных. Переписать их здесь значило бы стереть точку возврата.
  printf '   релиз уже выложен — переключение пропускается, приёмка доводится\n'
  if [ -f "$STATE" ]; then
    BEFORE=$(python3 -c "import json;print(json.load(open('$STATE'))['release_before'])")
    printf '   точка отката из состояния: %s\n' "$BEFORE"
  else
    BEFORE=""
    printf '   точки отката нет: откат этим скриптом невозможен\n'
  fi
else
  BEFORE=$(readlink "$LINK")
  say "резервная копия данных сообщества"
  mkdir -p "$STATE_DIR"
  if [ -f "$STORE" ]; then
    cp -a "$STORE" "$STORE.before-community-public.$(date -u +%Y%m%dT%H%M%SZ)"
    printf '   скопировано: %s\n' "$STORE"
  else
    printf '   файла ещё нет, копировать нечего\n'
  fi
  printf '{"release_before":"%s","release_applied":"%s","unit":"%s","animedia_02_before":"%s"}\n' \
    "$BEFORE" "$RELEASE_ID" "$UNIT" "$SPACE_BEFORE" > "$STATE"

  say "переключение"
  if [ -f "$MANIFEST" ]; then
    cp -a "$MANIFEST" "$MANIFEST_BACKUP"
  else
    die "манифест витрины не найден: $MANIFEST"
  fi
  ln -sfn "../../releases/$RELEASE_ID" "$LINK"
  SWITCHED=1
  "$SYSTEMCTL" restart "$UNIT"
  sleep 3
fi

rollback_now() {
  printf '\n!! приёмка не пройдена — откат только этой выкладки\n' >&2
  if [ -z "$BEFORE" ]; then
    printf 'ОТКАТ НЕВОЗМОЖЕН: точка возврата не записана\n' >&2
    exit 3
  fi
  ln -sfn "$BEFORE" "$LINK"
  if [ -f "$MANIFEST_BACKUP" ]; then
    cp -a "$MANIFEST_BACKUP" "$MANIFEST"
    printf 'манифест возвращён\n' >&2
  fi
  "$SYSTEMCTL" restart "$UNIT" || true
  sleep 3
  printf 'ROLLED_BACK -> %s\n' "$BEFORE" >&2
  printf 'Данные посетителей сохранены в %s\n' "$STORE" >&2
  exit 2
}

say "согласование манифеста"
DECLARED_NOW=$(python3 -c "import json;print(json.load(open('$MANIFEST'))['build_id'])" 2>/dev/null || echo "")
if [ "$DECLARED_NOW" = "$RELEASE_ID" ]; then
  printf '   манифест уже объявляет %s\n' "$RELEASE_ID"
else
  if [ ! -f "$MANIFEST_BACKUP" ]; then
    cp -a "$MANIFEST" "$MANIFEST_BACKUP"
  fi
  python3 - "$MANIFEST" "$RELEASE_ID" "$RELEASE_DIR/RELEASE.json" <<'PYMAN'
import json, sys
manifest, build_id, release = sys.argv[1], sys.argv[2], sys.argv[3]
m = json.load(open(manifest, encoding="utf-8"))
r = json.load(open(release, encoding="utf-8"))
m["build_id"] = build_id
m["artifact_sha256"] = r["artifact_sha256"]
m["stage"] = "ANIMEDIA-COMMUNITY-PUBLIC-01"
json.dump(m, open(manifest, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PYMAN
  printf '   манифест приведён к %s (заголовок догонит после перезапуска)\n' "$RELEASE_ID"
fi

"$SYSTEMCTL" is-active --quiet "$UNIT" || rollback_now

say "живая проверка"
PAGE=$("$CURL" -sS -m 15 --resolve "$RESOLVE" "$SITE$TITLE" || true)
HEADERS=$("$CURL" -sS -m 15 --resolve "$RESOLVE" -D - -o /dev/null "$SITE$TITLE" || true)

case "$PAGE" in *'data-b07-player="1"'*) check "плеер на месте" yes;;
  *) check "плеер на месте" no;; esac
case "$PAGE" in *'data-community="on"'*) check "раздел сообщества включён" yes;;
  *) check "раздел сообщества включён" no;; esac
case "$PAGE" in *'name="csrf"'*) check "CSRF-токен в формах" yes;;
  *) check "CSRF-токен в формах" no;; esac
case "$PAGE" in *'data-comments-subject-kind="content-id"'*)
  check "ключ обсуждения — постоянный идентификатор" yes;;
  *) check "ключ обсуждения — постоянный идентификатор" no;; esac
case "$PAGE" in *'data-comments-space="animedia-01"'*)
  check "пространство — конкретная витрина" yes;;
  *) check "пространство — конкретная витрина" no;; esac
case "$HEADERS" in *[Nn]oindex*) check "noindex сохранён" yes;;
  *) check "noindex сохранён" no;; esac

for path in / /catalog/; do
  code=$("$CURL" -sS -m 15 --resolve "$RESOLVE" -o /dev/null -w '%{http_code}' \
    "$SITE$path" || true)
  if [ "$code" = "200" ]; then check "$path отвечает 200" yes
  else check "$path отвечает 200" no; fi
done

SPACE_NOW=$(readlink "$LINK_SPACE" 2>/dev/null || echo "")
if [ "$SPACE_NOW" = "$SPACE_BEFORE" ]; then check "animedia.space не изменён" yes
else check "animedia.space не изменён" no; fi

if [ -f "$STORE" ]; then check "хранилище записей на месте" yes
else check "хранилище записей на месте" no; fi

RUNNING=$(basename "$(readlink -f "$LINK")")
DECLARED=$(python3 -c "import json;print(json.load(open('$MANIFEST'))['build_id'])" 2>/dev/null || echo "")
if [ "$RUNNING" = "$DECLARED" ]; then check "манифест объявляет исполняемый релиз" yes
else
  printf '   note исполняет %s, объявляет %s\n' "$RUNNING" "$DECLARED"
  check "манифест объявляет исполняемый релиз" no
fi

if [ "$errors" -ne 0 ]; then
  if [ "$SWITCHED" = "1" ] || [ -n "$BEFORE" ]; then
    rollback_now
  fi
  printf '\nприёмка не пройдена, откатывать нечего\n' >&2
  exit 2
fi

say "приёмка пройдена"
cat <<SUM
RELEASE=$RELEASE_ID
SWITCHED=$SWITCHED
ROLLBACK_POINT=${BEFORE:-нет}
STATE=$STATE
STORE=$STORE
Откат вручную: ln -sfn "${BEFORE:-<точка отката>}" "$LINK" && $SYSTEMCTL restart $UNIT
Модератор: ANIMEDIA_COMMUNITY_MODERATOR_KEY в юните + кука amd_mod с тем же значением.
SUM
