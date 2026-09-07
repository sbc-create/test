#!/usr/bin/env bash
# Браузерная приёмка боевой витрины Lords в двух движках.
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим
# именем и отвечает «command not found» на месте присваивания.
#
# Playwright установлен вне репозитория, и модуль резолвится от расположения
# сценария, а не от текущего каталога — поэтому сценарий запускается оттуда,
# где node его найдёт.
set -Eeuo pipefail
SITE="${1:?нужен адрес витрины, например https://1lordserials1.online}"
NAV="${2:-}"
MODULES="${PLAYWRIGHT_HOME:-/home/claude}"
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "${SELF}/lords_public_browser.js" "${MODULES}/.lords_public_browser.js"
LORDS_NAV="$NAV" node "${MODULES}/.lords_public_browser.js" "$SITE"
