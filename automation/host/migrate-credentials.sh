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
# Файл собирается во ВРЕМЕННЫЙ и подменяется только после проверки.
#
# Первая версия писала прямо в целевой файл. Перенаправление обрезает файл до
# запуска команды, и когда источник оказался уже выведенным из обращения,
# grep не нашёл ни строки, pipefail оборвал скрипт — а рабочая конфигурация
# к тому моменту была стёрта. Службы пережили это только потому, что
# перезапуска не случилось.
if [[ -f "$OLD_ENV" ]]; then
  TMP_ENV="$(mktemp)"
  {
    echo "# Несекретная конфигурация контура. Секреты здесь запрещены:"
    echo "# они выдаются через systemd LoadCredential из ${CRED}."
    grep -vE "$SECRET_NAMES" "$OLD_ENV" | grep -vE '^\s*#' | grep -vE '^\s*$' || true
  } > "$TMP_ENV"
  COUNT="$(grep -cE '^[A-Z_]+=' "$TMP_ENV" || true)"
  EXISTING="$( [[ -f "$NEW_ENV" ]] && grep -cE '^[A-Z_]+=' "$NEW_ENV" || echo 0 )"
  if (( COUNT >= EXISTING && COUNT > 0 )); then
    install -m 0644 "$TMP_ENV" "$NEW_ENV"
    log "несекретная конфигурация: ${COUNT} переменных"
  else
    log "конфигурация не тронута: источник дал ${COUNT}, действующая ${EXISTING}"
  fi
  rm -f "$TMP_ENV"
fi

# --- учётная запись службы подписи -------------------------------------------
if ! getent passwd "$SIGNER_USER" >/dev/null; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$SIGNER_USER"
  log "создана учётная запись ${SIGNER_USER}"
fi
usermod -G "" "$SIGNER_USER"

# --- непривилегированные учётные записи автономных служб ---------------------
# Заводятся заранее, до развёртывания самих служб: граница, созданная вместе с
# сервисом, обычно создаётся «потом», а потом сервис уже работает под тем, под
# чем его запустили в первый раз.
#
# qwen — MODEL. Он не должен уметь ни стать оператором, ни подписать, ни
# дотянуться до docker, sudo и ключей SSH.
for_each_service_account() {
  local name="$1"
  if ! getent passwd "$name" >/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$name"
    log "создана учётная запись ${name}"
  fi
  usermod -G "" "$name"
}
for_each_service_account qwen
for_each_service_account provider-adapters

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

# --- вывод общего файла из обращения ------------------------------------------
# Выполняется отдельной командой, ПОСЛЕ того как службы перезапущены и
# проверены: удалить источник до перевода значило бы уронить их все разом.
#
# Значения не сохраняются нигде. Они уже отозваны, и «резервная копия на
# всякий случай» была бы просто ещё одним местом, где лежит скомпрометированный
# секрет.
if [[ "${1:-}" == "finalize" ]]; then
  if [[ -f "$OLD_ENV" ]]; then
    {
      echo "# Файл выведен из обращения $(date -u +%Y-%m-%dT%H:%M:%SZ)."
      echo "# Секреты раздаются через systemd LoadCredential из ${CRED},"
      echo "# по одному файлу на личность. Прежние значения ОТОЗВАНЫ:"
      echo "# их отпечатки в ${CRED}/audit-token-fingerprints, поле revoked."
      echo "# Несекретная конфигурация: ${NEW_ENV}"
    } > "$OLD_ENV"
    chmod 0644 "$OLD_ENV"
    log "общий файл выведен из обращения: секретов в нём не осталось"
  fi
fi
