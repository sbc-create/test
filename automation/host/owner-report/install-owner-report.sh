#!/usr/bin/env bash
# Установка расписания отчётов владельцу. ОДНА операция владельца.
#
# Почему не из сессии: `systemctl` сессии недоступен (deny-правило профиля), и
# обходить запрет нельзя. Поэтому юниты лежат в репозитории, а включение —
# здесь, явной командой.
#
# Что делает: кладёт пользовательские юниты, перечитывает менеджер, включает
# таймер и ПОКАЗЫВАЕТ результат. Ничего на сайтах не меняет.
#
# Имена переменных только ASCII.
set -uo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

echo "==> репозиторий: $repo_root"
echo "==> каталог юнитов: $unit_dir"
mkdir -p "$unit_dir"

for f in owner-report.service owner-report.timer; do
  src="$repo_root/automation/host/owner-report/$f"
  [ -f "$src" ] || { echo "[x] нет $src"; exit 1; }
  # Резервная копия прежней версии: откат должен быть исполним, а не описан.
  if [ -f "$unit_dir/$f" ]; then
    cp "$unit_dir/$f" "$unit_dir/$f.before-$(date -u +%Y%m%dT%H%M%SZ)"
  fi
  install -m 0644 "$src" "$unit_dir/$f"
  echo "   поставлен $f"
done

echo "==> перечитываю пользовательский менеджер"
systemctl --user daemon-reload || { echo "[x] daemon-reload не удался"; exit 1; }

echo "==> включаю таймер"
systemctl --user enable --now owner-report.timer || {
  echo "[x] включение не удалось"; exit 1; }

echo "==> ПРОВЕРКА РЕЗУЛЬТАТА"
systemctl --user list-timers owner-report.timer --all --no-pager
systemctl --user is-enabled owner-report.timer
echo
echo "==> пробный запуск (отчёт будет записан, доставка — если есть токен)"
systemctl --user start owner-report.service
sleep 2
systemctl --user status owner-report.service --no-pager | tail -15
echo
python3 "$repo_root/automation/local/owner-report.py" --status

cat <<'ПАМЯТКА'

ОТКАТ: systemctl --user disable --now owner-report.timer
       (юниты остаются на месте; прежние версии — *.before-<время>)

ДОСТАВКА: отчёт записывается в docs/reports/ независимо от доставки.
Чтобы он УХОДИЛ в Telegram, нужны две вещи, и обе — решение владельца:
  1) файл токена бота, например /etc/site-factory/secrets/telegram_bot_token,
     и раскомментированная строка LoadCredential в owner-report.service;
  2) подтверждённый чат владельца (см. `python3 -m seo_operator.cli notify
     discover` и далее notify test).
Пока их нет, инструмент пишет в отчёте прямо: не доставлено, причина такая.
ПАМЯТКА
