#!/usr/bin/env bash
# Secret Hub — установка сервиса и постоянной веб-панели.
#
#     sudo /srv/site-factory/repo/bin/secret-hub-install
#     sudo /srv/site-factory/repo/bin/secret-hub-install --preflight
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

SELF="$(readlink -f "${BASH_SOURCE[0]}")"
# Корень репозитория — от расположения самого скрипта: он лежит в
# automation/secret-hub/, значит на два уровня выше. Так лончер работает из
# любого текущего каталога и не зависит от переменных окружения.
REPO="${SECRET_HUB_REPO:-$(dirname "$(dirname "$(dirname "$SELF")")")}"
HUB_UNIT=site-factory-secret-hub.service
PANEL_UNIT=site-factory-secret-panel.service
SOCKET=/run/site-factory-secret-hub/hub.sock
PY="${SECRET_HUB_VENV:-/opt/site-factory-secret-hub/venv}/bin/python"
PANEL_USER="${SECRET_HUB_PANEL_USER:-sfpanel}"
ENROLL_TTL="${SECRET_HUB_ENROLL_TTL:-3600}"

PREFLIGHT=0
for arg in "$@"; do
  case "$arg" in
    --preflight|--dry-run) PREFLIGHT=1 ;;
  esac
done

say() { printf '\n[secret-hub] %s\n' "$*"; }

# --- 0. предполётная проверка --------------------------------------------
# Ничего не меняет и не требует root. Существует затем, чтобы «команда не
# запустилась» можно было выяснить до того, как что-то будет тронуто: прежний
# лончер отсутствовал на хосте, и обнаружилось это только в момент запуска.
preflight() {
  local bad=0
  echo "  репозиторий:      $REPO"
  echo "  этот скрипт:      $SELF"

  local required=(
    "automation/secret-hub/install.sh"
    "automation/secret-hub/bootstrap-venv.sh"
    "automation/secret-hub/site-factory-secret-hub.service"
    "automation/secret-hub/site-factory-secret-panel.service"
    "automation/secret-hub/site-factory-secret-hub-import@.service"
    "config/secret-hub.json"
    "factory/secret_hub/reconcile.py"
    "bin/secret-hub-install"
  )
  local item
  for item in "${required[@]}"; do
    if [ -e "$REPO/$item" ]; then
      echo "  есть:             $item"
    else
      echo "  ОТСУТСТВУЕТ:      $item" >&2
      bad=1
    fi
  done

  # Синтаксис всех shell-частей: сломанный скрипт лучше поймать здесь.
  for item in "$REPO"/automation/secret-hub/*.sh "$REPO/bin/secret-hub-install"; do
    if bash -n "$item" 2>/dev/null; then
      echo "  синтаксис ok:     $(basename "$item")"
    else
      echo "  СИНТАКСИС СЛОМАН: $item" >&2
      bad=1
    fi
  done

  # Шаги, которые выполнит боевой запуск. Печатаются, чтобы было видно, что
  # команда действительно делает всё обещанное.
  local step
  for step in "перезапуск хаба:site-factory-secret-hub.service" \
              "перезапуск панели:site-factory-secret-panel.service" \
              "применение сохранённого:rootcmd reconcile" \
              "проверка результата:reconcile.audit"; do
    echo "  шаг:              ${step%%:*} (${step#*:})"
  done

  if [ "$(id -u)" -ne 0 ]; then
    echo "  запуск от:        не root — боевая установка потребует sudo"
  else
    echo "  запуск от:        root"
  fi
  return $bad
}

if [ "$PREFLIGHT" -eq 1 ]; then
  say "предполётная проверка (ничего не меняется)"
  if preflight; then
    say "PREFLIGHT=pass"
    exit 0
  fi
  say "PREFLIGHT=fail"
  exit 78
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "FATAL: запускать от root — команда создаёт мастер-ключ и правит nginx." >&2
  echo "нужно: sudo $REPO/bin/secret-hub-install" >&2
  exit 1
fi
[ -d "$REPO" ] || { echo "FATAL: репозиторий $REPO не найден." >&2; exit 1; }

say "предполётная проверка"
preflight || { echo "FATAL: предполётная проверка не пройдена." >&2; exit 78; }

# Интерпретатор появится на шаге установки: до него $PY ещё не существует, и
# это нормально. Проверка стоит после, а не здесь.

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
systemctl enable "$PANEL_UNIT"
# Именно restart, а не `enable --now`: для уже работающей службы `--now`
# ничего не делает, и после обновления репозитория панель продолжала бы
# крутить прежний код. Обновление кода без перезапуска — это обновление,
# которого не произошло.
systemctl restart "$PANEL_UNIT"
sleep 1
for _ in $(seq 1 15); do
  systemctl is-active --quiet "$PANEL_UNIT" && break
  sleep 1
done
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

# --- 7. применение уже сохранённых credentials ----------------------------
# Владельцу не должно оставаться отдельного клика: то, что уже сохранено и
# проверено, обязано доехать до потребителей само. Новых версий не создаётся,
# повторный ввод не требуется — работа идёт с активной версией направления.
if [ "$code" -eq 0 ]; then
  say "применение уже сохранённых credentials"
  set +e
  PYTHONPATH="$REPO" SECRET_HUB_CONFIG="$REPO/config/secret-hub.json" \
    "$PY" -m factory.secret_hub.rootcmd reconcile
  reconcile_code=$?
  set -e
  if [ "$reconcile_code" -ne 0 ]; then
    code=$reconcile_code
  fi
fi

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
