#!/usr/bin/env bash
# Подключение Метрики и Topvisor перечисленным доменам — одной командой.
#
#   sudo bash automation/host/connect-analytics.sh --domains-from-registry
#   sudo bash automation/host/connect-analytics.sh zonafilm12.site lordserials22.info
#   bash automation/host/connect-analytics.sh --dry-run --domains-from-registry
#
# Зачем скрипт вместо семи команд
# ------------------------------
#
# Блок из семи строк однажды не дал НИ ОДНОГО следа: ни отчётов служб, ни
# сообщения об отказе. При вставке целиком достаточно, чтобы `sudo` спросил
# пароль на первой строке — остальные строки уходят в тот же промпт и не
# выполняются, а внешне это неотличимо от «выполнено, но ничего не произошло».
#
# Поэтому здесь: одна точка входа, `set -euo pipefail`, проверка прав до первого
# действия, и протокол в файл после КАЖДОГО шага. Провал теперь оставляет след
# по построению.
#
# Чего скрипт не делает: не печатает секретов, не меняет прав файлов, не правит
# правила разрешений, не выполняет платных операций Topvisor и не переустанавливает
# ничего, кроме пяти юнитов аналитики штатным установщиком.
set -euo pipefail

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROTOCOL="${SRC_ROOT}/var/analytics/owner-run-$(date -u +%Y%m%dT%H%M%SZ).log"
dry_run=0
from_registry=0
domains=()

for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    --domains-from-registry) from_registry=1 ;;
    -*) echo "неизвестный ключ: $arg" >&2; exit 2 ;;
    *) domains+=("$arg") ;;
  esac
done

log() { printf '\n==> %s\n' "$*" | tee -a "$PROTOCOL"; }
note() { printf '    %s\n' "$*" | tee -a "$PROTOCOL"; }

# Домены берутся из реестра аналитики, а не из аргументов по умолчанию: реестр —
# единственный список, который заводится раньше всего остального. Пустая выборка
# — отказ, а не «делать нечего»: она означает либо опечатку, либо что счётчики уже
# есть у всех, и различать эти случаи обязан вывод, а не догадка.
if [ "$from_registry" = 1 ]; then
  mapfile -t from_reg < <(python3 - "$SRC_ROOT" <<'LIST'
import json, sys
from pathlib import Path
корень = Path(sys.argv[1])
аналитика = json.loads((корень / "config" / "analytics.json").read_text(encoding="utf-8"))
ячейки = json.loads((корень / "config" / "site-cells.json").read_text(encoding="utf-8"))["cells"]
свои = {c["domain"] for c in ячейки
        if not str(c["domain"]).endswith((".localhost", ".test", ".local", ".invalid"))}
for з in аналитика["properties"]:
    if з["domain"] in свои and not з.get("counter_id"):
        print(з["domain"])
LIST
)
  domains+=("${from_reg[@]}")
fi

mkdir -p "$(dirname "$PROTOCOL")"
: > "$PROTOCOL"

if [ "${#domains[@]}" = 0 ]; then
  echo "не выбрано ни одного домена: у всех перечисленных счётчик уже есть, либо список пуст" >&2
  exit 2
fi

log "домены к подключению (${#domains[@]})"
for d in "${domains[@]}"; do note "$d"; done
note "протокол: ${PROTOCOL#"$SRC_ROOT"/}"

if [ "$dry_run" = 0 ] && [ "$(id -u)" != 0 ]; then
  # Подсказка повторяет ФАКТИЧЕСКИЙ вызов, а не пример: иначе владелец
  # запустит не то, что проверял, — ровно тот способ разойтись с проверенной
  # командой, из-за которого и появился этот скрипт.
  {
    echo "[x] нужен root: запуск служб и установка юнитов выполняются от root."
    echo
    printf '    sudo bash %s/automation/host/connect-analytics.sh' "$SRC_ROOT"
    printf ' %s' "$@"
    echo
    echo
    echo "    Секрет при этом сессии не выдаётся: его получают службы через"
    echo "    LoadCredential, и только на время своего прогона."
  } >&2
  exit 4
fi

run() {
  if [ "$dry_run" = 1 ]; then
    note "[сухой прогон] $*"
    return 0
  fi
  # Отказ шага не прерывает остальные: у каждого домена свой счётчик, и
  # неудача одного не причина не подключать пять других. Код возврата
  # запоминается и попадает в итог.
  if "$@" >>"$PROTOCOL" 2>&1; then
    note "ок: $*"
    return 0
  fi
  local rc=$?
  note "ОТКАЗ (код $rc): $*"
  return "$rc"
}

log "шаг 1: обновление юнитов аналитики штатным установщиком"
if [ "$dry_run" = 1 ]; then
  note "[сухой прогон] bash ${SRC_ROOT}/automation/host/install-analytics-readers.sh"
else
  run bash "${SRC_ROOT}/automation/host/install-analytics-readers.sh" || {
    note "установщик отказал — дальше не идём: юниты остались прежними"
    exit 3
  }
fi

failed=0
log "шаг 2: счётчики Метрики"
for d in "${domains[@]}"; do
  unit="analytics-connect@${d}.service"
  run systemctl start "$unit" || failed=$((failed + 1))
  report="${SRC_ROOT}/var/analytics/connect-${d}.json"
  if [ "$dry_run" = 1 ]; then
    note "[сухой прогон] отчёт появится: ${report#"$SRC_ROOT"/}"
  elif [ -s "$report" ]; then
    note "отчёт: ${report#"$SRC_ROOT"/} ($(wc -c <"$report") Б)"
  else
    note "ОТЧЁТА НЕТ: ${report#"$SRC_ROOT"/} — служба не запускалась"
    failed=$((failed + 1))
  fi
done

log "шаг 3: проекты Topvisor (только бесплатные операции)"
run systemctl start topvisor-connect.service || failed=$((failed + 1))
for f in connect-latest.txt check-after-connect.txt; do
  report="${SRC_ROOT}/var/topvisor/${f}"
  if [ "$dry_run" = 1 ]; then
    note "[сухой прогон] отчёт появится: ${report#"$SRC_ROOT"/}"
  elif [ -s "$report" ]; then
    note "отчёт: ${report#"$SRC_ROOT"/} ($(wc -c <"$report") Б)"
  else
    note "ОТЧЁТА НЕТ: ${report#"$SRC_ROOT"/}"
    failed=$((failed + 1))
  fi
done

log "итог"
note "шагов с отказом или без отчёта: $failed"
note "полный протокол: ${PROTOCOL#"$SRC_ROOT"/}"
note "разбор без root и без секретов: python3 automation/host/analytics-report.py"
[ "$failed" = 0 ]
