#!/usr/bin/env bash
# Раскатка nova на витрину любого семейства: манифест, юнит, nginx.
#
# Имена переменных ASCII: bash не разбирает кириллическое имя как присваивание
# и исполняет строку как команду.
#
# Каталог должен быть подготовлен заранее — извлечением из отрисованных страниц
# или обходом публичного API семейства.
set -Eeuo pipefail

SITE="$1"        # zona-01
DOMAIN="$2"      # zonafilm.space
PORT="$3"        # 9120
FAMILY="$4"      # zona
PROFILE="$5"     # zona-general
SITENAME="$6"    # Zona Cinema
VERSION="$7"     # 1.0.0
BUILD_ID="$8"
ART="$9"
LEGACY="${10}"   # корень старого релиза для страниц, которых нет в новом маршруте

REPO=/home/claude/wt-integration-28
FRONT=/srv/lords/.frontend
COMMIT="$(git -C "$REPO" rev-parse HEAD)"

echo "[nova] ${SITE} → ${DOMAIN}:${PORT} семейство ${FAMILY} версия ${VERSION}"

test -s "${FRONT}/${SITE}-catalog.json" || { echo "нет каталога ${SITE}" >&2; exit 1; }
chmod 644 "${FRONT}/${SITE}-catalog.json"

python3 - "$SITE" "$FAMILY" "$PROFILE" "$COMMIT" "$BUILD_ID" "$ART" "$VERSION" <<'PY'
import json, sys, time
from pathlib import Path
сайт, семейство, профиль, коммит, сборка, арт, версия = sys.argv[1:8]
Path(f"/srv/lords/.frontend/template-manifest-{сайт}.json").write_text(json.dumps({
    "schema_version": 1,
    "template_family": семейство,
    "design_version": версия,
    "source_commit": коммит,
    "build_id": сборка,
    "artifact_sha256": арт,
    "profile": профиль,
    "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[nova] манифест {сайт}: {семейство} {версия} {сборка}")
PY
chmod 644 "${FRONT}/template-manifest-${SITE}.json"

cat > "/etc/systemd/system/nova-${SITE}.service" <<UNIT
[Unit]
Description=nova frontend: ${SITE} (${DOMAIN}) [${FAMILY}]
After=network-online.target

[Service]
Type=simple
User=lords
WorkingDirectory=${FRONT}
Environment=LORDS_TEMPLATE_MANIFEST=${FRONT}/template-manifest-${SITE}.json
Environment=LORDS_CATALOG=${FRONT}/${SITE}-catalog.json
Environment=LORDS_LEGACY_ROOT=${LEGACY}
Environment=LORDS_SITE_NAME=${SITENAME}
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 ${FRONT}/lords-frontend.py --port ${PORT}
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now "nova-${SITE}.service" >/dev/null
sleep 3
systemctl is-active "nova-${SITE}.service"

CONF="/etc/nginx/lords/${SITE}.conf"
OLDPORT="$(grep -oE '127\.0\.0\.1:[0-9]{4}' "$CONF" | head -1 | cut -d: -f2)"
cp "$CONF" "${CONF}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
sed -i "s/127\.0\.0\.1:${OLDPORT}/127.0.0.1:${PORT}/g" "$CONF"
if ! nginx -t >/dev/null 2>&1; then
  echo "[nova] ОТКАЗ: nginx -t не прошёл, возвращаю конфигурацию" >&2
  sed -i "s/127\.0\.0\.1:${PORT}/127.0.0.1:${OLDPORT}/g" "$CONF"
  exit 1
fi
systemctl reload nginx
echo "[nova] ${DOMAIN}: nginx ${OLDPORT} → ${PORT}"
