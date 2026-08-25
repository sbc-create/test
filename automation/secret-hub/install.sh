#!/usr/bin/env bash
# Установка Secret Hub. Запускается root'ом, один раз, на claude-control-01.
#
#   sudo bash /srv/site-factory/repo/automation/secret-hub/install.sh
#
# Что делает:
#   1. создаёт мастер-ключ (root:root 0600), если его ещё нет — существующий
#      НЕ перезаписывается: перезапись ключа означает потерю всех секретов;
#   2. создаёт каталог хранилища 0700 и группу управления;
#   3. ставит unit и запускает сервис;
#   4. печатает состояние.
#
# Чего не делает: не трогает DNS, nginx, индексацию, Basic Auth и базы данных;
# не читает и не печатает ни одного значения секрета; не удаляет существующие
# файлы credentials.
set -euo pipefail

REPO="${SECRET_HUB_REPO:-/srv/site-factory/repo}"
SECRET_DIR=/etc/site-factory/secrets
KEY_FILE="$SECRET_DIR/secret-hub-master.key"
STORE_DIR=/var/lib/site-factory-secret-hub
UNIT=site-factory-secret-hub.service
GROUP="${SECRET_HUB_GROUP:-sfhub}"
CONTROL_USER="${SECRET_HUB_CONTROL_USER:-claude}"

if [ "$(id -u)" -ne 0 ]; then
  echo "FATAL: установка выполняется от root." >&2
  exit 1
fi

if [ ! -d "$REPO" ]; then
  echo "FATAL: репозиторий $REPO не найден." >&2
  exit 1
fi

say() { printf '[secret-hub] %s\n' "$*"; }

# --- 1. мастер-ключ -------------------------------------------------------
install -d -m 0700 -o root -g root "$SECRET_DIR"
if [ -e "$KEY_FILE" ]; then
  say "мастер-ключ уже существует — не трогаю (перезапись = потеря всех секретов)"
else
  say "создаю мастер-ключ $KEY_FILE"
  # Ключ пишется сразу с правами 0600: umask здесь ненадёжен, а окно, в котором
  # ключ читается миром, не нужно даже на миллисекунду.
  ( umask 077; "$REPO/.venv/bin/python" -c \
      'from factory.secret_hub.crypto import generate_master_key; print(generate_master_key())' \
      > "$KEY_FILE" )
  chown root:root "$KEY_FILE"
  chmod 0600 "$KEY_FILE"
fi

# --- 2. хранилище и группа управления ------------------------------------
install -d -m 0700 -o root -g root "$STORE_DIR"
install -d -m 0700 -o root -g root "$STORE_DIR/backups"
install -d -m 0700 -o root -g root "$STORE_DIR/consumer-backups"
install -d -m 0700 -o root -g root "$STORE_DIR/imported"

if ! getent group "$GROUP" >/dev/null; then
  say "создаю группу управления $GROUP"
  groupadd --system "$GROUP"
fi
if id "$CONTROL_USER" >/dev/null 2>&1 && ! id -nG "$CONTROL_USER" | tr ' ' '\n' | grep -qx "$GROUP"; then
  say "добавляю $CONTROL_USER в $GROUP (право спросить и запустить, но не увидеть)"
  usermod -aG "$GROUP" "$CONTROL_USER"
fi

# --- 3. зависимость шифрования -------------------------------------------
if ! "$REPO/.venv/bin/python" -c 'import cryptography' >/dev/null 2>&1; then
  say "ставлю cryptography в $REPO/.venv"
  "$REPO/.venv/bin/pip" install --quiet --require-virtualenv \
    -r "$REPO/requirements.txt"
fi

# --- 4. unit'ы ------------------------------------------------------------
say "ставлю unit'ы"
for unit in "$UNIT" \
            site-factory-secret-hub-enroll@.service \
            site-factory-secret-hub-import@.service; do
  install -m 0644 -o root -g root "$REPO/automation/secret-hub/$unit" \
          "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable --now "$UNIT"

sleep 1
if ! systemctl is-active --quiet "$UNIT"; then
  say "СЕРВИС НЕ ЗАПУСТИЛСЯ. Журнал:"
  journalctl -u "$UNIT" --no-pager -n 30
  exit 1
fi

# --- 5. состояние ---------------------------------------------------------
say "готово. Состояние:"
sudo -u "$CONTROL_USER" env PYTHONPATH="$REPO" \
  "$REPO/.venv/bin/python" -m factory secrets status || true

cat <<'EOF'

Дальше — ввод credentials. Для каждого направления отдельно:

  sudo systemctl start site-factory-secret-hub-enroll@yami.service
  sudo journalctl -u site-factory-secret-hub-enroll@yami.service -n 20 --no-pager

В журнале появится одноразовый код, адрес и отпечаток TLS. С рабочей машины:

  ssh -N -L 8443:127.0.0.1:8443 <этот-хост>

и открыть https://127.0.0.1:8443/ — сверив отпечаток сертификата.

Если credentials уже лежат на хосте файлами, вместо формы можно импортировать:

  sudo systemctl start site-factory-secret-hub-import@yami.service

Ни одна из команд не печатает значения.
EOF
