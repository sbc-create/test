#!/usr/bin/env bash
# Раскатка nova на витрину любого семейства: манифест, юнит, nginx.
#
# Имена переменных ASCII: bash не разбирает кириллическое имя как присваивание
# и исполняет строку как команду.
#
# Каталог должен быть подготовлен заранее — извлечением из отрисованных страниц
# или обходом публичного API семейства.
#
# Обязательные переменные окружения:
#   REPO              чистый worktree-источник (не /srv/site-factory/repo)
# Опционально:
#   SOURCE_COMMIT     полный SHA (по умолчанию HEAD из REPO)
#   NOVA_INSTALL_FRONTEND=1  скопировать lords-frontend.py (+ collection_contract)
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

REPO="${REPO:?REPO must point to the clean source worktree}"
FRONT=/srv/lords/.frontend
COMMIT="${SOURCE_COMMIT:-$(git -C "$REPO" rev-parse HEAD)}"
# runtime_commit — SHA общего lords-frontend.py. Не подменяет source_commit.
RUNTIME_COMMIT="${RUNTIME_COMMIT:-$COMMIT}"
RUNTIME_REPO="${RUNTIME_REPO:-$REPO}"

case "${COMMIT}" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;;
  *) echo "[nova] ОТКАЗ: SOURCE_COMMIT должен быть полным SHA40, получено: ${COMMIT}" >&2; exit 1 ;;
esac
case "${RUNTIME_COMMIT}" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;;
  *) echo "[nova] ОТКАЗ: RUNTIME_COMMIT должен быть полным SHA40, получено: ${RUNTIME_COMMIT}" >&2; exit 1 ;;
esac

echo "[nova] ${SITE} → ${DOMAIN}:${PORT} семейство ${FAMILY} версия ${VERSION} source ${COMMIT:0:12} runtime ${RUNTIME_COMMIT:0:12} from ${REPO}"

if [[ "${NOVA_INSTALL_FRONTEND:-0}" == "1" ]]; then
  test -s "${RUNTIME_REPO}/automation/host/lords-frontend.py" \
    || { echo "[nova] нет ${RUNTIME_REPO}/automation/host/lords-frontend.py" >&2; exit 1; }
  install -m 0755 "${RUNTIME_REPO}/automation/host/lords-frontend.py" "${FRONT}/lords-frontend.py"
  if [[ -s "${RUNTIME_REPO}/factory/lords/collection_contract.py" ]]; then
    install -m 0644 "${RUNTIME_REPO}/factory/lords/collection_contract.py" "${FRONT}/collection_contract.py"
  fi
  echo "[nova] установлен frontend runtime из ${RUNTIME_REPO} (${RUNTIME_COMMIT:0:12})"
fi

test -s "${FRONT}/${SITE}-catalog.json" || { echo "нет каталога ${SITE}" >&2; exit 1; }
chmod 644 "${FRONT}/${SITE}-catalog.json"

python3 - "$SITE" "$FAMILY" "$PROFILE" "$COMMIT" "$RUNTIME_COMMIT" "$BUILD_ID" "$ART" "$VERSION" <<'PY'
import json, sys, time
from pathlib import Path
сайт, семейство, профиль, коммит, рантайм, сборка, арт, версия = sys.argv[1:9]
Path(f"/srv/lords/.frontend/template-manifest-{сайт}.json").write_text(json.dumps({
    "schema_version": 1,
    "template_family": семейство,
    "design_version": версия,
    "source_commit": коммит,
    "runtime_commit": рантайм,
    "build_id": сборка,
    "artifact_sha256": арт,
    "profile": профиль,
    "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[nova] манифест {сайт}: {семейство} {версия} source={коммит[:12]} runtime={рантайм[:12]} {сборка}")
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
systemctl restart "nova-${SITE}.service"
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
