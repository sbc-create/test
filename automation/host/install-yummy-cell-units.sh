#!/usr/bin/env bash
# Юниты ячеек Yummy: три основных и три кандидатских.
#
#   sudo bash automation/host/install-yummy-cell-units.sh [--dry-run]
#
# Зачем
# -----
#
# Для zona-01, lords-01, lords-02 и lords-03 юниты ячеек уже стоят, у Yummy их
# нет ни одного. Без них исполнитель не может ни прогреть кандидата, ни
# повысить его: он ЗАПУСКАЕТ службу по имени из реестра, а path_outа с таким именем
# в /etc/systemd/system нет.
#
# Хуже другое, и это главная причина писать отдельный сценарий, а не просить
# «поставить пакет». В реестре у витрин Yummy сейчас записан unit МОНОЛИТА
# (`nova-yummy-site.service`). Если оставить так, повышение перезапустило бы
# монолитную службу, а её ExecStart ведёт в /srv/lords/.frontend — то есть
# выпуск прошёл бы «успешно», ничего не переключив. Снаружи это неотличимо от
# настоящего выпуска: сайт отвечает 200 и показывает прежний код. Поэтому
# ячейке нужна СВОЯ служба, а монолитная становится previous_unit и гасится.
#
# Что делает
# ----------
#
#   nova-yummyani-<role>.service            ячейка, port как у монолита
#   nova-yummyani-<role>-candidate.service  кандидат, port +1000
#
# Чего НЕ делает: не включает и не запускает их. Запуск кандидата и повышение —
# работа исполнителя, и делать это здесь значило бы поднять витрину до того,
# как в её хранилище что-либо положено.
#
# Учётные записи и dir_nameи создаёт исполнитель на шаге prepare. Файл юнита
# ссылается на пользователя, которого может ещё не быть: systemd проверяет это
# при запуске, а не при установке.
set -Eeuo pipefail

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

UNIT_DIR=/etc/systemd/system
log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"

# role:domain:port — порядок портов именно такой, это не опечатка:
# site 9132, org 9131, biz 9130. Проверено по upstream-path_outам nginx и по
# LORDS_LEGACY_UPSTREAM монолитных юнитов.
LIST="site:yummyani.site:9132 org:yummyani.org:9131 biz:yummyani.biz:9130"

write_unit() {
  local path_out="$1" body="$2"
  if [ "$dry_run" = 1 ]; then
    printf '   [сухой прогон] %s\n' "$path_out"
    return 0
  fi
  if [ -f "$path_out" ] && [ "$(cat "$path_out")" = "$body" ]; then
    printf '   без изменений: %s\n' "$path_out"
    return 0
  fi
  printf '%s' "$body" > "$path_out"
  chmod 0644 "$path_out"
  printf '   записан: %s\n' "$path_out"
}

unit_body() {
  local domain="$1" account="$2" port="$3" dir_name="$4"
  cat <<UNITEOF
[Unit]
Description=${domain} (${account}), выделенная ячейка
After=network-online.target

[Service]
Type=simple
User=${account}
Group=${account}
WorkingDirectory=/srv/${account}/${dir_name}
ExecStart=/usr/bin/python3 /srv/${account}/${dir_name}/run.py --port ${port} --data-dir /srv/${account}/data
Restart=on-failure
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
# База оценок лежит в хранилище и открывается на entry: рядом появляются
# -wal и -shm, поэтому dir_name целиком, а не один path_out.
ReadWritePaths=/srv/${account}/data
ProtectKernelTunables=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
UNITEOF
}

for entry in $LIST; do
  role="${entry%%:*}"
  rest="${entry#*:}"
  domain="${rest%%:*}"
  port="${rest##*:}"
  account="yummyani-${role}"
  log "ячейка ${domain}: порт ${port}, кандидат $((port + 1000))"
  write_unit "${UNIT_DIR}/nova-${account}.service" "$(unit_body "$domain" "$account" "$port" current)"
  write_unit "${UNIT_DIR}/nova-${account}-candidate.service" \
           "$(unit_body "$domain" "$account" "$((port + 1000))" candidate)"
done

if [ "$dry_run" = 1 ]; then
  echo
  echo "сухой прогон завершён: ничего не менялось"
  exit 0
fi

log "перечитывание юнитов"
systemctl daemon-reload

log "готово: шесть юнитов установлены, ни один не включён и не запущен"
echo "Дальше — выпуск через очередь; включать и запускать их вручную не нужно."
