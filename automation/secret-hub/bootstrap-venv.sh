#!/usr/bin/env bash
# Отдельное окружение Secret Hub. Создаётся установщиком, живёт вне репозитория
# и вне /home.
#
# Зачем отдельное, а не `.venv` репозитория
# -----------------------------------------
# Боевая установка упала так:
#
#   Failed to locate executable /srv/site-factory/repo/.venv/bin/python:
#   No such file or directory        status=203/EXEC
#
# Файл при этом существовал и открывался руками. Причина в двух вещах сразу:
#
#   1. `.venv/bin/python` был симлинком в /home/<пользователь>/.local/share/uv/…,
#      а unit'ы Secret Hub закрывают /home директивой ProtectHome=true. Для
#      службы этого пути просто нет — `ls` его видит, systemd нет.
#   2. `.venv` в .gitignore, поэтому на действительно чистом checkout его нет
#      вовсе.
#
# Отсюда правило: интерпретатор службы обязан лежать там, куда служба имеет
# доступ, и создаваться установкой, а не оказываться там случайно.
#
# Почему не «просто системный python»
# -----------------------------------
# Тихий откат на /usr/bin/python3 — это и есть тот способ, которым служба
# однажды объявляет себя настроенной и падает на ImportError. Базовый
# интерпретатор здесь выбирается явно, проверяется на пригодность и печатается;
# если подходящего нет, установка отказывается с внятной причиной.
set -euo pipefail

VENV="${SECRET_HUB_VENV:-/opt/site-factory-secret-hub/venv}"
REPO="${SECRET_HUB_REPO:-/srv/site-factory/repo}"
REQUIREMENTS="$REPO/requirements.txt"

#: Модули, без которых служба неработоспособна. Проверяются импортом, а не
#: наличием файлов: установленный, но несобираемый пакет — не установленный.
REQUIRED_MODULES=(cryptography webauthn jsonschema yaml)

say() { printf '[venv] %s\n' "$*"; }
die() { printf '[venv] FATAL: %s\n' "$*" >&2; exit 78; }   # EX_CONFIG

# --- выбор базового интерпретатора ---------------------------------------
# Явный список кандидатов в порядке предпочтения. Переменная окружения
# позволяет назвать интерпретатор прямо — это не откат, а осознанный выбор
# оператора.
candidates=()
[ -n "${SECRET_HUB_PYTHON:-}" ] && candidates+=("$SECRET_HUB_PYTHON")
candidates+=(/usr/bin/python3.13 /usr/bin/python3.12 /usr/bin/python3.11 \
             /usr/bin/python3.10 /usr/local/bin/python3 /usr/bin/python3)

usable() {
  local py="$1"
  [ -x "$py" ] || return 1
  # Интерпретатор под /home недоступен службе с ProtectHome=true. Проверяем
  # разрешённый путь, а не сам симлинк: именно на этом установка и упала.
  local real; real="$(readlink -f "$py" 2>/dev/null || echo "")"
  [ -n "$real" ] || return 1
  case "$real" in /home/*|/root/*) return 1 ;; esac
  # Версия и модуль venv — без них создать окружение нечем.
  "$py" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
    2>/dev/null || return 1
  "$py" -c 'import venv, ensurepip' 2>/dev/null || return 1
  return 0
}

BASE=""
for candidate in "${candidates[@]}"; do
  if usable "$candidate"; then BASE="$candidate"; break; fi
done

if [ -z "$BASE" ]; then
  {
    echo "не найден пригодный интерпретатор для окружения Secret Hub."
    echo "Требуется: Python >= 3.10, вне /home и /root, с модулями venv и ensurepip."
    echo "Проверены: ${candidates[*]}"
    echo "Назначить явно: SECRET_HUB_PYTHON=/путь/к/python3 $0"
  } >&2
  exit 78
fi
say "базовый интерпретатор: $BASE ($("$BASE" --version 2>&1)) → $(readlink -f "$BASE")"

# --- проверка готовности существующего окружения --------------------------
# Идемпотентность: рабочее окружение переиспользуется, сломанное
# пересоздаётся. Ничего, кроме самого каталога окружения, не трогается.
healthy() {
  [ -x "$VENV/bin/python" ] || return 1
  local real; real="$(readlink -f "$VENV/bin/python" 2>/dev/null || echo "")"
  [ -n "$real" ] || return 1
  case "$real" in /home/*|/root/*) return 1 ;; esac
  local module
  for module in "${REQUIRED_MODULES[@]}"; do
    "$VENV/bin/python" -c "import $module" 2>/dev/null || return 1
  done
  "$VENV/bin/python" -c 'import factory.secret_hub' 2>/dev/null || return 1
  return 0
}

export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"

if healthy; then
  say "окружение $VENV уже готово — не пересоздаю"
else
  if [ -e "$VENV" ]; then
    say "окружение $VENV неполно или сломано — пересоздаю"
    # Удаляется только каталог окружения. Мастер-ключ, пользователи, группы и
    # хранилище лежат в других местах и не затрагиваются.
    rm -rf "${VENV:?}"
  fi
  # Родительский каталог создаётся, только если его нет. `install -d` меняет
  # владельца и права и у существующего — а это может быть общий каталог вроде
  # /opt, который установка Secret Hub трогать не должна.
  parent="$(dirname "$VENV")"
  if [ ! -d "$parent" ]; then
    mkdir -p "$parent"
    chmod 0755 "$parent"
    [ "$(id -u)" -eq 0 ] && chown root:root "$parent"
  fi
  say "создаю окружение $VENV"
  "$BASE" -m venv "$VENV"
  "$VENV/bin/python" -m pip install --quiet --upgrade pip
  [ -f "$REQUIREMENTS" ] || die "не найден $REQUIREMENTS"
  say "ставлю закреплённые зависимости из requirements.txt"
  "$VENV/bin/python" -m pip install --quiet -r "$REQUIREMENTS"
fi

# --- предполётная проверка ------------------------------------------------
# Выполняется всегда, в том числе для переиспользованного окружения: «было
# рабочим вчера» не является проверкой.
say "предполётная проверка"

[ -x "$VENV/bin/python" ] || die "$VENV/bin/python не исполняем"
REAL="$(readlink -f "$VENV/bin/python")"
case "$REAL" in
  /home/*|/root/*)
    die "интерпретатор указывает в $REAL — служба с ProtectHome=true его не увидит" ;;
esac
echo "  интерпретатор: $VENV/bin/python → $REAL"

missing=()
for module in "${REQUIRED_MODULES[@]}"; do
  "$VENV/bin/python" -c "import $module" 2>/dev/null || missing+=("$module")
done
[ ${#missing[@]} -eq 0 ] || die "не импортируются модули: ${missing[*]}"
echo "  зависимости: ${REQUIRED_MODULES[*]} — импортируются"

# Модули самой службы: именно они запускаются из ExecStart.
for module in factory.secret_hub.service factory.secret_hub.panel.server; do
  "$VENV/bin/python" -c "import $module" 2>/dev/null \
    || die "не импортируется $module (PYTHONPATH=$REPO)"
done
echo "  модули службы: импортируются"

# Точки входа обязаны отвечать на --help: unit запускает именно их.
"$VENV/bin/python" -m factory.secret_hub --help >/dev/null 2>&1 \
  || die "python -m factory.secret_hub не запускается"
echo "  точка входа factory.secret_hub: отвечает"

say "окружение готово: $VENV"
