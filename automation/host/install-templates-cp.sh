#!/usr/bin/env bash
# Установка внутреннего адаптера Templates: закреплённая копия + служба.
#
# Ставится ТОЛЬКО внутренний потребитель событий Registry. Он читает
# Control Plane и пишет собственную проекцию; к витринам, релизам и
# контентной базе не прикасается.
#
# Копия закрепляется по коммиту, а не запускается из рабочего дерева:
# ветка в worktree переключается другими сессиями, и служба, живущая в
# рабочем дереве, однажды поедет на чужом коде.
#
# Имена переменных ASCII: bash не разбирает кириллическое имя как присваивание.
set -Eeuo pipefail

# Служба работает под СОБСТВЕННОЙ учётной записью, а не под claude.
#
# Это и есть закрытие прямого deploy на уровне прав ОС. Под claude служба
# получала бы группу claude (а значит чтение /etc/site-factory/control-api.env
# с девятью служебными токенами и приватным ключом подписи), доступ к сокету
# docker и право перезапускать юниты витрин. Отдельная учётная запись без
# sudo, без групп docker/claude/lords не может ни выложить релиз витрины, ни
# прочитать чужой секрет — независимо от того, что случится с кодом.
SERVICE_USER=templates-cp

REPO="${REPO:-/home/claude/wt-integration-28}"
COMMIT="$(git -C "$REPO" rev-parse HEAD)"

# Манифест объявляет коммит, а копируется рабочее дерево. Если дерево грязное
# по устанавливаемым путям, манифест соврёт о происхождении — и это ровно тот
# класс дефекта «в репозитории одно, в работе другое», который потом ищут
# часами. Отказ здесь дешевле.
DIRTY="$(git -C "$REPO" status --porcelain -- factory/templates_cp factory/__init__.py)"
if [[ -n "$DIRTY" ]]; then
  printf '[templates-cp] ОТКАЗ: рабочее дерево грязное по устанавливаемым путям:\n%s\n' "$DIRTY" >&2
  exit 5
fi
ROOT=/srv/templates-cp
RELEASE="${ROOT}/releases/${COMMIT}"
STATE=/var/lib/templates-cp
UNIT=/etc/systemd/system/templates-cp-consumer.service

log() { printf '[templates-cp] %s\n' "$*"; }

log "коммит: ${COMMIT}"

if ! getent passwd "$SERVICE_USER" >/dev/null; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
  log "создана служебная учётная запись ${SERVICE_USER}"
fi
# Ни одной дополнительной группы: членство в docker, lords или claude вернуло
# бы ровно тот путь в production, который здесь закрывается.
usermod -G "" "$SERVICE_USER"

# Служба останавливается ДО смены владельца состояния. Работающий процесс,
# у которого из-под рук забирают файл базы, падает на записи с «disk I/O
# error» — и падает он уже на завершении, где это некому обработать.
systemctl stop templates-cp-consumer.service 2>/dev/null || true

install -d -o "$SERVICE_USER" -g "$SERVICE_USER" "$ROOT" "$ROOT/releases" "$STATE"
rm -rf "$RELEASE"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" "$RELEASE/factory"
cp -a "$REPO/factory/templates_cp" "$RELEASE/factory/templates_cp"
cp -a "$REPO/factory/__init__.py" "$RELEASE/factory/__init__.py"
chown -R "$SERVICE_USER":"$SERVICE_USER" "$RELEASE"

# Отпечаток артефакта: что именно поедет в работу.
#
# Считается по СОДЕРЖИМОМУ и относительным путям. Первая версия хэшировала
# вывод sha256sum вместе с абсолютными путями, и один и тот же код через
# `releases/<sha>/` и через `current/` давал разные отпечатки — сравнение
# «установлено против работает» ломалось на пустом месте.
ARTIFACT="$(cd "$RELEASE" && find . -name '*.py' -type f | LC_ALL=C sort \
  | xargs sha256sum | sha256sum | cut -d' ' -f1)"
printf '{"commit":"%s","artifact_sha256":"%s","installed_at":"%s"}\n' \
  "$COMMIT" "$ARTIFACT" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$RELEASE/release-manifest.json"
chown "$SERVICE_USER":"$SERVICE_USER" "$RELEASE/release-manifest.json"
log "artifact_sha256: ${ARTIFACT}"

# Состояние могло остаться от прежней учётной записи.
chown -R "$SERVICE_USER":"$SERVICE_USER" "$STATE"

ln -sfn "$RELEASE" "${ROOT}/current.new" && mv -Tf "${ROOT}/current.new" "${ROOT}/current"

cat > "$UNIT" <<UNITEOF
[Unit]
Description=site-factory: потребитель событий Registry для Templates
After=network-online.target site-factory-control-api.service
Wants=site-factory-control-api.service
# Бюджет рестартов задаётся в [Unit]: в [Service] systemd эти ключи
# игнорирует с предупреждением, и ограничение молча не действует.
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
# Права не расширяются ни при каких условиях: setuid-бинарь внутри службы
# повышения не даст.
NoNewPrivileges=true
CapabilityBoundingSet=
AmbientCapabilities=
# Файловая система только для чтения, кроме собственного состояния. Каталог
# витрин, /etc и чужие релизы недоступны для записи по построению.
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ReadWritePaths=${STATE}
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
ProtectClock=true
ProtectHostname=true
RestrictSUIDSGID=true
RestrictRealtime=true
RestrictNamespaces=true
LockPersonality=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
SystemCallFilter=@system-service
SystemCallErrorNumber=EPERM
WorkingDirectory=${ROOT}/current
Environment=PYTHONPATH=${ROOT}/current
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONUNBUFFERED=1
Environment=TEMPLATES_CP_BASE=http://127.0.0.1:8790
Environment=TEMPLATES_CP_STATE=${STATE}/projection.sqlite3
ExecStart=/usr/bin/python3 -m factory.templates_cp.consumer
Restart=on-failure
RestartSec=5
TimeoutStopSec=20
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
UNITEOF

# Доказательства аудита кладутся туда, где их читает служебная учётная
# запись: домашний каталог оператора ей закрыт (750), и это правильно —
# служба не должна ходить в рабочее дерево человека.
EVIDENCE_SRC="${REPO}/artifacts/fleet-audit"
EVIDENCE_DST="${ROOT}/evidence/fleet-audit"
if [[ -d "$EVIDENCE_SRC" ]]; then
  install -d -o root -g "$SERVICE_USER" -m 0750 "${ROOT}/evidence" "$EVIDENCE_DST"
  # Только разборные файлы: скриншоты службе не нужны и в журнал не идут.
  find "$EVIDENCE_SRC" -maxdepth 1 -type f \( -name '*.json' -o -name '*.md' \) \
    -exec install -o root -g "$SERVICE_USER" -m 0640 {} "$EVIDENCE_DST/" \;
  log "доказательства аудита: $(find "$EVIDENCE_DST" -type f | wc -l) файлов"
fi

systemctl daemon-reload
systemctl enable templates-cp-consumer.service >/dev/null
# Именно restart, а не `enable --now`: на уже активной службе `--now`
# ничего не делает, и новая копия молча не поедет в работу. Это тот же
# класс дефекта, что «исправлено в репозитории, но не выложено».
systemctl restart templates-cp-consumer.service
sleep 4
systemctl is-active templates-cp-consumer.service
RUNNING="$(systemctl show templates-cp-consumer -p MainPID --value)"
RUN_ART="$(cd "${ROOT}/current" && find . -name '*.py' -type f | LC_ALL=C sort \
  | xargs sha256sum | sha256sum | cut -d' ' -f1)"
[[ "$RUN_ART" == "$ARTIFACT" ]] \
  || { log "ОТКАЗ: работает артефакт ${RUN_ART}, установлен ${ARTIFACT}"; exit 4; }
log "работает pid=${RUNNING}; манифест: ${RUN_ART}"
log "установлено: ${RELEASE}"
