#!/usr/bin/env bash
# Secret Hub — установка сервиса и постоянной веб-панели.
#
#     sudo bash /srv/site-factory/repo/var/install-secret-hub.sh
#
# Root нужен ровно один раз — здесь. После этого владелец работает только через
# браузер: открывает панель, входит по passkey, вводит и заменяет credentials,
# применяет их к направлениям. Ни sudo, ни SSH, ни консоль больше не требуются.
#
# Что делает:
#   1. ставит Secret Hub (мастер-ключ, хранилище, группа, unit'ы) и запускает его;
#   2. заводит непривилегированную учётную запись панели и ставит её unit;
#   3. прописывает постоянный location панели в nginx и перезагружает его;
#   4. проверяет на РЕАЛЬНОМ хосте, что панель отвечает 200 без пароля, отдаёт
#      свою метку, основной сайт жив, сертификат домена валиден, журнал выключен;
#   5. выдаёт одноразовый код первичной регистрации passkey;
#   6. печатает адрес панели, код и срок его действия.
#
# Чего не делает: не спрашивает API Token в консоли, не импортирует прежние
# credentials Yami и Lords (владелец вводит их заново и осознанно), не трогает
# DNS, индексацию, Вебмастер и базы сайтов, не ставит и не восстанавливает
# Basic Auth, не печатает значений секретов.
set -euo pipefail

REPO="${SECRET_HUB_REPO:-/srv/site-factory/repo}"
HUB_UNIT=site-factory-secret-hub.service
PANEL_UNIT=site-factory-secret-panel.service
SOCKET=/run/site-factory-secret-hub/hub.sock
PY="${SECRET_HUB_VENV:-/opt/site-factory-secret-hub/venv}/bin/python"
PANEL_USER="${SECRET_HUB_PANEL_USER:-sfpanel}"
ENROLL_TTL="${SECRET_HUB_ENROLL_TTL:-3600}"

if [ "$(id -u)" -ne 0 ]; then
  echo "FATAL: запускать от root — команда создаёт мастер-ключ и правит nginx." >&2
  echo "нужно: sudo bash var/install-secret-hub.sh" >&2
  exit 1
fi
[ -d "$REPO" ] || { echo "FATAL: репозиторий $REPO не найден." >&2; exit 1; }

# Интерпретатор появится на шаге установки: до него $PY ещё не существует, и
# это нормально. Проверка стоит после, а не здесь.

say() { printf '\n[secret-hub] %s\n' "$*"; }

# --- 1. сервис хаба -------------------------------------------------------
say "установка сервиса"
bash "$REPO/automation/secret-hub/install.sh"

if ! systemctl is-active --quiet "$HUB_UNIT"; then
  echo "FATAL: $HUB_UNIT не запущен. Журнал:" >&2
  journalctl -u "$HUB_UNIT" --no-pager -n 30 >&2
  exit 1
fi
[ -S "$SOCKET" ] || { echo "FATAL: сокет $SOCKET отсутствует." >&2; exit 1; }
echo "  $HUB_UNIT: active, сокет на месте"

# --- 2. учётная запись и unit панели --------------------------------------
say "учётная запись панели"
if ! id "$PANEL_USER" >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$PANEL_USER"
  echo "  создан пользователь $PANEL_USER"
fi
usermod -aG sfhub "$PANEL_USER"
install -d -m 0700 -o "$PANEL_USER" -g "$PANEL_USER" /var/lib/site-factory-secret-panel

say "unit панели"
install -m 0644 -o root -g root \
  "$REPO/automation/secret-hub/$PANEL_UNIT" "/etc/systemd/system/$PANEL_UNIT"
systemctl daemon-reload
systemctl enable --now "$PANEL_UNIT"
sleep 1
if ! systemctl is-active --quiet "$PANEL_UNIT"; then
  echo "FATAL: $PANEL_UNIT не запустился. Журнал:" >&2
  journalctl -u "$PANEL_UNIT" --no-pager -n 30 >&2
  exit 1
fi
echo "  $PANEL_UNIT: active"

# --- 3-6. nginx, живая проверка, код регистрации --------------------------
# Всё остальное делает Python: там же, где живёт разбор конфигурации nginx и
# живые проверки, и там же, где им место — в коде, покрытом тестами.
say "публикация панели и живая проверка на установленном nginx"
set +e
PYTHONPATH="$REPO" SECRET_HUB_CONFIG="$REPO/config/secret-hub.json" \
  "$PY" -m factory.secret_hub.rootcmd install-panel --enroll-ttl "$ENROLL_TTL" "$@"
code=$?
set -e

if [ "$code" -ne 0 ]; then
  cat >&2 <<'EOF'

Панель не установлена или живая проверка не пройдена.

Адрес и код регистрации в этом случае намеренно НЕ печатались: отправлять
владельца вводить credentials, не убедившись, что панель отвечает и никого не
сломала, нельзя. Конфигурация nginx возвращена в прежнее состояние, основной
сайт не тронут.

Значения секретов не выводились ни при каком исходе.
EOF
fi
exit "$code"
