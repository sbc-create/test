#!/usr/bin/env bash
# Напечатать ГОТОВЫЙ блок для терминала tech@srv-qwen.
#
#   bash automation/local/print-srv-qwen-block.sh > /tmp/блок-для-srv-qwen.txt
#
# Зачем. Передачи файлов на srv-qwen нет: ключ канала несёт
# `command="/bin/false"` и `permitopen="127.0.0.1:9000"` (возможен только
# проброс на порт моста), обратного доступа в inventory нет, а мост отдаёт
# только инструменты MCP в режиме чтения. Поэтому пакет едет ВНУТРИ
# инструкции, а SHA-256 распакованного файла подтверждает версию.
#
# Этот сценарий собирает блок ИЗ ФАКТИЧЕСКОГО файла пакета и подставляет его
# настоящий SHA-256: пересказ руками исключён. Если вставка в терминал
# когда-нибудь испортит вложение, `sha256sum -c` остановит установку, и блок
# можно напечатать заново этой же командой.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PACKAGE="${ROOT_DIR}/automation/srv-qwen/connect-site-factory-bridge.sh"
TARGET_DIR="/opt/qwen/site-factory"
TARGET="${TARGET_DIR}/connect-site-factory-bridge.sh"

[ -f "$PACKAGE" ] || { printf 'нет пакета %s\n' "$PACKAGE" >&2; exit 1; }
SUM="$(sha256sum "$PACKAGE" | awk '{print $1}')"

printf '# Вставить целиком в терминал tech@srv-qwen.\n'
printf '# Пакет: connect-site-factory-bridge.sh, %s байт, SHA-256 %s\n' \
  "$(wc -c < "$PACKAGE")" "$SUM"
printf '# Блок: размещение -> сверка SHA-256 -> проверка без изменений -> установка с приёмкой.\n'
printf '# При отказе любой проверки изменения не применяются; откат — ключ --rollback.\n\n'
printf 'sudo install -d -m 0750 %s\n' "$TARGET_DIR"
printf "cat <<'SFB_PACKAGE_B64' | base64 -d | gzip -dc | sudo tee %s >/dev/null\n" "$TARGET"
# mtime=0 — вложение одинаково от прогона к прогону.
gzip -9 -n -c "$PACKAGE" | base64 | fold -w 76
printf 'SFB_PACKAGE_B64\n'
printf "printf '%%s  %%s\\\\n' %s %s | sha256sum -c - \\\\\n" "$SUM" "$TARGET"
printf '  && sudo bash %s --check \\\n' "$TARGET"
printf '  && sudo bash %s\n' "$TARGET"
