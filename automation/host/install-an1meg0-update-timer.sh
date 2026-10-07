#!/usr/bin/env bash
# Доставка снимков каталога для an1meg0.site: юнит и таймер, которых у ячейки нет.
#
#   sudo bash automation/host/install-an1meg0-update-timer.sh [--dry-run]
#
# ЗАЧЕМ. Измерено 2026-10-07: каталог an1meg0.site заморожен на 2026-09-28.
#
#     /srv/an1meg0-site/data/animego-04-catalog.json   09-28 03:56
#     /srv/an1mego-site/data/animego-02-catalog.json   10-06 04:03
#     /srv/animeg0-site/data/animego-03-catalog.json   10-06 04:04
#
# Расписание витрины пусто и помечено `generated_at 2026-09-28T17:42:55+03:00`,
# в карте сайта 7501 адрес против 8069 у двух соседних ячеек того же семейства.
# Причина — не код: у соседей есть таймер доставки (`an1mego-site-update.timer`,
# `animeg0-site-update.timer`, оба раз в 10 минут), а у этой ячейки из юнитов
# только `an1meg0-site-popular-weekly.*`. Сценарий доставки на месте
# (`/srv/an1meg0-site/current/automation/site-update.py`) — запускать его нечем.
#
# Юниты ниже скопированы с соседней ячейки и отличаются ровно тремя вещами:
# именем площадки, каталогом (`current`, а не `app` — у этой ячейки раскладка с
# выпусками) и пользователем. Ничего, кроме своих файлов, они не трогают: запись
# разрешена только в каталог данных площадки.
# Имена переменных только ASCII: bash считает именем лишь
# [A-Za-z_][A-Za-z0-9_]*, и строка вида `СУХОЙ=0` для него не
# присваивание, а вызов команды — измерено на этом же файле.
set -euo pipefail

DRY=0
if [ "${1:-}" = "--dry-run" ]; then DRY=1; fi

ACCOUNT=an1meg0-site
UNIT_DIR=/etc/systemd/system
SCRIPT=/srv/$ACCOUNT/current/automation/site-update.py
DATA_DIR=/srv/$ACCOUNT/data

if [ ! -f "$SCRIPT" ]; then
  echo "отказ: нет сценария доставки $SCRIPT" >&2
  exit 2
fi
if [ ! -d "$DATA_DIR" ]; then
  echo "отказ: нет каталога данных $DATA_DIR" >&2
  exit 2
fi

SERVICE_TEXT=$(cat <<UNIT
[Unit]
Description=Доставка снимков каталога для an1meg0.site
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$ACCOUNT
Group=$ACCOUNT
WorkingDirectory=/srv/$ACCOUNT/current
ExecStart=/usr/bin/python3 $SCRIPT --data-dir $DATA_DIR
# Источники открываются только на чтение; писать можно лишь в свой каталог.
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=yes
NoNewPrivileges=yes
ReadWritePaths=$DATA_DIR
TimeoutStartSec=300
UNIT
)

TIMER_TEXT=$(cat <<UNIT
[Unit]
Description=an1meg0.site: регулярная доставка снимков каталога

[Timer]
OnBootSec=3min
OnUnitActiveSec=10min
AccuracySec=30s
RandomizedDelaySec=45s
Persistent=true
Unit=$ACCOUNT-update.service

[Install]
WantedBy=timers.target
UNIT
)

if [ "$DRY" = "1" ]; then
  echo "--- $UNIT_DIR/$ACCOUNT-update.service"
  printf '%s\n' "$SERVICE_TEXT"
  echo "--- $UNIT_DIR/$ACCOUNT-update.timer"
  printf '%s\n' "$TIMER_TEXT"
  echo "сухой прогон: ничего не записано, таймер не включён"
  exit 0
fi

printf '%s\n' "$SERVICE_TEXT" > "$UNIT_DIR/$ACCOUNT-update.service"
printf '%s\n' "$TIMER_TEXT" > "$UNIT_DIR/$ACCOUNT-update.timer"
systemctl daemon-reload
systemctl enable --now "$ACCOUNT-update.timer"

# Первый прогон — сразу, чтобы расхождение в девять дней закрылось не через
# десять минут, а сейчас, и чтобы его исход был виден в этом же выводе.
if systemctl start "$ACCOUNT-update.service"; then
  echo "доставка выполнена; свежесть снимка:"
  ls -l --time-style=+%F' '%T "$DATA_DIR"/animego-04-catalog.json
else
  echo "ПЕРВЫЙ ПРОГОН НЕ УДАЛСЯ: journalctl -u $ACCOUNT-update.service -n 50" >&2
  exit 1
fi

systemctl list-timers "$ACCOUNT-update.timer" --no-pager || true
