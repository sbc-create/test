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

# --- 1. отдельное окружение Secret Hub ------------------------------------
# Идёт первым, а не после ключа: этим же интерпретатором генерируется
# мастер-ключ и запускаются все unit'ы. Установка, которая пишет unit раньше,
# чем проверен интерпретатор, объявляет себя успешной и падает с 203/EXEC.
say "окружение Secret Hub"
bash "$REPO/automation/secret-hub/bootstrap-venv.sh"

# --- 2. мастер-ключ -------------------------------------------------------
install -d -m 0700 -o root -g root "$SECRET_DIR"
if [ -e "$KEY_FILE" ]; then
  say "мастер-ключ уже существует — не трогаю (перезапись = потеря всех секретов)"
else
  say "создаю мастер-ключ $KEY_FILE"
  # Ключ пишется сразу с правами 0600: umask здесь ненадёжен, а окно, в котором
  # ключ читается миром, не нужно даже на миллисекунду.
  ( umask 077; "$PY" -c \
      'from factory.secret_hub.crypto import generate_master_key; print(generate_master_key())' \
      > "$KEY_FILE" )
  chown root:root "$KEY_FILE"
  chmod 0600 "$KEY_FILE"
fi

# --- 3. хранилище и группа управления ------------------------------------
install -d -m 0700 -o root -g root "$STORE_DIR"
install -d -m 0700 -o root -g root "$STORE_DIR/backups"
install -d -m 0700 -o root -g root "$STORE_DIR/consumer-backups"
install -d -m 0700 -o root -g root "$STORE_DIR/imported"

# Родительские каталоги целей направлений. Хаб создаёт недостающие сам
# (mkdir с parents=True), но заводить их при установке дешевле: так права
# задаются один раз и явно, а не наследуются от того, кто создал первым.
# Список берётся из реестра — дописывать сюда руками ничего не нужно.
"$PY" - <<'PYEOF'
import os
from pathlib import Path
from factory.secret_hub.registry import load

for portfolio in load().portfolios:
    for consumer in portfolio.consumers:
        parent = consumer.directory.parent
        if str(parent) in ("/", "") or parent.exists():
            continue
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(parent, 0o700)
        print(f"  создан каталог цели: {parent}")
PYEOF

if ! getent group "$GROUP" >/dev/null; then
  say "создаю группу управления $GROUP"
  groupadd --system "$GROUP"
fi
if id "$CONTROL_USER" >/dev/null 2>&1 && ! id -nG "$CONTROL_USER" | tr ' ' '\n' | grep -qx "$GROUP"; then
  say "добавляю $CONTROL_USER в $GROUP (право спросить и запустить, но не увидеть)"
  usermod -aG "$GROUP" "$CONTROL_USER"
fi

# --- 4. unit'ы ------------------------------------------------------------
say "ставлю unit'ы"
# Список берётся из каталога, а не переписывается руками: unit, удалённый из
# репозитория, иначе продолжает числиться здесь, и установка падает на
# «файл не найден» при первом же чистом запуске.
for path in "$REPO"/automation/secret-hub/*.service; do
  unit="$(basename "$path")"
  install -m 0644 -o root -g root "$path" "/etc/systemd/system/$unit"
done
# Отзыв прежней одноразовой формы: её больше нет в репозитории, но на хосте
# после старой установки она могла остаться.
if [ -e /etc/systemd/system/site-factory-secret-hub-enroll@.service ]; then
  say "снимаю устаревший unit одноразовой формы"
  rm -f /etc/systemd/system/site-factory-secret-hub-enroll@.service
fi

systemctl daemon-reload
systemctl enable "$UNIT"

# Именно restart, а не только `enable --now`. Служба, застрявшая в цикле
# перезапуска после 203/EXEC, находится в состоянии `activating`, и `start`
# для неё — тишина: systemd считает, что запуск уже идёт. Прежний ExecStart
# подхватился бы только на следующем витке цикла, то есть неопределённо когда.
# `restart` применяет перечитанный unit сразу и делает восстановление
# предсказуемым.
systemctl restart "$UNIT"

# Ожидание с проверкой, а не фиксированная пауза: на медленном хосте секунды
# может не хватить, и установка объявила бы отказ по своему же таймеру.
for _ in $(seq 1 15); do
  systemctl is-active --quiet "$UNIT" && break
  sleep 1
done
if ! systemctl is-active --quiet "$UNIT"; then
  say "СЕРВИС НЕ ЗАПУСТИЛСЯ ($(systemctl is-active "$UNIT" 2>&1)). Журнал:"
  journalctl -u "$UNIT" --no-pager -n 30
  exit 1
fi
say "сервис активен"

# --- 5. состояние ---------------------------------------------------------
say "готово. Состояние:"
sudo -u "$CONTROL_USER" env PYTHONPATH="$REPO" \
  "$REPO/.venv/bin/python" -m factory secrets status || true

cat <<'EOF'

Дальше — панель. Её ставит и проверяет верхний установщик:

  sudo /srv/site-factory/repo/bin/secret-hub-install

Он опубликует https://yummyani.site/__factory-secrets, проверит панель на
работающем nginx и напечатает одноразовый код регистрации passkey.

Прежние credentials Yami и Lords НЕ импортируются автоматически: владелец
вводит их заново через панель. Ручной импорт, если он всё-таки понадобится, —
отдельная осознанная команда:

  sudo systemctl start site-factory-secret-hub-import@<направление>.service

Ни одна из команд не печатает значения.
EOF
