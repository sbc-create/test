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
#      `restrict,permitopen="127.0.0.1:9000",command="/bin/false"`;
#   4. добавляет узкий блок Match в конфигурацию sshd, потому что глобально
#      проброс ЗАПРЕЩЁН (см. ниже), и проверяет её ДО перезагрузки службы.
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

КОРЕНЬ="/home/claude/wt-portable-site-cell-01"
ЮНИТ_ИСТОЧНИК="${КОРЕНЬ}/automation/host/site-factory-mcp.service"
ЮНИТ="/etc/systemd/system/site-factory-mcp.service"
УЧЁТКА="sfbridge"
ДОМ="/var/lib/site-factory-bridge"
ФРАГМЕНТ="/etc/ssh/sshd_config.d/20-site-factory-bridge.conf"
ЦЕЛЬ_ТУННЕЛЯ="127.0.0.1:9000"
МЕТКА="$(date -u +%Y%m%dT%H%M%SZ)"

# Открытый ключ канала, присланный администратором srv-qwen 2026-10-03.
# Величина публичная; закрытая часть остаётся на srv-qwen.
КЛЮЧ_ТИП="ssh-ed25519"
КЛЮЧ_ТЕЛО="AAAAC3NzaC1lZDI1NTE5AAAAIBdXYS9HsyXBfoYfC1fSpJGYkhQq2ap8y2Zcx+gXZ9AR"
КЛЮЧ_КОММЕНТ="site-factory-bridge@srv-qwen"
ОТПЕЧАТОК_ОЖИДАЕМЫЙ="SHA256:AbTvnN9WdSN8elbkKJJG0WXoV/+rVgAL14af8JNCc3g"
ОГРАНИЧЕНИЯ="restrict,permitopen=\"${ЦЕЛЬ_ТУННЕЛЯ}\",command=\"/bin/false\""

лог() { printf '\033[1m==>\033[0m %s\n' "$*"; }
беда() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" = 0 ] || беда "нужен root: служба и список ключей принадлежат ему"
[ -f "$ЮНИТ_ИСТОЧНИК" ] || беда "нет юнита $ЮНИТ_ИСТОЧНИК"

# --- 0. Отпечаток присланного ключа обязан совпасть -------------------------
лог "сверка отпечатка присланного ключа"
ВРЕМ_КЛЮЧ="$(mktemp)"
trap 'rm -f "$ВРЕМ_КЛЮЧ"' EXIT
printf '%s %s %s\n' "$КЛЮЧ_ТИП" "$КЛЮЧ_ТЕЛО" "$КЛЮЧ_КОММЕНТ" > "$ВРЕМ_КЛЮЧ"
ОТПЕЧАТОК_ФАКТ="$(ssh-keygen -lf "$ВРЕМ_КЛЮЧ" | awk '{print $2}')"
[ "$ОТПЕЧАТОК_ФАКТ" = "$ОТПЕЧАТОК_ОЖИДАЕМЫЙ" ] \
  || беда "отпечаток ключа $ОТПЕЧАТОК_ФАКТ не совпал с присланным $ОТПЕЧАТОК_ОЖИДАЕМЫЙ"
лог "   отпечаток совпал: $ОТПЕЧАТОК_ФАКТ"

# --- 1. Служба моста --------------------------------------------------------
лог "служба site-factory-mcp"
if [ -f "$ЮНИТ" ] && cmp -s "$ЮНИТ_ИСТОЧНИК" "$ЮНИТ"; then
  лог "   юнит уже установлен и совпадает"
else
  [ -f "$ЮНИТ" ] && cp -a "$ЮНИТ" "${ЮНИТ}.bak.${МЕТКА}" && лог "   копия прежнего: ${ЮНИТ}.bak.${МЕТКА}"
  install -m 0644 -o root -g root "$ЮНИТ_ИСТОЧНИК" "$ЮНИТ"
  systemctl daemon-reload
fi
systemctl enable --now site-factory-mcp.service

# --- 2. Выделенная учётная запись канала ------------------------------------
лог "учётная запись канала $УЧЁТКА"
if id -u "$УЧЁТКА" >/dev/null 2>&1; then
  лог "   уже существует"
else
  useradd --system --home-dir "$ДОМ" --create-home \
          --shell /usr/sbin/nologin --comment "site-factory MCP bridge channel" \
          "$УЧЁТКА"
  passwd -l "$УЧЁТКА" >/dev/null
  лог "   создана без оболочки и без пароля"
fi
install -d -m 0700 -o "$УЧЁТКА" -g "$УЧЁТКА" "${ДОМ}/.ssh"
СПИСОК="${ДОМ}/.ssh/authorized_keys"
[ -f "$СПИСОК" ] || install -m 0600 -o "$УЧЁТКА" -g "$УЧЁТКА" /dev/null "$СПИСОК"

# --- 3. Ключ с ограничениями, без дублей ------------------------------------
лог "разрешение туннеля для присланного ключа"
cp -a "$СПИСОК" "${СПИСОК}.bak.${МЕТКА}"
СТРОКА="${ОГРАНИЧЕНИЯ} ${КЛЮЧ_ТИП} ${КЛЮЧ_ТЕЛО} ${КЛЮЧ_КОММЕНТ}"
# Совпадение ищется по ТЕЛУ ключа: сменились ограничения — строка
# переписывается, а не добавляется второй. Остальные ключи сохраняются.
ВРЕМ_СПИСОК="$(mktemp)"
grep -v -F "$КЛЮЧ_ТЕЛО" "$СПИСОК" > "$ВРЕМ_СПИСОК" || true
printf '%s\n' "$СТРОКА" >> "$ВРЕМ_СПИСОК"
install -m 0600 -o "$УЧЁТКА" -g "$УЧЁТКА" "$ВРЕМ_СПИСОК" "$СПИСОК"
rm -f "$ВРЕМ_СПИСОК"
СКОЛЬКО="$(grep -c -F "$КЛЮЧ_ТЕЛО" "$СПИСОК")"
[ "$СКОЛЬКО" = 1 ] || беда "ключ встречается $СКОЛЬКО раз — повтор создал дубликат"
ВСЕГО="$(grep -c . "$СПИСОК")"
лог "   ключей в списке: $ВСЕГО, нашего ровно один"

# --- 4. Узкий блок Match в конфигурации sshd --------------------------------
лог "разрешение проброса ровно этой учётной записи"
[ -f "$ФРАГМЕНТ" ] && cp -a "$ФРАГМЕНТ" "${ФРАГМЕНТ}.bak.${МЕТКА}"
cat > "$ФРАГМЕНТ" <<КОНЕЦ
# Канал srv-qwen -> мост MCP фабрики. Создан install-mcp-bridge-grant.sh.
#
# Глобально проброс запрещён (01-hardening.conf: AllowTcpForwarding no), и это
# правильно. Здесь он разрешается РОВНО одной учётной записи и РОВНО на один
# адрес: порт моста в петле, где тот отвечает только чтением.
Match User ${УЧЁТКА}
    AllowTcpForwarding local
    PermitOpen ${ЦЕЛЬ_ТУННЕЛЯ}
    PermitListen none
    PermitTTY no
    X11Forwarding no
    AllowAgentForwarding no
    PermitTunnel no
    AllowStreamLocalForwarding no
КОНЕЦ
chmod 0644 "$ФРАГМЕНТ"
if ! sshd -t; then
  if [ -f "${ФРАГМЕНТ}.bak.${МЕТКА}" ]; then
    mv "${ФРАГМЕНТ}.bak.${МЕТКА}" "$ФРАГМЕНТ"
  else
    rm -f "$ФРАГМЕНТ"
  fi
  sshd -t >/dev/null 2>&1 || true
  беда "sshd -t не прошёл: конфигурация возвращена, служба НЕ перезагружалась"
fi
systemctl reload ssh 2>/dev/null || systemctl reload sshd
лог "   sshd -t пройден, служба перезагружена"

# --- 5. Проверка после установки --------------------------------------------
лог "проверка"
АКТИВНА="$(systemctl is-active site-factory-mcp.service || true)"
ВКЛЮЧЕНА="$(systemctl is-enabled site-factory-mcp.service || true)"
printf '   служба: active=%s enabled=%s\n' "$АКТИВНА" "$ВКЛЮЧЕНА"
[ "$АКТИВНА" = active ] || беда "служба не active"
[ "$ВКЛЮЧЕНА" = enabled ] || беда "служба не enabled"

ЗДОРОВЬЕ="$(curl -sS -m 10 http://127.0.0.1:9000/healthz || true)"
printf '   /healthz: %s\n' "$(printf '%s' "$ЗДОРОВЬЕ" | head -c 200)"
printf '%s' "$ЗДОРОВЬЕ" | grep -q '"ready": true' || беда "/healthz не ответил ready"
printf '%s' "$ЗДОРОВЬЕ" | grep -q '"read_only": true' \
  || беда "служба запущена НЕ в режиме только чтения"

РЕЕСТР="$(curl -sS -m 90 -X POST http://127.0.0.1:9000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"system_readiness","arguments":{}}}' || true)"
САЙТОВ="$(printf '%s' "$РЕЕСТР" | sed -n 's/.*sites[^0-9]*\([0-9][0-9]*\).*/\1/p' | head -1)"
ОТПЕЧАТОК_СПИСКА="$(printf '%s' "$РЕЕСТР" | sed -n 's/.*sites_digest[^0-9a-f]*\([0-9a-f]\{16\}\).*/\1/p' | head -1)"
printf '   реестр: сайтов=%s отпечаток=%s\n' "${САЙТОВ:-?}" "${ОТПЕЧАТОК_СПИСКА:-?}"
printf '%s' "$РЕЕСТР" | grep -q 'config/site-cells.json' \
  || беда "ответ не называет источник реестра config/site-cells.json"
[ "${САЙТОВ:-0}" -gt 0 ] || беда "реестр пуст: это не тот источник"

лог "открытые ключи сервера для known_hosts на srv-qwen"
for К in /etc/ssh/ssh_host_ed25519_key.pub /etc/ssh/ssh_host_ecdsa_key.pub; do
  [ -f "$К" ] || continue
  printf '   %s\n' "$(ssh-keygen -lf "$К")"
done
printf '\n   строка known_hosts (ed25519):\n   45.131.182.225 %s\n\n' \
  "$(awk '{print $1" "$2}' /etc/ssh/ssh_host_ed25519_key.pub)"

лог "готово"
cat <<'ИТОГ'
   Дальше на srv-qwen (tech@): в compose указать пользователя канала
   sfbridge@45.131.182.225 — НЕ claude; строку known_hosts взять из вывода выше.

   Откат:
     systemctl disable --now site-factory-mcp.service
     rm -f /etc/systemd/system/site-factory-mcp.service && systemctl daemon-reload
     rm -f /etc/ssh/sshd_config.d/20-site-factory-bridge.conf && sshd -t && systemctl reload ssh
     # ключ: удалить строку с комментарием site-factory-bridge@srv-qwen из
     # /var/lib/site-factory-bridge/.ssh/authorized_keys (рядом лежат копии .bak.<метка>)
     userdel -r sfbridge            # только если учётная запись больше не нужна
ИТОГ
