#!/usr/bin/env bash
# Доставка SEO-отчётов владельцу в Telegram. Два шага владельца:
#
#   1) sudo bash automation/host/install-notify.sh
#      — спросит токен бота СКРЫТЫМ вводом (не отображается, не попадает в
#        историю оболочки и в журналы), сохранит его в
#        /etc/site-factory/secrets/telegram/bot_token (root, 0600), поставит
#        юниты и покажет чаты, написавшие боту /start. Сообщений не отправляет.
#
#   2) sudo bash automation/host/install-notify.sh --chat <id>
#      — подтверждение чата владельца: только id из списка шага 1; включает
#        отчёт в 09:00 МСК и срочные ошибки, отправляет тестовое сообщение и
#        показывает ответ Telegram.
#
# Перед шагом 1: создать бота у @BotFather и написать ему /start со своего
# аккаунта (иначе бот не видит чат и не может в него писать).
#
#   --dry-run   показать действия, ничего не записывая
set -Eeuo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SECRETS=/etc/site-factory/secrets/telegram
DEST=/etc/systemd/system
STATE="$REPO_ROOT/var/notify"
UNITS=(notify@.service notify-discover.service notify-daily.timer notify-alerts.timer)

dry_run=0; chat=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --chat) chat="${2:-}"; shift ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 64 ;;
  esac
  shift
done

run() { if [ "$dry_run" -eq 1 ]; then echo "[dry-run] $*"; else echo "+ $*"; "$@"; fi; }

for unit in "${UNITS[@]}"; do
  [ -f "$HERE/notify/$unit" ] || { echo "нет $HERE/notify/$unit" >&2; exit 66; }
  case "$unit" in *.service)
    grep -qx "WorkingDirectory=$REPO_ROOT" "$HERE/notify/$unit" || { echo "$unit: чужое дерево" >&2; exit 65; } ;;
  esac
done
grep -q "host: api.telegram.org" "$REPO_ROOT/inventory/network-allowlist.yaml" || {
  echo "api.telegram.org нет в inventory — доставка не разрешена" >&2; exit 65; }

if [ "$dry_run" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then echo "нужен root: sudo bash $0" >&2; exit 1; fi

show_chats() {
  sudo -u claude python3 - "$STATE/chat-candidates.json" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except OSError:
    print("список чатов не получен"); sys.exit(0)
if not d.get("ok"):
    print("Telegram отказал:", d.get("description")); sys.exit(0)
if not d["chats"]:
    print("чатов нет: напишите боту /start со своего аккаунта и повторите шаг 1")
for c in d["chats"]:
    name = c.get("title") or " ".join(x for x in (c.get("first_name"), "@" + c["username"] if c.get("username") else None) if x)
    print(f"  chat_id={c['chat_id']}  тип={c['type']}  имя={name}  последнее={c.get('last_text')!r}")
PY
}

if [ -z "$chat" ]; then
  # --- шаг 1: токен, юниты, поиск чата ------------------------------------
  run install -d -o root -g root -m 0700 "$SECRETS"
  run install -d -o claude -g claude -m 0755 "$STATE"
  if [ "$dry_run" -eq 0 ] && [ ! -s "$SECRETS/bot_token" ]; then
    printf 'Токен бота (ввод не отображается): ' >&2
    IFS= read -rs token; echo >&2
    if ! [[ "$token" =~ ^[0-9]{5,}:[A-Za-z0-9_-]{30,}$ ]]; then
      unset token; echo "это не похоже на токен бота Telegram — ничего не записано" >&2; exit 65
    fi
    ( umask 077; printf '%s' "$token" > "$SECRETS/bot_token" )
    unset token
    chmod 0600 "$SECRETS/bot_token"; chown root:root "$SECRETS/bot_token"
    echo "токен сохранён: $SECRETS/bot_token (root, 0600)"
  else
    echo "токен уже есть или dry-run — не спрашиваю"
  fi
  for unit in "${UNITS[@]}"; do run install -m 0644 "$HERE/notify/$unit" "$DEST/$unit"; done
  run systemctl daemon-reload
  run systemctl start notify-discover.service
  [ "$dry_run" -eq 1 ] || { echo "чаты, написавшие боту:"; show_chats; }
  echo
  echo "Дальше — подтвердите СВОЙ чат: sudo bash $0 --chat <chat_id из списка>"
  exit 0
fi

# --- шаг 2: подтверждение чата, включение, тест ------------------------------
[[ "$chat" =~ ^-?[0-9]+$ ]] || { echo "chat_id — число из списка шага 1" >&2; exit 64; }
grep -q "\"chat_id\": \"$chat\"" "$STATE/chat-candidates.json" 2>/dev/null || {
  echo "chat_id $chat нет в списке чатов, написавших боту (шаг 1) — не подтверждаю" >&2; exit 65; }
if [ "$dry_run" -eq 0 ]; then
  ( umask 077; printf '%s' "$chat" > "$SECRETS/chat_id" ); chmod 0600 "$SECRETS/chat_id"
else
  echo "[dry-run] записать chat_id в $SECRETS/chat_id (0600)"
fi
run systemctl daemon-reload
run systemctl start notify@test.service
run systemctl enable --now notify-daily.timer notify-alerts.timer
if [ "$dry_run" -eq 0 ]; then
  echo "ответ Telegram на тест:"
  sudo -u claude tail -1 "$STATE/deliveries.jsonl"
fi
run systemctl list-timers --no-pager notify-daily.timer notify-alerts.timer
