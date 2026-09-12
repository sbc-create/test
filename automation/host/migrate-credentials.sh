#!/usr/bin/env bash
# Перевод служб контура на раздельные учётные данные.
#
# Что здесь происходит и почему именно так
# ----------------------------------------
#
# Общий EnvironmentFile отдаётся юниту ЦЕЛИКОМ. Пока три службы читали один
# файл, каждая получала девять служебных личностей, приватный ключ подписи и
# токены управляющего слоя — включая те, что ей не нужны ни для чего. Убрать
# лишнее после старта невозможно: к первой строке кода значения уже в процессе.
#
# Поэтому файл разделяется на два разных предмета:
#   * несекретная конфигурация (пути к базам, флаги, адреса) остаётся
#     переменными окружения — секретами она не является;
#   * секреты уходят в отдельные файлы, по одному на личность, и выдаются
#     через LoadCredential — systemd кладёт в приватный tmpfs юнита ровно
#     то, что юнит попросил, и ничего сверх.
#
# Перевод идёт drop-in'ами, а не переписыванием юнитов: откат — удаление
# каталога drop-in, без восстановления чего-либо из резервной копии.
#
# Имена переменных ASCII: bash не разбирает кириллическое имя как присваивание.
set -Eeuo pipefail

REPO="${REPO:-/home/claude/wt-arc-002}"
CRED=/etc/site-factory/credentials
OLD_ENV=/etc/site-factory/control-api.env
NEW_ENV=/etc/site-factory/control-plane.env
SIGNER_USER=approval-signer
RUNTIME=/srv/site-factory/control-api/current

log() { printf '[credentials] %s\n' "$*"; }

# Секреты, которым не место в окружении ни одной службы.
SECRET_NAMES='^(AUDIT_TOKEN_[A-Z_]+|CHANGESET_APPROVAL_KEY|SITE_ENGINE_CONTROL_TOKENS|AUDIT_REVOKED_FINGERPRINTS)='

log "выдача учётных данных по личностям"
PYTHONPATH="$REPO" python3 -m factory.site_engine.credentials.provision ensure >/dev/null

# --- несекретная конфигурация ------------------------------------------------
if [[ -f "$OLD_ENV" ]]; then
  {
    echo "# Несекретная конфигурация контура. Секреты здесь запрещены:"
    echo "# они выдаются через systemd LoadCredential из ${CRED}."
    grep -vE "$SECRET_NAMES" "$OLD_ENV" | grep -vE '^\s*#' | grep -vE '^\s*$'
  } > "$NEW_ENV"
  chmod 0644 "$NEW_ENV"
  log "несекретная конфигурация: $(grep -cE '^[A-Z]' "$NEW_ENV") переменных"
fi

# --- учётная запись службы подписи -------------------------------------------
if ! getent passwd "$SIGNER_USER" >/dev/null; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$SIGNER_USER"
  log "создана учётная запись ${SIGNER_USER}"
fi
usermod -G "" "$SIGNER_USER"

# --- юнит службы подписи ------------------------------------------------------
cat > /etc/systemd/system/site-factory-approval-signer.service <<UNIT
[Unit]
Description=site-factory: выделенная служба подписи одобрений (Ed25519)
After=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=${SIGNER_USER}
Group=${SIGNER_USER}
WorkingDirectory=${RUNTIME}
Environment=PYTHONPATH=${RUNTIME}
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONUNBUFFERED=1
Environment=APPROVAL_SIGNER_PORT=8795
# Единственный процесс контура, которому принадлежит приватный ключ.
LoadCredential=approval-signing-key:${CRED}/approval-signing-key
LoadCredential=approval-verify-keys:${CRED}/approval-verify-keys
LoadCredential=approval-signer-token:${CRED}/approval-signer-token
NoNewPrivileges=true
CapabilityBoundingSet=
AmbientCapabilities=
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictRealtime=true
RestrictNamespaces=true
LockPersonality=true
RestrictAddressFamilies=AF_INET AF_UNIX
SystemCallFilter=@system-service
SystemCallErrorNumber=EPERM
ExecStart=${RUNTIME}/.venv/bin/python -m factory.site_engine.approval.service
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

# --- drop-in: каждой службе только своё --------------------------------------
# EnvironmentFile= с пустым значением сбрасывает список: без этого общий файл
# остался бы в нём, и весь перевод был бы декорацией.
dropin() {
  local unit="$1"; shift
  install -d "/etc/systemd/system/${unit}.d"
  {
    echo "[Service]"
    echo "EnvironmentFile="
    echo "EnvironmentFile=-${NEW_ENV}"
    for name in "$@"; do
      echo "LoadCredential=${name}:${CRED}/${name}"
    done
  } > "/etc/systemd/system/${unit}.d/10-credentials.conf"
  log "${unit}: $# credential(ов)"
}

# Control API опознаёт службы по ОТПЕЧАТКАМ токенов, сырых значений не хранит.
dropin site-factory-control-api.service \
  audit-token-fingerprints approval-verify-keys approval-signer-token \
  site-engine-control-tokens

# Мосту нужна ровно его собственная личность.
dropin site-factory-audit-bridge.service audit-token-control-plane

# Рабочий процесс только ПРОВЕРЯЕТ одобрения — ему достаточно публичного ключа.
dropin site-factory-changeset-worker.service \
  approval-verify-keys audit-token-control-plane

systemctl daemon-reload
log "drop-in'ы записаны; перезапуск выполняется отдельным шагом"
