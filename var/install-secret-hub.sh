#!/usr/bin/env bash
# Secret Hub — установка и приёмка одной командой.
#
#     sudo bash var/install-secret-hub.sh
#
# Что делает, по порядку:
#   1. ставит Secret Hub (мастер-ключ, хранилище, группа, unit'ы) и запускает сервис;
#   2. проверяет, что сервис жив и unix-сокет на месте и закрыт;
#   3. пытается импортировать уже лежащие на хосте credentials Yami и Lords —
#      внутри root-процесса, без вывода значений;
#   4. проверяет импортированное живым read-only запросом и применяет к
#      направлениям, у которых есть куда применять;
#   5. если чего-то не хватило — временно открывает форму на
#      https://<домен>/__factory-secrets, но только после того, как на
#      настоящем nginx подтвердит: endpoint отвечает 200 без пароля, отдаёт
#      метку этой сессии, основной сайт жив, сертификат домена на месте,
#      access_log выключен;
#   6. печатает адрес, одноразовый код, срок и статусы направлений;
#   7. по завершении сессии снимает endpoint и проверяет, что он отвечает 404.
#
# Чего не делает: не трогает DNS, индексацию, Вебмастер и базы сайтов; не
# ставит и не восстанавливает Basic Auth; не печатает значений секретов.
set -euo pipefail

REPO="${SECRET_HUB_REPO:-/srv/site-factory/repo}"
UNIT=site-factory-secret-hub.service
SOCKET=/run/site-factory-secret-hub/hub.sock
PY="$REPO/.venv/bin/python"

if [ "$(id -u)" -ne 0 ]; then
  echo "FATAL: запускать от root — команда читает мастер-ключ и файлы секретов." >&2
  echo "нужно: sudo bash var/install-secret-hub.sh" >&2
  exit 1
fi
if [ ! -d "$REPO" ]; then
  echo "FATAL: репозиторий $REPO не найден." >&2
  exit 1
fi

say() { printf '\n[secret-hub] %s\n' "$*"; }

# --- 1. установка ---------------------------------------------------------
say "установка"
bash "$REPO/automation/secret-hub/install.sh"

# --- 2. сервис и сокет ----------------------------------------------------
say "проверка сервиса и сокета"
if ! systemctl is-active --quiet "$UNIT"; then
  echo "FATAL: $UNIT не запущен. Журнал:" >&2
  journalctl -u "$UNIT" --no-pager -n 30 >&2
  exit 1
fi
if [ ! -S "$SOCKET" ]; then
  echo "FATAL: unix-сокет $SOCKET отсутствует — сервис не принимает команды." >&2
  exit 1
fi
# Права сокета: мир не должен иметь к нему доступа даже на подключение.
socket_mode="$(stat -c '%a' "$SOCKET")"
case "$socket_mode" in
  *[0-7][0-7][1-7]) echo "FATAL: сокет доступен миру (права $socket_mode)." >&2; exit 1 ;;
esac
echo "  $UNIT: active, сокет $SOCKET ($socket_mode)"

# --- 3-6. импорт, применение, форма, живая проверка -----------------------
say "импорт существующих credentials, применение и, если нужно, форма"
set +e
PYTHONPATH="$REPO" SECRET_HUB_CONFIG="$REPO/config/secret-hub.json" \
  "$PY" -m factory.secret_hub.rootcmd bootstrap "$@"
bootstrap_code=$?
set -e

# --- 7. итог --------------------------------------------------------------
say "итоговое состояние (значения секретов не показываются)"
PYTHONPATH="$REPO" SECRET_HUB_CONFIG="$REPO/config/secret-hub.json" \
  "$PY" -m factory secrets status || true

if [ "$bootstrap_code" -ne 0 ]; then
  cat >&2 <<'EOF'

Приёмка завершена не полностью. Что это может значить:

  * какое-то направление осталось ненастроенным — повторите запуск, форма
    откроется снова;
  * живая проверка nginx не прошла — адрес и код в этом случае намеренно НЕ
    печатались, endpoint снят, основной сайт не тронут;
  * направление в статусе BLOCKED_TARGET — его инфраструктура не передана,
    и это не ошибка запуска.

Значения секретов не выводились ни при каком исходе.
EOF
fi
exit "$bootstrap_code"
