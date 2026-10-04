#!/usr/bin/env bash
# Открыть Qwen ШТАТНУЮ операцию индексации через мост MCP.
#
#   sudo bash /home/claude/wt-portable-site-cell-01/automation/host/enable-mcp-write-mode.sh
#   sudo bash /home/claude/wt-portable-site-cell-01/automation/host/enable-mcp-write-mode.sh --undo
#
# Что меняется и что НЕ меняется
# ------------------------------
# Служба моста запущена с `--read-only`: пишущие инструменты она не объявляет
# вовсе. Это ограничение ПОДКЛЮЧЕНИЯ, а не операции — та же смена режима всё
# время была доступна командой на сервере. Здесь ограничение снимается
# systemd-врезкой, сам юнит не правится, откат — удалением врезки.
#
# Открыть production-домен этим нельзя, и это измерение, а не обещание:
# предпроверка операции требует ОТДЕЛЬНО разрешение владельца
# (`indexing.open_authorized` в реестре ячеек) и разрешение выпуска
# (`indexing.release_permits_open` в выложенном `config/site.json`). 2026-10-04
# в режиме записи попытка открыть `lordserials22.info` и `zonafilm.cc` отклонена
# до единой записи с названием ОБОИХ недостающих разрешений. Этот сценарий
# скрипт проверяет сам, после перезапуска службы, и при неудаче возвращает
# режим только чтения.
#
# Имена переменных только ASCII — требование bash (tests/unit/test_host_scripts_ascii.py).
set -Eeuo pipefail

UNIT="site-factory-mcp.service"
DROPIN_DIR="/etc/systemd/system/${UNIT}.d"
DROPIN="${DROPIN_DIR}/10-write-mode.conf"
ROOT_DIR="/home/claude/wt-portable-site-cell-01"
# Домен для ПРОБЫ отказа. Только изолированная ячейка реестра: проба делает
# настоящий вызов set_indexing_mode с mode=open, и на production-домене это
# попытка его открыть.
#
# Прежде здесь стоял lordserials22.info, и пока разрешения владельца не было,
# проба «проходила»: отказ приходил от предпроверки. Как только владелец выдал
# разрешение (2026-10-04), та же проба начала подавать настоящую заявку
# исполнителю — то есть установка режима записи пыталась открыть production. То
# же самое нашлось и в прогоне тестов (решение D145). Проверять отказ можно
# только на субъекте, открытие которого ничего не меняет.
PROBE_DOMAIN="${PROBE_DOMAIN:-site-a.localhost}"
MODE="enable"
[ "${1:-}" = "--undo" ] && MODE="undo"

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
ok()  { printf '   \033[32mOK\033[0m   %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Обрезка по СИМВОЛАМ, а не по байтам.
#
# `head -c 240` рвал последний многобайтный символ русского сообщения, и вывод
# команды перестал быть валидным UTF-8: прогон, читавший её вывод,
# падал с `UnicodeDecodeError: invalid continuation byte` — не на ошибке
# команды, а на её ОТЧЁТЕ. Отчёт, который нельзя прочитать, хуже отсутствия
# отчёта: он выглядит сбоем того, что работает.
cut_chars() {
  python3 -c 'import sys
предел = int(sys.argv[1])
текст = sys.stdin.buffer.read().decode("utf-8", "replace")
sys.stdout.write(текст[:предел])' "$1"
}

[ "$(id -u)" = 0 ] || die "нужен root: правка /etc/systemd/system и перезапуск службы"
systemctl list-unit-files "$UNIT" >/dev/null 2>&1 \
  || die "юнита $UNIT нет: сначала установка моста (install-mcp-bridge-grant.sh)"

ask() {   # ask <инструмент> <аргументы JSON>
  curl -sS -m 300 -X POST http://127.0.0.1:9000/mcp \
    -H 'Content-Type: application/json' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$2}}"
}

if [ "$MODE" = undo ]; then
  log "возврат режима только чтения"
  rm -f "$DROPIN"
  rmdir "$DROPIN_DIR" 2>/dev/null || true
  systemctl daemon-reload
  systemctl restart "$UNIT"
  sleep 2
  curl -sS -m 20 http://127.0.0.1:9000/healthz | grep -q '"read_only": true' \
    || die "служба не вернулась в режим только чтения"
  ok "режим только чтения восстановлен, врезка удалена"
  exit 0
fi

# --- 1. Врезка -------------------------------------------------------------
log "1. systemd-врезка: тот же запуск без --read-only"
install -d -m 0755 "$DROPIN_DIR"
[ -f "$DROPIN" ] && cp -a "$DROPIN" "${DROPIN}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
cat > "$DROPIN" <<DROPIN_BODY
# Пишущие инструменты моста для сессии Qwen. Создано enable-mcp-write-mode.sh.
#
# Пустой ExecStart обязателен: без него systemd добавил бы ВТОРУЮ команду
# запуска к существующей, а не заменил её.
#
# Открытие production-домена остаётся невозможным: предпроверка операции
# требует разрешение владельца и разрешение выпуска по отдельности.
[Service]
ExecStart=
ExecStart=/usr/bin/python3 -m factory.qwen.mcp --http 127.0.0.1:9000
DROPIN_BODY
chmod 0644 "$DROPIN"
ok "врезка записана: $DROPIN"

# --- 2. Перезапуск ---------------------------------------------------------
log "2. перезапуск службы"
systemctl daemon-reload
systemctl restart "$UNIT"
sleep 2
systemctl is-active "$UNIT" >/dev/null || die "служба не поднялась после правки"
HEALTH="$(curl -sS -m 20 http://127.0.0.1:9000/healthz || true)"
printf '   /healthz: %s\n' "$(printf '%s' "$HEALTH" | cut_chars 160)"
printf '%s' "$HEALTH" | grep -q '"ready": true' || die "/healthz не ответил ready"
printf '%s' "$HEALTH" | grep -q '"read_only": false' \
  || die "служба всё ещё в режиме только чтения: врезка не применилась"
ok "служба active, режим записи"

# --- 3. Инструменты объявлены ----------------------------------------------
log "3. пишущие инструменты объявлены"
TOOLS="$(curl -sS -m 30 -X POST http://127.0.0.1:9000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' || true)"
for NAME in set_indexing_mode rollback_indexing analytics_readiness; do
  printf '%s' "$TOOLS" | grep -q "\"$NAME\"" \
    || die "инструмент $NAME не объявлен: проверьте журнал службы"
  ok "объявлен $NAME"
done

# --- 4. Производственный домен НЕ открывается ------------------------------
# Главная проверка этого скрипта. Отказ обязан наступить в ПРЕДПРОВЕРКЕ, то
# есть до единой записи, и назвать недостающее разрешение владельца.
log "4. попытка открыть ${PROBE_DOMAIN} обязана быть отклонена"
BEFORE="$(ask indexing_journal "{\"site\":\"${PROBE_DOMAIN}\"}" | tr -d ' \n')"
ANSWER="$(ask set_indexing_mode "{\"site\":\"${PROBE_DOMAIN}\",\"mode\":\"open\",\"author\":\"write-mode-check\"}")"
printf '   ответ: %s\n' "$(printf '%s' "$ANSWER" | cut_chars 240)"
revert_and_die() {
  printf '\033[31m[x]\033[0m %s\n' "$1" >&2
  rm -f "$DROPIN"
  rmdir "$DROPIN_DIR" 2>/dev/null || true
  systemctl daemon-reload
  systemctl restart "$UNIT" || true
  printf '   режим только чтения возвращён\n' >&2
  exit 1
}
printf '%s' "$ANSWER" | grep -q '"isError": *true' \
  || revert_and_die "попытка открытия НЕ отклонена: режим записи возвращён в только чтение"
printf '%s' "$ANSWER" | grep -q 'владелец не разрешал' \
  || revert_and_die "отказ не называет причину предпроверки (разрешение владельца или разрешение выпуска)"
ok "открытие отклонено предпроверкой, разрешение владельца названо"

AFTER="$(ask indexing_journal "{\"site\":\"${PROBE_DOMAIN}\"}" | tr -d ' \n')"
[ "$BEFORE" = "$AFTER" ] \
  || revert_and_die "состояние домена изменилось при отклонённой попытке"
ok "файл состояния и журнал домена не изменились"

log "готово"
cat <<'SUMMARY'
   Сессии Qwen доступны штатные операции: set_indexing_mode, rollback_indexing,
   confirm_indexing, domain_indexing_readiness, indexing_journal,
   analytics_readiness и чтение реестра. Открытие домена по-прежнему требует
   ОТДЕЛЬНО разрешения владельца в реестре ячеек и разрешающего выпуска.

   Возврат режима только чтения одной командой:
     sudo bash /home/claude/wt-portable-site-cell-01/automation/host/enable-mcp-write-mode.sh --undo
SUMMARY
