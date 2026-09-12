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

REPO="${REPO:-/home/claude/wt-integration-28}"
COMMIT="$(git -C "$REPO" rev-parse HEAD)"
ROOT=/srv/templates-cp
RELEASE="${ROOT}/releases/${COMMIT}"
STATE=/var/lib/templates-cp
UNIT=/etc/systemd/system/templates-cp-consumer.service

log() { printf '[templates-cp] %s\n' "$*"; }

log "коммит: ${COMMIT}"
install -d -o claude -g claude "$ROOT" "$ROOT/releases" "$STATE"
rm -rf "$RELEASE"
install -d -o claude -g claude "$RELEASE/factory"
cp -a "$REPO/factory/templates_cp" "$RELEASE/factory/templates_cp"
cp -a "$REPO/factory/__init__.py" "$RELEASE/factory/__init__.py"
chown -R claude:claude "$RELEASE"

# Отпечаток артефакта: что именно поедет в работу.
ARTIFACT="$(find "$RELEASE" -name '*.py' -type f | sort | xargs sha256sum | sha256sum | cut -d' ' -f1)"
printf '{"commit":"%s","artifact_sha256":"%s","installed_at":"%s"}\n' \
  "$COMMIT" "$ARTIFACT" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$RELEASE/release-manifest.json"
chown claude:claude "$RELEASE/release-manifest.json"
log "artifact_sha256: ${ARTIFACT}"

ln -sfn "$RELEASE" "${ROOT}/current.new" && mv -Tf "${ROOT}/current.new" "${ROOT}/current"

cat > "$UNIT" <<UNITEOF
[Unit]
Description=site-factory: потребитель событий Registry для Templates
After=network-online.target site-factory-control-api.service
Wants=site-factory-control-api.service

[Service]
Type=simple
User=claude
Group=claude
WorkingDirectory=${ROOT}/current
Environment=PYTHONPATH=${ROOT}/current
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONUNBUFFERED=1
Environment=TEMPLATES_CP_BASE=http://127.0.0.1:8790
Environment=TEMPLATES_CP_STATE=${STATE}/projection.sqlite3
ExecStart=/usr/bin/python3 -m factory.templates_cp.consumer
Restart=on-failure
RestartSec=5
# Ограниченный бюджет рестартов: бесконечный цикл перезапусков — это не
# отказоустойчивость, а способ исчерпать StartLimit и потерять службу.
StartLimitIntervalSec=300
StartLimitBurst=5
TimeoutStopSec=20
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
UNITEOF

systemctl daemon-reload
systemctl enable --now templates-cp-consumer.service >/dev/null
sleep 3
systemctl is-active templates-cp-consumer.service
log "установлено: ${RELEASE}"
