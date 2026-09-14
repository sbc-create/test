#!/bin/bash
# Загрузчик транзакции закрепления. Исполняется владельцем от root.
#
# Задача загрузчика — довести управление до проверенного установщика, не
# исполнив по дороге ни одного файла, который мог бы подменить агент. Всё, что
# он делает до первой проверки хешей, обязано быть неизменяемым системным
# бинарником по абсолютному пути.
#
# Почему не «просто запустить установщик из репозитория»: репозиторий
# принадлежит `claude`. Запуск оттуда от root — ровно тот дефект, который
# транзакция закрывает. Поэтому: выгрузить → проверить → скопировать в
# root-owned каталог → проверить ещё раз → и только теперь исполнить.
#
# Почему выгрузка из git идёт от непривилегированного пользователя: `git`
# читает конфигурацию, `replace`-объекты, grafts и alternates из самого
# репозитория и из окружения. Это большая поверхность, и запускать её от root
# незачем — содержимое всё равно проверяется по sha256 после выгрузки, а
# понижение прав убирает целый класс вопросов.
set -euo pipefail

# --- абсолютные пути: PATH не участвует в решении, что исполнится ---------
readonly GIT=/usr/bin/git
readonly TAR=/bin/tar
readonly INSTALL=/usr/bin/install
readonly SHA256SUM=/usr/bin/sha256sum
readonly MKTEMP=/bin/mktemp
readonly RM=/bin/rm
readonly ID=/usr/bin/id
readonly SETPRIV=/usr/bin/setpriv
readonly BASH=/bin/bash
readonly CHOWN=/bin/chown
readonly CHMOD=/bin/chmod
readonly FIND=/usr/bin/find
readonly STAT=/usr/bin/stat

say()  { printf '[bootstrap] %s\n' "$*"; }
fail() { printf '[bootstrap] ОТКАЗ: %s\n' "$*" >&2; exit 1; }

for binary in "$GIT" "$TAR" "$INSTALL" "$SHA256SUM" "$MKTEMP" "$RM" "$ID" \
              "$BASH" "$CHOWN" "$CHMOD" "$FIND" "$STAT"; do
  [ -x "$binary" ] || fail "нет системного бинарника $binary"
  owner="$("$STAT" -c '%U' "$binary")"
  [ "$owner" = "root" ] || fail "$binary принадлежит $owner, а не root"
done

[ "$("$ID" -u)" = "0" ] || fail "запускается только от root"

# --- параметры транзакции: подставляются владельцем из отчёта -------------
SOURCE_COMMIT="${SFH_COMMIT:-}"
EXPECT_INSTALLER="${SFH_INSTALLER_SHA256:-}"
EXPECT_RELEASE="${SFH_RELEASE_SHA256:-}"
EXPECT_PROVENANCE="${SFH_PROVENANCE_SHA256:-}"
EXPECT_MANIFEST="${SFH_MANIFEST_SHA256:-}"
EXPECT_AGGREGATE="${SFH_AGGREGATE_SHA256:-}"
SOURCE_REPO="${SFH_SOURCE_REPO:-/srv/site-factory/repo}"
UNPRIV_USER="${SFH_UNPRIV_USER:-claude}"
PASSTHROUGH="${SFH_ARGS:-}"

for required in SOURCE_COMMIT EXPECT_INSTALLER EXPECT_RELEASE EXPECT_PROVENANCE \
                EXPECT_MANIFEST EXPECT_AGGREGATE; do
  [ -n "${!required}" ] || fail "не задан ${required}: все хеши приходят из отчёта, а не из репозитория"
done
case "$SOURCE_COMMIT" in
  *[!0-9a-f]* | "") fail "SFH_COMMIT обязан быть полным hex-хешем коммита" ;;
esac
[ "${#SOURCE_COMMIT}" = "40" ] || fail "SFH_COMMIT обязан быть полным 40-символьным хешем"

# --- новый уникальный root-owned staging ---------------------------------
# Каждый запуск получает свой каталог: переиспользование означало бы, что в нём
# может лежать что-то от прошлого раза, и проверять пришлось бы ещё и это.
STAGE_ROOT=/root/site-factory-hardening
"$INSTALL" -d -m 0700 -o root -g root "$STAGE_ROOT"
STAGE="$("$MKTEMP" -d "${STAGE_ROOT}/txn-XXXXXXXXXXXX")"
"$CHOWN" root:root "$STAGE"
"$CHMOD" 0700 "$STAGE"
say "staging: $STAGE (root:root 0700, создан этим запуском)"

cleanup() { [ -n "${STAGE:-}" ] && "$RM" -rf -- "$STAGE" || true; }
trap 'cleanup' ERR

# --- выгрузка из git от непривилегированного пользователя ----------------
# Влияние пользовательской конфигурации, replace-объектов, grafts и alternates
# выключается явно. Любой из них способен подменить содержимое, которое git
# отдаст по имени коммита, не меняя самого имени.
EXPORT_DIR="${STAGE}/export"
"$INSTALL" -d -m 0755 -o root -g root "$EXPORT_DIR"
"$CHOWN" "${UNPRIV_USER}:${UNPRIV_USER}" "$EXPORT_DIR"

GIT_ENV=(
  "GIT_CONFIG_GLOBAL=/dev/null"
  "GIT_CONFIG_SYSTEM=/dev/null"
  "GIT_CONFIG_NOSYSTEM=1"
  "GIT_NO_REPLACE_OBJECTS=1"
  "GIT_ALTERNATE_OBJECT_DIRECTORIES="
  "GIT_GRAFT_FILE=/dev/null"
  "GIT_ATTR_NOSYSTEM=1"
  "GIT_TERMINAL_PROMPT=0"
  "HOME=/nonexistent"
)

say "выгрузка ${SOURCE_COMMIT:0:12} из ${SOURCE_REPO} от имени ${UNPRIV_USER}"
if [ -x "$SETPRIV" ]; then
  env -i "${GIT_ENV[@]}" "$SETPRIV" --reuid="$UNPRIV_USER" --regid="$UNPRIV_USER" \
      --clear-groups --no-new-privs \
      "$GIT" -C "$SOURCE_REPO" --no-replace-objects \
      -c "safe.directory=${SOURCE_REPO}" \
      archive --format=tar "$SOURCE_COMMIT" automation/hardening \
    > "${STAGE}/export.tar" || fail "выгрузка не удалась"
else
  fail "нет ${SETPRIV}: понижение прав для выгрузки невозможно, а выгружать от root не станем"
fi

"$TAR" -xf "${STAGE}/export.tar" -C "$EXPORT_DIR" --no-same-owner --no-same-permissions \
  || fail "распаковка выгрузки не удалась"
"$CHOWN" -R root:root "$EXPORT_DIR"
"$FIND" "$EXPORT_DIR" -type d -exec "$CHMOD" 0755 {} +
"$FIND" "$EXPORT_DIR" -type f -exec "$CHMOD" 0644 {} +

H="${EXPORT_DIR}/automation/hardening"
INSTALLER="${H}/pin-root-units.sh"
RELEASE="${H}/release/release.json"
PROVENANCE="${H}/release/provenance.json"
MANIFEST="${H}/manifest.json"

# --- независимая проверка ВСЕХ управляющих файлов до первого исполнения ---
# Значения приходят из отчёта владельца, а не из выгруженного дерева: файл,
# который проверяет сам себя, не проверяет ничего.
verify() {
  local path="$1" expect="$2" label="$3"
  [ -f "$path" ] || fail "нет ${label}: ${path}"
  local got
  got="$("$SHA256SUM" "$path" | cut -d' ' -f1)"
  [ "$got" = "$expect" ] || fail "sha256 ${label} не совпал:
  ожидался $expect
  получен  $got
  Транзакция остановлена ДО единого изменения системы."
  say "sha256 ${label}: совпал"
}

verify "$INSTALLER"   "$EXPECT_INSTALLER"   "установщика"
verify "$RELEASE"     "$EXPECT_RELEASE"     "release.json"
verify "$PROVENANCE"  "$EXPECT_PROVENANCE"  "provenance.json"
verify "$MANIFEST"    "$EXPECT_MANIFEST"    "manifest.json"

# Совокупный отпечаток сверяется с ЛИТЕРАЛОМ из команды владельца, а не с тем,
# что записано в release.json: иначе подменённая пара файлов сошлась бы сама с
# собой.
AGG_IN_FILE="$(/usr/bin/python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["aggregate_sha256"])' "$RELEASE")"
[ "$AGG_IN_FILE" = "$EXPECT_AGGREGATE" ] \
  || fail "совокупный отпечаток в release.json (${AGG_IN_FILE}) не совпал с ожидаемым из команды (${EXPECT_AGGREGATE})"
say "совокупный отпечаток: совпал с литералом из команды"

# --- исполнение проверенного установщика из root-owned каталога ----------
"$CHMOD" 0700 "$INSTALLER"
say "передаю управление установщику"
trap - ERR
# shellcheck disable=SC2086
exec "$BASH" "$INSTALLER" \
  --release="$RELEASE" \
  --provenance="$PROVENANCE" \
  --manifest="$MANIFEST" \
  --source-repo="$SOURCE_REPO" \
  --stage="$STAGE" \
  $PASSTHROUGH
