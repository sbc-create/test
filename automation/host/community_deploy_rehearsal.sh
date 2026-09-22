#!/usr/bin/env bash
# Репетиция выкладки в песочнице: скрипт ИСПОЛНЯЕТСЯ, а не только разбирается.
#
# Нужна потому, что `bash -n` пропустил `ошибок=0` — кириллическое имя
# переменной разбирается как имя команды, и это синтаксически законно. Сбой
# случился у владельца, уже после переключения ссылки. Единственное, что ловит
# такое, — запуск.
#
# Три сценария: успех, принудительный отказ живой проверки, повторный запуск
# после частичного выполнения.
set -uo pipefail

SCRIPT="$(cd "$(dirname "$0")" && pwd)/animedia-community-public-deploy.sh"
RELEASE_ID="20260923T001500Z-community-public-03"
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT

fails=0
report() {
  if [ "$2" = "yes" ]; then printf '   ok   %s\n' "$1"
  else printf '   FAIL %s\n' "$1"; fails=$((fails + 1)); fi
}

make_sandbox() {
  rm -rf "$ROOT/box"
  mkdir -p "$ROOT/box/front/releases/$RELEASE_ID" \
           "$ROOT/box/front/releases/old-release" \
           "$ROOT/box/front/sites/animedia-01" \
           "$ROOT/box/front/sites/animedia-02" \
           "$ROOT/box/data" "$ROOT/box/state" "$ROOT/box/bin"
  ln -sfn "../../releases/old-release" "$ROOT/box/front/sites/animedia-01/current"
  ln -sfn "../../releases/old-release" "$ROOT/box/front/sites/animedia-02/current"
  # Пользовательские записи: их обязан пережить и успех, и откат.
  printf '{"titles":{"01a0":{"votes":{"v1":7},"comments":[{"id":"c1","text":"чужое"}]}}}\n' \
    > "$ROOT/box/data/animedia-community.json"
  # Публичный build-id живёт здесь, а не в каталоге релиза.
  printf '{"schema_version":1,"build_id":"old-release","artifact_sha256":"old"}\n' \
    > "$ROOT/box/front/template-manifest-animedia-01.json"
  printf '{"artifact_sha256":"newsha"}\n' \
    > "$ROOT/box/front/releases/$RELEASE_ID/RELEASE.json"

  cat > "$ROOT/box/bin/systemctl" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$SANDBOX/systemctl.log"
[ "${1:-}" = "is-active" ] && exit 0
exit 0
STUB
  cat > "$ROOT/box/bin/curl" <<'STUB'
#!/usr/bin/env bash
# Заголовки
for a in "$@"; do [ "$a" = "-D" ] && { printf 'HTTP/2 200\nX-Robots-Tag: noindex, nofollow\n'; exit 0; }; done
# Код ответа
case "$*" in *%{http_code}*) printf '200'; exit 0;; esac
# Страница
if [ "${FORCE_BAD_PAGE:-0}" = "1" ]; then
  printf '<html>сломанная страница без плеера и раздела</html>'
else
  printf '<div data-b07-player="1"></div><section data-community="on" '
  printf 'data-comments-space="animedia-01" data-comments-subject-kind="content-id">'
  printf '<input name="csrf" value="x"></section>'
fi
STUB
  chmod +x "$ROOT/box/bin/systemctl" "$ROOT/box/bin/curl"
}

run_deploy() {
  SANDBOX="$ROOT/box" \
  PATH="$ROOT/box/bin:$PATH" \
  FRONTEND_ROOT="$ROOT/box/front" \
  STATE_DIR="$ROOT/box/state" \
  SITE_DATA="$ROOT/box/data" \
  SYSTEMCTL="$ROOT/box/bin/systemctl" \
  CURL="$ROOT/box/bin/curl" \
  REQUIRE_ROOT=0 \
  FORCE_BAD_PAGE="${1:-0}" \
  bash "$SCRIPT" > "$ROOT/box/out.txt" 2>&1
  echo $?
}

link_now() { basename "$(readlink -f "$ROOT/box/front/sites/animedia-01/current")"; }
data_now() { cat "$ROOT/box/data/animedia-community.json"; }

echo "== сценарий 1: успешная выкладка"
make_sandbox
BASE_DATA=$(data_now)
rc=$(run_deploy 0)
report "код возврата 0" "$([ "$rc" = "0" ] && echo yes || echo no)"
report "витрина на новом релизе" "$([ "$(link_now)" = "$RELEASE_ID" ] && echo yes || echo no)"
report "записи посетителей целы" "$([ "$(data_now)" = "$BASE_DATA" ] && echo yes || echo no)"
report "резервная копия создана" \
  "$(ls "$ROOT"/box/data/*.before-community-public.* >/dev/null 2>&1 && echo yes || echo no)"
report "точка отката записана" \
  "$(grep -q 'old-release' "$ROOT/box/state/community-public-state.json" && echo yes || echo no)"
report "приёмка объявлена пройденной" \
  "$(grep -q 'приёмка пройдена' "$ROOT/box/out.txt" && echo yes || echo no)"
report "манифест объявляет выложенный релиз" \
  "$(grep -q "$RELEASE_ID" "$ROOT/box/front/template-manifest-animedia-01.json" && echo yes || echo no)"

echo
echo "== сценарий 2: живая проверка падает после переключения"
make_sandbox
BASE_DATA=$(data_now)
rc=$(run_deploy 1)
report "код возврата ненулевой" "$([ "$rc" != "0" ] && echo yes || echo no)"
report "витрина возвращена на прежний релиз" \
  "$([ "$(link_now)" = "old-release" ] && echo yes || echo no)"
report "записи посетителей целы после отката" \
  "$([ "$(data_now)" = "$BASE_DATA" ] && echo yes || echo no)"
report "откат объявлен" "$(grep -q 'ROLLED_BACK' "$ROOT/box/out.txt" && echo yes || echo no)"
report "юнит перезапущен при откате" \
  "$([ "$(grep -c 'restart' "$ROOT/box/systemctl.log" 2>/dev/null || echo 0)" -ge 2 ] && echo yes || echo no)"
report "манифест возвращён к прежнему релизу" \
  "$(grep -q 'old-release' "$ROOT/box/front/template-manifest-animedia-01.json" && echo yes || echo no)"

echo
echo "== сценарий 3: повторный запуск после частичного выполнения"
# Ровно то, что случилось у владельца: ссылка переставлена, приёмка не дошла.
make_sandbox
ln -sfn "../../releases/$RELEASE_ID" "$ROOT/box/front/sites/animedia-01/current"
printf '{"release_before":"../../releases/old-release","release_applied":"%s","unit":"u","animedia_02_before":""}\n' \
  "$RELEASE_ID" > "$ROOT/box/state/community-public-state.json"
STATE_BEFORE=$(cat "$ROOT/box/state/community-public-state.json")
BASE_DATA=$(data_now)
rc=$(run_deploy 0)
report "код возврата 0" "$([ "$rc" = "0" ] && echo yes || echo no)"
report "переключение пропущено" \
  "$(grep -q 'переключение пропускается' "$ROOT/box/out.txt" && echo yes || echo no)"
report "приёмка всё равно выполнена" \
  "$(grep -q 'живая проверка' "$ROOT/box/out.txt" && echo yes || echo no)"
report "точка отката не переписана" \
  "$([ "$(cat "$ROOT/box/state/community-public-state.json")" = "$STATE_BEFORE" ] && echo yes || echo no)"
report "лишняя резервная копия не создана" \
  "$(ls "$ROOT"/box/data/*.before-community-public.* >/dev/null 2>&1 && echo no || echo yes)"
report "записи посетителей целы" "$([ "$(data_now)" = "$BASE_DATA" ] && echo yes || echo no)"

echo
echo "== сценарий 4: повторный запуск и проверка падает — откат по записанной точке"
make_sandbox
ln -sfn "../../releases/$RELEASE_ID" "$ROOT/box/front/sites/animedia-01/current"
printf '{"release_before":"../../releases/old-release","release_applied":"%s","unit":"u","animedia_02_before":""}\n' \
  "$RELEASE_ID" > "$ROOT/box/state/community-public-state.json"
BASE_DATA=$(data_now)
rc=$(run_deploy 1)
report "код возврата ненулевой" "$([ "$rc" != "0" ] && echo yes || echo no)"
report "откат по записанной точке" \
  "$([ "$(link_now)" = "old-release" ] && echo yes || echo no)"
report "записи посетителей целы" "$([ "$(data_now)" = "$BASE_DATA" ] && echo yes || echo no)"

echo
if [ "$fails" -eq 0 ]; then echo "REHEARSAL=PASS"; else echo "REHEARSAL=FAIL ($fails)"; fi
exit "$fails"
