#!/usr/bin/env bash
# Поднимает витрину Zona из рабочей ветки на отдельном порту, поверх боевых
# данных, но не трогая боевой процесс.
#
# Нужен затем, что правку нельзя проверять на том же :9120, где работает
# выложенный артефакт: измерять надо новую сборку, а живую при этом не
# беспокоить. Данные читаются те же самые и только на чтение.
set -euo pipefail

PORT="${1:-9130}"
export LORDS_TEMPLATE_MANIFEST=/srv/lords/.frontend/template-manifest-zona-01.json
export LORDS_CATALOG=/srv/lords/.frontend/zona-01-catalog.json
export LORDS_DETAILS=/srv/lords/.frontend/zona-01-details.json
export LORDS_PLAYER_CONFIG=/srv/lords/.frontend/player-zona-01.json
export LORDS_SITE_NAME=Zona

exec python3 automation/host/lords-frontend.py --port "$PORT"
