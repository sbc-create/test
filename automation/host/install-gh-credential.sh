#!/usr/bin/env bash
# Подключение учётных данных GitHub к исполнителю выпусков.
#
#   sudo bash automation/host/install-gh-credential.sh              # ввод с клавиатуры
#   sudo bash automation/host/install-gh-credential.sh --from-file /path/to/token
#   sudo bash automation/host/install-gh-credential.sh --check      # только проверить
#
# Зачем это отдельный сценарий
# ----------------------------
#
# Исполнитель обязан доказать происхождение выпуска: разрешённый репозиторий,
# разрешённая ветка, точный коммит, успешный прогон. Спрашивает он GitHub, а
# работает от root, у которого нет входа в `gh`. Без учётных данных доказать
# нечем, и заявка отвергается ДО единой операции над витриной — по замыслу.
#
# Токен не должен попасть ни в историю команд, ни в вывод, ни в журнал.
# Поэтому он не бывает аргументом: либо вводится с клавиатуры без эха, либо
# берётся из уже существующего файла по пути. Сценарий не печатает его ни
# целиком, ни частями, ни длиной.
#
# Какой токен нужен
# -----------------
#
#   тип         fine-grained personal access token
#   владелец    sbc-create
#   репозитории только site-* из реестра ячеек (Only select repositories)
#   права       Repository permissions -> Actions: Read-only
#               Repository permissions -> Metadata: Read-only (обязательна)
#   больше ничего: ни Contents, ни Workflows, ни прав организации
#
# Read-only на Actions достаточно: проверка только читает прогоны. Токен с
# правом записи дал бы службе возможность менять то, что она проверяет.
set -Eeuo pipefail
umask 077

DEST=/usr/local/lib/site-factory-cell
TOKEN_FILE="${CELL_GH_TOKEN_FILE:-/etc/site-factory/gh-token}"
UNIT_DIR=/etc/systemd/system
SERVICE=site-cell-executor.service
DROPIN="$UNIT_DIR/$SERVICE.d/gh-credential.conf"

mode=prompt
source_file=""
while [ $# -gt 0 ]; do
  case "$1" in
    --from-file) mode=file; source_file="${2:-}"; shift ;;
    --check) mode=check ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" = 0 ] || die "нужен root"
[ -f "$DEST/factory/cell/executor.py" ] || die "исполнитель не установлен в $DEST"

# Проверка идёт ИЗ КОНТЕКСТА СЛУЖБЫ, а не из этой оболочки. Успешный `gh` у
# того, кто запускает сценарий, ничего не доказывает о службе: у неё другой
# пользователь, другой HOME и учётные данные приходят от systemd. Временный
# юнит получает тот же файл тем же механизмом и исполняет тот же код.
check_in_service_context() {
  systemd-run --quiet --pipe --wait --collect \
      --unit=cell-ci-ready-probe \
      --property=LoadCredential=gh-token:"$TOKEN_FILE" \
      --property=WorkingDirectory="$DEST" \
      --property=Environment=PYTHONPATH="$DEST" \
      --property=Environment=HOME=/root \
      --property=ProtectHome=read-only \
      /usr/bin/python3 -m factory cell ci-ready
}

if [ "$mode" != check ]; then
  if [ "$mode" = file ]; then
    [ -n "$source_file" ] && [ -r "$source_file" ] || die "не читается файл токена"
    install -d -m 0750 -o root -g root "$(dirname "$TOKEN_FILE")" 2>/dev/null || true
    tmp="$(mktemp "$(dirname "$TOKEN_FILE")/.gh-token.XXXXXX")"
    tr -d ' \t\r\n' < "$source_file" > "$tmp"
  else
    install -d -m 0750 -o root -g root "$(dirname "$TOKEN_FILE")" 2>/dev/null || true
    echo "Вставьте токен и нажмите Enter. Он не отображается и не попадает в историю."
    # -s: без эха. Значение живёт только в переменной оболочки и уходит в файл.
    IFS= read -rs token || die "ввод прерван"
    echo
    tmp="$(mktemp "$(dirname "$TOKEN_FILE")/.gh-token.XXXXXX")"
    printf '%s' "$token" | tr -d ' \t\r\n' > "$tmp"
    unset token
  fi

  # Форма проверяется без вывода значения: пустой или явно не-токен лучше
  # отвергнуть здесь, чем получить «gh не ответил» на первой же заявке.
  if [ ! -s "$tmp" ]; then rm -f "$tmp"; die "пустой токен — ничего не записано"; fi
  case "$(head -c 11 "$tmp")" in
    github_pat_|ghp_*|gho_*|ghs_*) : ;;
    *) rm -f "$tmp"; die "это не похоже на токен GitHub — ничего не записано" ;;
  esac

  chown root:root "$tmp"
  chmod 0600 "$tmp"
  mv "$tmp" "$TOKEN_FILE"
  log "токен записан в $TOKEN_FILE (root:root 0600); значение нигде не выведено"

  log "drop-in службы"
  install -d -m 0755 "$UNIT_DIR/$SERVICE.d"
  cat > "$DROPIN" <<DROP
# Учётные данные GitHub для проверки происхождения выпуска. Секрет остаётся
# файлом root; systemd кладёт его в \$CREDENTIALS_DIRECTORY только на время
# работы службы, вне окружения процесса и вне журнала.
[Service]
LoadCredential=gh-token:$TOKEN_FILE
DROP
  chmod 0644 "$DROPIN"
  systemctl daemon-reload
  log "  $DROPIN"
fi

[ -f "$TOKEN_FILE" ] || die "нет $TOKEN_FILE: выпуск заблокирован, доказывать происхождение нечем"
[ -f "$DROPIN" ] || die "нет $DROPIN: служба не получит учётные данные"

log "проверка доступа ИЗ КОНТЕКСТА СЛУЖБЫ"
if check_in_service_context; then
  echo
  printf '\033[32mГОТОВ К ВЫПУСКУ\033[0m: служба доказывает происхождение по всем репозиториям.\n'
  exit 0
fi
echo
printf '\033[31mВЫПУСК ЗАБЛОКИРОВАН\033[0m: служба не может спросить GitHub (см. blocked выше).\n'
printf 'Заявки будут отвергаться ДО единой операции над витринами — это исправно.\n'
exit 1
