#!/usr/bin/env bash
# Постоянная read-only служба MCP + ограниченное разрешение туннеля для srv-qwen.
#
#   sudo bash /home/claude/wt-portable-site-cell-01/automation/host/install-mcp-bridge-grant.sh
#
# Делает ровно четыре вещи и каждую — идемпотентно:
#
#   1. ставит и включает службу site-factory-mcp.service
#      (`--http 127.0.0.1:9000 --read-only`, от учётной записи claude);
#   2. создаёт ВЫДЕЛЕННУЮ системную учётную запись канала (без оболочки),
#      чтобы разрешение проброса не доставалось учётной записи claude и её
#      другим ключам;
#   3. вносит открытый ключ srv-qwen с ограничениями
#      `restrict,port-forwarding,permitopen="127.0.0.1:9000",command="/bin/false"`;
#   4. добавляет узкий блок Match в конфигурацию sshd, потому что глобально
#      проброс ЗАПРЕЩЁН (см. ниже), и проверяет её ДО перезагрузки службы.
#
# ИМЕНА ПЕРЕМЕННЫХ ЗДЕСЬ ТОЛЬКО ASCII — ЭТО ТРЕБОВАНИЕ BASH, А НЕ СТИЛЬ.
# -----------------------------------------------------------------------------
# Идентификатор bash — `[A-Za-z_][A-Za-z_0-9]*`. Кириллическое имя не является
# присваиванием: `ROOT_RU="/путь"` разбирается как ЗАПУСК КОМАНДЫ с таким
# именем и даёт `No such file or directory` (rc=127). `bash -n` этого не
# находит — конструкция синтаксически законна. Ровно это сломало первый запуск
# установщика на строке 44. Так же ломаются `for ИМЯ in`, `${ИМЯ}` («bad
# substitution») и `export ИМЯ=`; хуже всего `$ИМЯ` без скобок — он молча
# раскрывается в литерал `$ИМЯ`. Правило проверяется по всем скриптам
# репозитория — `tests/unit/test_host_scripts_ascii.py`, а ИСПОЛНЕНИЕ этого
# установщика в песочнице — `tests/unit/test_install_mcp_bridge_grant.py`.
# Русский текст в комментариях, сообщениях и значениях остаётся: он
# идентификатором не является.
#
# Почему нужен блок Match, а не только ограничения в ключе
# --------------------------------------------------------
#
# Измерено на этом хосте: `/etc/ssh/sshd_config.d/01-hardening.conf` объявляет
# `AllowTcpForwarding no`. Это запрет СЕРВЕРА: при нём `permitopen` в ключе
# бессилен — сервер отклонит проброс, не дойдя до разбора ограничений ключа.
# Снимать запрет глобально нельзя: он защищает весь хост. Поэтому разрешение
# выдаётся ровно одной учётной записи и ровно на один адрес:
#
#   AllowTcpForwarding local      только локальный проброс (-L), не -R
#   PermitOpen 127.0.0.1:9000     единственная разрешённая цель
#   PermitListen none             обратные туннели (-R) запрещены
#   PermitTTY no                  PTY не выдаётся
#   X11Forwarding no              X11 запрещён
#   AllowAgentForwarding no       переброс агента запрещён
#
# Пересечение с ограничениями ключа даёт тот же результат двумя независимыми
# способами: ослабление одного места не открывает канал шире.
#
# OpenSSH на хосте — 1:8.9p1 (Ubuntu). `restrict` поддерживается с 7.2,
# `PermitListen` — с 8.0: обе директивы применимы.
#
# Резервные копии: конфигурация sshd и список ключей копируются с метками
# времени ДО правки. Откат описан в конце вывода.
set -Eeuo pipefail

ROOT_DIR="/home/claude/wt-portable-site-cell-01"
UNIT_SRC="${ROOT_DIR}/automation/host/site-factory-mcp.service"
UNIT="/etc/systemd/system/site-factory-mcp.service"
ACCOUNT="sfbridge"
ACCOUNT_HOME="/var/lib/site-factory-bridge"
SSHD_FRAGMENT="/etc/ssh/sshd_config.d/20-site-factory-bridge.conf"
TUNNEL_TARGET="127.0.0.1:9000"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

# Открытый ключ канала, присланный администратором srv-qwen 2026-10-03.
# Величина публичная; закрытая часть остаётся на srv-qwen.
KEY_TYPE="ssh-ed25519"
KEY_BODY="AAAAC3NzaC1lZDI1NTE5AAAAIBdXYS9HsyXBfoYfC1fSpJGYkhQq2ap8y2Zcx+gXZ9AR"
KEY_COMMENT="site-factory-bridge@srv-qwen"
FINGERPRINT_EXPECTED="SHA256:AbTvnN9WdSN8elbkKJJG0WXoV/+rVgAL14af8JNCc3g"
# ПОРЯДОК И СОСТАВ ЗДЕСЬ СУЩЕСТВЕННЫ.
#
# `restrict` выключает ВСЁ, включая проброс портов. `permitopen` проброс НЕ
# включает — он только ограничивает цель уже разрешённого проброса
# (sshd(8): «Limit local port forwarding with the ssh -L option such that it
# may only connect to the specified host and port»). Поэтому между ними
# обязателен `port-forwarding` — по документации того же sshd(8) «Enable port
# forwarding previously disabled by the restrict option».
#
# Без неё строка ВЫГЛЯДЕЛА разрешающей, а канал не поднялся бы вовсе: ровно
# это противоречие было в первой редакции скрипта.
#
# Что остаётся запрещённым после `restrict,port-forwarding`: оболочка и
# выполнение команд (плюс `command="/bin/false"`), PTY, переброс агента, X11,
# `~/.ssh/rc`. Обратные туннели (`-R`) отдельной опцией не включаются и
# закрыты на сервере директивой `PermitListen none`.
KEY_OPTIONS="restrict,port-forwarding,permitopen=\"${TUNNEL_TARGET}\",command=\"/bin/false\""

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" = 0 ] || die "нужен root: служба и список ключей принадлежат ему"
[ -f "$UNIT_SRC" ] || die "нет юнита $UNIT_SRC"

# --- 0. Отпечаток присланного ключа обязан совпасть -------------------------
log "сверка отпечатка присланного ключа"
TMP_KEY="$(mktemp)"
trap 'rm -f "$TMP_KEY"' EXIT
printf '%s %s %s\n' "$KEY_TYPE" "$KEY_BODY" "$KEY_COMMENT" > "$TMP_KEY"
FINGERPRINT_ACTUAL="$(ssh-keygen -lf "$TMP_KEY" | awk '{print $2}')"
[ "$FINGERPRINT_ACTUAL" = "$FINGERPRINT_EXPECTED" ] \
  || die "отпечаток ключа $FINGERPRINT_ACTUAL не совпал с присланным $FINGERPRINT_EXPECTED"
log "   отпечаток совпал: $FINGERPRINT_ACTUAL"

# --- 1. Служба моста --------------------------------------------------------
log "служба site-factory-mcp"
if [ -f "$UNIT" ] && cmp -s "$UNIT_SRC" "$UNIT"; then
  log "   юнит уже установлен и совпадает"
else
  if [ -f "$UNIT" ]; then
    cp -a "$UNIT" "${UNIT}.bak.${STAMP}"
    log "   копия прежнего: ${UNIT}.bak.${STAMP}"
  fi
  install -m 0644 -o root -g root "$UNIT_SRC" "$UNIT"
  systemctl daemon-reload
fi
systemctl enable --now site-factory-mcp.service

# --- 2. Выделенная учётная запись канала ------------------------------------
log "учётная запись канала $ACCOUNT"
if id -u "$ACCOUNT" >/dev/null 2>&1; then
  log "   уже существует"
else
  useradd --system --home-dir "$ACCOUNT_HOME" --create-home \
          --shell /usr/sbin/nologin --comment "site-factory MCP bridge channel" \
          "$ACCOUNT"
  passwd -l "$ACCOUNT" >/dev/null
  log "   создана без оболочки и без пароля"
fi
install -d -m 0700 -o "$ACCOUNT" -g "$ACCOUNT" "${ACCOUNT_HOME}/.ssh"
AUTH_KEYS="${ACCOUNT_HOME}/.ssh/authorized_keys"
[ -f "$AUTH_KEYS" ] || install -m 0600 -o "$ACCOUNT" -g "$ACCOUNT" /dev/null "$AUTH_KEYS"

# --- 3. Ключ с ограничениями, без дублей ------------------------------------
log "разрешение туннеля для присланного ключа"
cp -a "$AUTH_KEYS" "${AUTH_KEYS}.bak.${STAMP}"
KEY_LINE="${KEY_OPTIONS} ${KEY_TYPE} ${KEY_BODY} ${KEY_COMMENT}"
# Совпадение ищется по ТЕЛУ ключа: сменились ограничения — строка
# переписывается, а не добавляется второй. Остальные ключи сохраняются.
TMP_LIST="$(mktemp)"
grep -v -F "$KEY_BODY" "$AUTH_KEYS" > "$TMP_LIST" || true
printf '%s\n' "$KEY_LINE" >> "$TMP_LIST"
install -m 0600 -o "$ACCOUNT" -g "$ACCOUNT" "$TMP_LIST" "$AUTH_KEYS"
rm -f "$TMP_LIST"
COUNT_OURS="$(grep -c -F "$KEY_BODY" "$AUTH_KEYS")"
[ "$COUNT_OURS" = 1 ] || die "ключ встречается $COUNT_OURS раз — повтор создал дубликат"
COUNT_ALL="$(grep -c . "$AUTH_KEYS")"
log "   ключей в списке: $COUNT_ALL, нашего ровно один"
# Сверка СМЫСЛА, а не только наличия строки: без `port-forwarding` она
# запрещает тот самый проброс, который ей полагается разрешить, и канал не
# поднимется — отказ наступит раньше разбора `permitopen`.
grep -F "$KEY_BODY" "$AUTH_KEYS" \
  | grep -q "restrict,port-forwarding,permitopen=\"${TUNNEL_TARGET}\"" \
  || die "строка ключа без port-forwarding: restrict запрещает проброс, а permitopen его не включает"
log "   ограничения: restrict,port-forwarding,permitopen=\"${TUNNEL_TARGET}\",command=\"/bin/false\""

# --- 4. Узкий блок Match в конфигурации sshd --------------------------------
log "разрешение проброса ровно этой учётной записи"
if [ -f "$SSHD_FRAGMENT" ]; then
  cp -a "$SSHD_FRAGMENT" "${SSHD_FRAGMENT}.bak.${STAMP}"
fi
cat > "$SSHD_FRAGMENT" <<SSHD_BLOCK
# Канал srv-qwen -> мост MCP фабрики. Создан install-mcp-bridge-grant.sh.
#
# Глобально проброс запрещён (01-hardening.conf: AllowTcpForwarding no), и это
# правильно. Здесь он разрешается РОВНО одной учётной записи и РОВНО на один
# адрес: порт моста в петле, где тот отвечает только чтением.
Match User ${ACCOUNT}
    AllowTcpForwarding local
    PermitOpen ${TUNNEL_TARGET}
    PermitListen none
    PermitTTY no
    X11Forwarding no
    AllowAgentForwarding no
    PermitTunnel no
    AllowStreamLocalForwarding no
SSHD_BLOCK
chmod 0644 "$SSHD_FRAGMENT"
if ! sshd -t; then
  if [ -f "${SSHD_FRAGMENT}.bak.${STAMP}" ]; then
    mv "${SSHD_FRAGMENT}.bak.${STAMP}" "$SSHD_FRAGMENT"
  else
    rm -f "$SSHD_FRAGMENT"
  fi
  sshd -t >/dev/null 2>&1 || true
  die "sshd -t не прошёл: конфигурация возвращена, служба НЕ перезагружалась"
fi
systemctl reload ssh 2>/dev/null || systemctl reload sshd
log "   sshd -t пройден, служба перезагружена"

# --- 5. Проверка после установки --------------------------------------------
log "проверка"
SERVICE_ACTIVE="$(systemctl is-active site-factory-mcp.service || true)"
SERVICE_ENABLED="$(systemctl is-enabled site-factory-mcp.service || true)"
printf '   служба: active=%s enabled=%s\n' "$SERVICE_ACTIVE" "$SERVICE_ENABLED"
[ "$SERVICE_ACTIVE" = active ] || die "служба не active"
[ "$SERVICE_ENABLED" = enabled ] || die "служба не enabled"

HEALTH="$(curl -sS -m 10 http://127.0.0.1:9000/healthz || true)"
printf '   /healthz: %s\n' "$(printf '%s' "$HEALTH" | head -c 200)"
printf '%s' "$HEALTH" | grep -q '"ready": true' || die "/healthz не ответил ready"
printf '%s' "$HEALTH" | grep -q '"read_only": true' \
  || die "служба запущена НЕ в режиме только чтения"

REGISTRY_ANSWER="$(curl -sS -m 90 -X POST http://127.0.0.1:9000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"system_readiness","arguments":{}}}' || true)"
SITES_COUNT="$(printf '%s' "$REGISTRY_ANSWER" | sed -n 's/.*sites[^0-9]*\([0-9][0-9]*\).*/\1/p' | head -1)"
SITES_DIGEST="$(printf '%s' "$REGISTRY_ANSWER" | sed -n 's/.*sites_digest[^0-9a-f]*\([0-9a-f]\{16\}\).*/\1/p' | head -1)"
printf '   реестр: сайтов=%s отпечаток=%s\n' "${SITES_COUNT:-?}" "${SITES_DIGEST:-?}"
printf '%s' "$REGISTRY_ANSWER" | grep -q 'config/site-cells.json' \
  || die "ответ не называет источник реестра config/site-cells.json"
[ "${SITES_COUNT:-0}" -gt 0 ] || die "реестр пуст: это не тот источник"

log "открытые ключи сервера для known_hosts на srv-qwen"
for pub in /etc/ssh/ssh_host_ed25519_key.pub /etc/ssh/ssh_host_ecdsa_key.pub; do
  [ -f "$pub" ] || continue
  printf '   %s\n' "$(ssh-keygen -lf "$pub")"
done
printf '\n   строка known_hosts (ed25519):\n   45.131.182.225 %s\n\n' \
  "$(awk '{print $1" "$2}' /etc/ssh/ssh_host_ed25519_key.pub)"

log "готово"
cat <<'SUMMARY'
   Дальше на srv-qwen (tech@): в compose указать пользователя канала
   sfbridge@45.131.182.225 — НЕ claude; строку known_hosts взять из вывода выше.

   Откат:
     systemctl disable --now site-factory-mcp.service
     rm -f /etc/systemd/system/site-factory-mcp.service && systemctl daemon-reload
     rm -f /etc/ssh/sshd_config.d/20-site-factory-bridge.conf && sshd -t && systemctl reload ssh
     # ключ: удалить строку с комментарием site-factory-bridge@srv-qwen из
     # /var/lib/site-factory-bridge/.ssh/authorized_keys (рядом лежат копии .bak.<метка>)
     userdel -r sfbridge            # только если учётная запись больше не нужна
SUMMARY
