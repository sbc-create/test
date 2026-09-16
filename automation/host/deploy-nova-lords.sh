#!/usr/bin/env bash
# Раскатка Lords nova на одну витрину: каталог, манифест, юнит, nginx.
#
# ВНИМАНИЕ: имена переменных здесь ASCII. Bash допускает только
# [a-zA-Z_][a-zA-Z0-9_]*, кириллическое имя не разбирается как присваивание и
# исполняется как команда. Эта ошибка повторилась в сессии трижды.
#
# Артефакт шаблона — САМ КОД frontend, без каталога витрины. Иначе «тот же
# артефакт на трёх витринах» было бы неправдой: снимки содержимого у них
# разные, и отпечаток различался бы при одном и том же шаблоне.
#
# Версия, build_id и артефакт у семейства общие; профиль — свой у каждой
# витрины. Так «один неизменяемый артефакт Lords 1.0.0» остаётся проверяемым
# утверждением.
set -Eeuo pipefail

SITE="$1"        # lords-02
DOMAIN="$2"       # lordserial33.biz
PORT="$3"        # 9111
PROFILE="$4"     # lords-new
SITENAME="$5"         # Lordserial
BUILD_ID="$6"    # общий для семейства
ART="$7"         # общий отпечаток артефакта

REPO=/home/claude/wt-integration-28
FRONT=/srv/lords/.frontend
COMMIT="$(git -C "$REPO" rev-parse HEAD)"

echo "[nova] ${SITE} → ${DOMAIN}:${PORT} профиль ${PROFILE}"

# 1. Каталог из уже отрисованных страниц витрины.
if [ ! -s "${FRONT}/${SITE}-catalog.json" ]; then
  python3 "${REPO}/automation/host/lords-extract-catalog.py" \
    --site-root "/srv/lords/${SITE}/current/site" \
    --out "${FRONT}/${SITE}-catalog.json"
fi
chmod 644 "${FRONT}/${SITE}-catalog.json"

# 2. Манифест витрины: версия и артефакт общие, профиль свой.
python3 - "$SITE" "$PROFILE" "$COMMIT" "$BUILD_ID" "$ART" <<'PY'
import json, sys, time
from pathlib import Path
сайт, профиль, коммит, сборка, арт = sys.argv[1:6]
Path(f"/srv/lords/.frontend/template-manifest-{сайт}.json").write_text(json.dumps({
    "schema_version": 1,
    "template_family": "lords",
    "design_version": "1.0.0",
    "source_commit": коммит,
    "build_id": сборка,
    "artifact_sha256": арт,
    "profile": профиль,
    "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[nova] манифест {сайт}: 1.0.0 {сборка}")
PY
chmod 644 "${FRONT}/template-manifest-${SITE}.json"

# 3. Юнит витрины.
cat > "/etc/systemd/system/nova-${SITE}.service" <<UNIT
[Unit]
Description=Lords nova frontend: ${SITE} (${DOMAIN})
After=network-online.target

[Service]
Type=simple
User=lords
WorkingDirectory=${FRONT}
Environment=LORDS_TEMPLATE_MANIFEST=${FRONT}/template-manifest-${SITE}.json
Environment=LORDS_CATALOG=${FRONT}/${SITE}-catalog.json
Environment=LORDS_LEGACY_ROOT=/srv/lords/${SITE}/current/site
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

# 4. nginx: витрина переводится на новый порт после проверки конфигурации.
OLDPORT="$(grep -oE '127\.0\.0\.1:9[0-9]{3}' "/etc/nginx/lords/${SITE}.conf" | head -1 | cut -d: -f2)"
cp "/etc/nginx/lords/${SITE}.conf" "/etc/nginx/lords/${SITE}.conf.bak.$(date -u +%Y%m%dT%H%M%SZ)"
sed -i "s/127\.0\.0\.1:${OLDPORT}/127.0.0.1:${PORT}/g" "/etc/nginx/lords/${SITE}.conf"
if ! nginx -t >/dev/null 2>&1; then
  echo "[nova] ОТКАЗ: nginx -t не прошёл, возвращаю конфигурацию" >&2
  sed -i "s/127\.0\.0\.1:${PORT}/127.0.0.1:${OLDPORT}/g" "/etc/nginx/lords/${SITE}.conf"
  exit 1
fi
systemctl reload nginx
echo "[nova] ${DOMAIN}: nginx ${OLDPORT} → ${PORT}"
