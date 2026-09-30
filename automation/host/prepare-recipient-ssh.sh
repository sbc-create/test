#!/usr/bin/env bash
# Отдельный SSH-доступ получателю: создать пару, установить публичную часть,
# ПРОВЕРИТЬ вход и сказать отдельно, что именно проверено.
#
#   bash automation/host/prepare-recipient-ssh.sh --dry-run   # только показать
#   bash automation/host/prepare-recipient-ssh.sh             # выполнить
#
# Запускать под учётной записью, которой принадлежит ~/.ssh (здесь claude).
# root не нужен: всё происходит внутри домашнего каталога.
#
# ИДЕНТИФИКАТОРЫ ЗДЕСЬ ТОЛЬКО ЛАТИНСКИЕ. `bash -n` разбирает кириллические
# имена переменных без ошибки, а при выполнении отвечает `bad substitution` — в
# этом проекте на этом обожглись шесть раз. Комментарии по-русски, код нет.
#
# ЧЕГО СЦЕНАРИЙ НЕ ДЕЛАЕТ
#
#   * не печатает приватный ключ и не копирует его никуда;
#   * не перезаписывает authorized_keys — только дописывает, и только после
#     резервной копии. Ограничения существующих записей живут в их строках,
#     поэтому дописывание их не затрагивает;
#   * не создаёт вторую пару, если файл с таким именем уже есть: повторный
#     ключ означал бы два действующих доступа там, где ожидался один;
#   * не трогает sshd_config, sudoers, DNS, firewall и соседние учётные записи.
#
# ЧТО ВАЖНО ЗНАТЬ ДО ЗАПУСКА
#
# Ключ ставится пользователю claude. На этом хосте claude входит в группы
# `sudo` и `docker`. Членство в `docker` само по себе равносильно root:
# контейнером монтируется корень хоста. То есть это НЕ «отдельный ограниченный
# доступ», а полный доступ к серверу. Если получателю нужен ограниченный —
# заводите отдельную учётную запись без этих групп, а не ключ к claude.
set -Eeuo pipefail

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

KEY_DIR="${HOME}/.ssh"
KEY_NAME="${RECIPIENT_KEY_NAME:-recipient-$(date -u +%Y%m%d)}"
KEY_PATH="${KEY_DIR}/${KEY_NAME}"
AUTH="${KEY_DIR}/authorized_keys"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

log()  { printf '[ssh-access] %s\n' "$*"; }
die()  { printf '[ssh-access] ОТКАЗ: %s\n' "$*" >&2; exit 1; }
run()  { if [ "$dry_run" = 1 ]; then printf '   [сухой прогон] %s\n' "$*"; else "$@"; fi; }

command -v ssh-keygen >/dev/null || die "ssh-keygen не найден"
[ -d "$KEY_DIR" ] || die "нет $KEY_DIR: создайте каталог с правами 700 и повторите"

# ------------------------------------------------- 1. ключ уже есть?
#
# Повторный ключ не создаётся. Если файл на месте — сценарий сообщает его
# отпечаток и переходит к установке и проверке: это отвечает на вопрос «ключ уже
# создан?» фактом, а не памятью.
created=0
if [ -f "$KEY_PATH" ]; then
  log "ключ уже существует: $KEY_PATH — повторный не создаю"
else
  log "ключа нет, создаю Ed25519: $KEY_PATH"
  log "пароль на ключ задайте НЕПУСТЫМ: тогда файл в пути передачи бесполезен сам по себе"
  # umask в подоболочке: ssh-keygen и так ставит 600, но при досрочном
  # прерывании файл не должен успеть побывать доступным для чтения группе.
  run bash -c "umask 077; ssh-keygen -t ed25519 -a 100 -C 'recipient handover ${STAMP}' -f '${KEY_PATH}'"
  created=1
fi

if [ "$dry_run" = 0 ]; then
  [ -f "$KEY_PATH" ]     || die "приватный файл не появился: $KEY_PATH"
  [ -f "${KEY_PATH}.pub" ] || die "публичный файл не появился: ${KEY_PATH}.pub"
  chmod 600 "$KEY_PATH"
  chmod 644 "${KEY_PATH}.pub"
fi

# ------------------------------------------------- 2. установка публичной части
#
# Дописывание, а не перезапись, и только после копии. Идемпотентно: если эта
# самая публичная строка уже в файле, второй раз она не добавляется.
if [ "$dry_run" = 0 ]; then
  pub="$(cat "${KEY_PATH}.pub")"
  if [ -f "$AUTH" ] && grep -qxF -- "$pub" "$AUTH"; then
    log "публичная часть уже в authorized_keys — не дублирую"
  else
    if [ -f "$AUTH" ]; then
      cp -a "$AUTH" "${AUTH}.bak-${STAMP}"
      log "резервная копия: ${AUTH}.bak-${STAMP}"
    else
      touch "$AUTH"
    fi
    printf '%s\n' "$pub" >> "$AUTH"
    chmod 600 "$AUTH"
    log "публичная часть дописана в $AUTH"
  fi
else
  printf '   [сухой прогон] %s\n' "копия ${AUTH} -> ${AUTH}.bak-${STAMP}, затем дописать ${KEY_PATH}.pub"
fi

# ------------------------------------------------- 3. что сообщать наружу
log "--- для передачи получателю ---"
log "сервер:      $(hostname -f 2>/dev/null || hostname)"
log "порт:        $(awk '/^[[:space:]]*Port[[:space:]]/{p=$2} END{print (p?p:22)}' /etc/ssh/sshd_config 2>/dev/null || echo 22)"
log "пользователь: ${USER:-$(id -un)}"
log "приватный файл: ${KEY_PATH}"
if [ "$dry_run" = 0 ]; then
  log "права приватного файла: $(stat -c '%a %U:%G' "$KEY_PATH")"
  log "отпечаток публичного ключа:"
  ssh-keygen -lf "${KEY_PATH}.pub" | sed 's/^/[ssh-access]   /'
  log "отпечатки ключей ХОСТА (для закрепления на стороне получателя):"
  for h in /etc/ssh/ssh_host_*_key.pub; do
    [ -f "$h" ] && ssh-keygen -lf "$h" | sed 's/^/[ssh-access]   /'
  done
fi

# ------------------------------------------------- 4. вход ПРОВЕРЯЕТСЯ отдельно
#
# Созданный файл и работающий вход — разные утверждения. Без этой проверки
# отчёт сказал бы «доступ готов», не зная, пускает ли sshd.
if [ "$dry_run" = 1 ]; then
  printf '   [сухой прогон] %s\n' "пробный вход: ssh -i ${KEY_PATH} -o IdentitiesOnly=yes ... ${USER:-claude}@127.0.0.1 true"
  log "сухой прогон завершён: ничего не менялось"
  exit 0
fi

log "--- проверка входа новым ключом ---"
login_ok=0
if ssh -i "$KEY_PATH" -o IdentitiesOnly=yes -o BatchMode=yes \
       -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
       "${USER:-claude}@127.0.0.1" true 2>/tmp/ssh-access-check.$$; then
  login_ok=1
  log "ВХОД ПРОВЕРЕН: подключение новым ключом прошло"
else
  log "ВХОД НЕ ПРОВЕРЕН. Причина от ssh:"
  sed 's/^/[ssh-access]   /' "/tmp/ssh-access-check.$$" || true
  log "если ключ с паролем — BatchMode запрещает его спросить, и это ОЖИДАЕМО:"
  log "  повторите вручную: ssh -i ${KEY_PATH} -o IdentitiesOnly=yes ${USER:-claude}@127.0.0.1 true"
fi
rm -f "/tmp/ssh-access-check.$$"

log "--- итог ---"
log "ключ создан этим запуском: $([ "$created" = 1 ] && echo да || echo 'нет, использован существующий')"
log "вход проверен: $([ "$login_ok" = 1 ] && echo да || echo НЕТ)"
log "забрать файл: тяните со своей машины своим уже имеющимся доступом —"
log "  scp ${USER:-claude}@$(hostname -f 2>/dev/null || hostname):${KEY_PATH} ./"
log "после передачи удалите с сервера: shred -u ${KEY_PATH}"
