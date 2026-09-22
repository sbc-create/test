#!/usr/bin/env bash
# Репетиция включения модератора: скрипт ИСПОЛНЯЕТСЯ в песочнице.
#
# Тот же приём, что у community_deploy_rehearsal.sh, и по той же причине:
# `bash -n` не отличает присваивание от вызова команды, а ошибка здесь
# оставила бы витрину с чужой или полуприменённой конфигурацией юнита.
#
# Сценарии: успех, повторный запуск, отказ ПОСЛЕ изменения конфигурации —
# отдельно когда drop-in не существовал и когда существовал чужой.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/animedia-enable-moderator.sh"
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
  mkdir -p "$ROOT/box/etc/$RELEASE_ID" "$ROOT/box/systemd" "$ROOT/box/keys" \
           "$ROOT/box/state" "$ROOT/box/bin"
  printf '{"release_before":"../../releases/old-release","release_applied":"%s","unit":"u","animedia_02_before":""}\n' \
    "$RELEASE_ID" > "$ROOT/box/state/community-public-state.json"

  cat > "$ROOT/box/bin/systemctl" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$SANDBOX/systemctl.log"
case "${1:-}" in
  is-active)
    [ -f "$SANDBOX/unit-down" ] && exit 3
    printf 'active\n'; exit 0;;
  restart)
    [ -f "$SANDBOX/restart-fails" ] && exit 1
    exit 0;;
esac
exit 0
STUB
  cat > "$ROOT/box/bin/curl" <<'STUB'
#!/usr/bin/env bash
for a in "$@"; do
  if [ "$a" = "-D" ]; then
    if [ -f "$SANDBOX/wrong-build" ]; then
      printf 'HTTP/2 200\nX-Site-Factory-Build-Id: some-other-release\n'
    else
      printf 'HTTP/2 200\nX-Site-Factory-Build-Id: %s\n' "$RELEASE_ID"
    fi
    exit 0
  fi
done
case "$*" in *%{http_code}*) printf '200'; exit 0;; esac
printf 'page'
STUB
  cat > "$ROOT/box/bin/verify.py" <<'STUB'
#!/usr/bin/env python3
import os, sys
if os.path.exists(os.environ["SANDBOX"] + "/verify-fails"):
    print("MODERATION_VERDICT=FAIL"); sys.exit(1)
print("MODERATION_VERDICT=PASS")
STUB
  chmod +x "$ROOT/box/bin/verify.py"
  cat > "$ROOT/box/bin/deploy.sh" <<'STUB'
#!/usr/bin/env bash
if [ -f "$SANDBOX/accept-fails" ]; then echo "приёмка провалена"; exit 2; fi
echo "RELEASE=$RELEASE_ID"
echo "SWITCHED=0"
STUB
  chmod +x "$ROOT/box/bin/systemctl" "$ROOT/box/bin/curl" "$ROOT/box/bin/deploy.sh"
}

run_mod() {
  SANDBOX="$ROOT/box" RELEASE_ID="$RELEASE_ID" \
  PATH="$ROOT/box/bin:$PATH" \
  ETC_SYSTEMD="$ROOT/box/systemd" \
  KEYFILE="$ROOT/box/keys/community-moderator.key" \
  STATE_DIR="$ROOT/box/state" \
  SYSTEMCTL="$ROOT/box/bin/systemctl" \
  CURL="$ROOT/box/bin/curl" \
  DEPLOY="$ROOT/box/bin/deploy.sh" \
  VERIFY="$ROOT/box/bin/verify.py" \
  REQUIRE_ROOT=0 READY_TIMEOUT=5 \
  bash "$SCRIPT" > "$ROOT/box/out.txt" 2>&1
  echo $?
}

DROPIN="$ROOT/box/systemd/nova-animedia-01.service.d/community-moderator.conf"
KEYF="$ROOT/box/keys/community-moderator.key"
STATEF="$ROOT/box/state/community-public-state.json"

echo "== сценарий 1: успешное включение"
make_sandbox
rc=$(run_mod)
report "код возврата 0" "$([ "$rc" = "0" ] && echo yes || echo no)"
report "drop-in создан" "$([ -f "$DROPIN" ] && echo yes || echo no)"
report "ключ создан" "$([ -s "$KEYF" ] && echo yes || echo no)"
report "drop-in несёт переменную" \
  "$(grep -q 'ANIMEDIA_COMMUNITY_MODERATOR_KEY=' "$DROPIN" 2>/dev/null && echo yes || echo no)"
report "значение ключа не напечатано" \
  "$(grep -qF "$(cat "$KEYF")" "$ROOT/box/out.txt" && echo no || echo yes)"
report "приёмка вызвана" "$(grep -q 'SWITCHED=0' "$ROOT/box/out.txt" && echo yes || echo no)"
report "sleep 3 не используется — ждём готовности" \
  "$(grep -q 'витрина готова через' "$ROOT/box/out.txt" && echo yes || echo no)"

echo
echo "== сценарий 2: повторный запуск"
KEY1=$(cat "$KEYF"); STATE1=$(cat "$STATEF")
rc=$(run_mod)
report "код возврата 0" "$([ "$rc" = "0" ] && echo yes || echo no)"
report "ключ не перевыпущен" "$([ "$(cat "$KEYF")" = "$KEY1" ] && echo yes || echo no)"
report "точка отката не переписана" "$([ "$(cat "$STATEF")" = "$STATE1" ] && echo yes || echo no)"
report "сообщено, что ключ оставлен как есть" \
  "$(grep -q 'оставлен как есть' "$ROOT/box/out.txt" && echo yes || echo no)"

echo
echo "== сценарий 3: отказ build-id после изменения конфигурации, drop-in не существовал"
make_sandbox
touch "$ROOT/box/wrong-build"
rc=$(run_mod)
report "код возврата ненулевой" "$([ "$rc" != "0" ] && echo yes || echo no)"
report "созданный drop-in удалён" "$([ -f "$DROPIN" ] && echo no || echo yes)"
report "ключ сохранён" "$([ -s "$KEYF" ] && echo yes || echo no)"
report "восстановление объявлено" \
  "$(grep -q 'MODERATOR_ENABLE_FAILED' "$ROOT/box/out.txt" && echo yes || echo no)"
report "служба перезапущена при восстановлении" \
  "$([ "$(grep -c 'restart' "$ROOT/box/systemctl.log" 2>/dev/null || echo 0)" -ge 2 ] && echo yes || echo no)"

echo
echo "== сценарий 4: отказ приёмки, drop-in СУЩЕСТВОВАЛ — содержимое обязано вернуться"
make_sandbox
mkdir -p "$(dirname "$DROPIN")"
printf '[Service]\nEnvironment=CHUZHAYA_NASTROYKA=1\n' > "$DROPIN"
BEFORE=$(cat "$DROPIN")
touch "$ROOT/box/accept-fails"
rc=$(run_mod)
report "код возврата ненулевой" "$([ "$rc" != "0" ] && echo yes || echo no)"
report "чужой drop-in не удалён" "$([ -f "$DROPIN" ] && echo yes || echo no)"
report "чужое содержимое возвращено" \
  "$([ "$(cat "$DROPIN")" = "$BEFORE" ] && echo yes || echo no)"

echo
echo "== сценарий 5: перезапуск не удался"
make_sandbox
touch "$ROOT/box/restart-fails"
rc=$(run_mod)
report "код возврата ненулевой" "$([ "$rc" != "0" ] && echo yes || echo no)"
report "drop-in убран" "$([ -f "$DROPIN" ] && echo no || echo yes)"

echo
echo "== сценарий 6: приёмка переключила релиз — это отказ"
make_sandbox
cat > "$ROOT/box/bin/deploy.sh" <<'STUB'
#!/usr/bin/env bash
echo "SWITCHED=1"
STUB
chmod +x "$ROOT/box/bin/deploy.sh"
rc=$(run_mod)
report "код возврата ненулевой" "$([ "$rc" != "0" ] && echo yes || echo no)"
report "названа причина" \
  "$(grep -q 'переключила релиз' "$ROOT/box/out.txt" && echo yes || echo no)"

echo
echo "== сценарий 7: модерация не подтвердилась — отказ и восстановление"
make_sandbox
touch "$ROOT/box/verify-fails"
rc=$(run_mod)
report "код возврата ненулевой" "$([ "$rc" != "0" ] && echo yes || echo no)"
report "drop-in убран" "$([ -f "$DROPIN" ] && echo no || echo yes)"
report "названа причина" \
  "$(grep -q 'проверка модерации не пройдена' "$ROOT/box/out.txt" && echo yes || echo no)"

echo
echo "== сценарий 8: успех включает подтверждение модерации"
make_sandbox
rc=$(run_mod)
report "код возврата 0" "$([ "$rc" = "0" ] && echo yes || echo no)"
report "модерация подтверждена" \
  "$(grep -q 'MODERATION_VERDICT=PASS' "$ROOT/box/out.txt" && echo yes || echo no)"

echo
if [ "$fails" -eq 0 ]; then echo "MODERATOR_REHEARSAL=PASS"; else echo "MODERATOR_REHEARSAL=FAIL ($fails)"; fi
exit "$fails"
