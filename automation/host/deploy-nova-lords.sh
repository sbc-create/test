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
# витрины. Так «один неизменяемый артефакт Lords» остаётся проверяемым
# утверждением.
#
# Обязательные переменные окружения:
#   REPO              чистый worktree-источник (не /srv/site-factory/repo)
# Опционально:
#   SOURCE_COMMIT     полный SHA (по умолчанию HEAD из REPO)
#   DESIGN_VERSION    SemVer (по умолчанию 1.1.0)
#   NOVA_INSTALL_FRONTEND=1  скопировать lords-frontend.py (+ collection_contract)
set -Eeuo pipefail

SITE="$1"        # lords-02
DOMAIN="$2"       # lordserial33.biz
PORT="$3"        # 9111
PROFILE="$4"     # lords-new
SITENAME="$5"         # Lordserial
BUILD_ID="$6"    # общий для семейства
ART="$7"         # общий отпечаток артефакта

REPO="${REPO:?REPO must point to the clean source worktree}"
FRONT=/srv/lords/.frontend
COMMIT="${SOURCE_COMMIT:-$(git -C "$REPO" rev-parse HEAD)}"
RUNTIME_COMMIT="${RUNTIME_COMMIT:-$COMMIT}"
RUNTIME_REPO="${RUNTIME_REPO:-$REPO}"
DESIGN_VERSION="${DESIGN_VERSION:-1.1.0}"

case "${COMMIT}" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;;
  *) echo "[nova] ОТКАЗ: SOURCE_COMMIT должен быть полным SHA40, получено: ${COMMIT}" >&2; exit 1 ;;
esac
case "${RUNTIME_COMMIT}" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;;
  *) echo "[nova] ОТКАЗ: RUNTIME_COMMIT должен быть полным SHA40, получено: ${RUNTIME_COMMIT}" >&2; exit 1 ;;
esac

echo "[nova] ${SITE} → ${DOMAIN}:${PORT} профиль ${PROFILE} source ${COMMIT:0:12} runtime ${RUNTIME_COMMIT:0:12} from ${REPO}"

if [[ "${NOVA_INSTALL_FRONTEND:-0}" == "1" ]]; then
  test -s "${RUNTIME_REPO}/automation/host/lords-frontend.py" \
    || { echo "[nova] нет ${RUNTIME_REPO}/automation/host/lords-frontend.py" >&2; exit 1; }
  install -m 0755 "${RUNTIME_REPO}/automation/host/lords-frontend.py" "${FRONT}/lords-frontend.py"
  if [[ -s "${RUNTIME_REPO}/factory/lords/collection_contract.py" ]]; then
    install -m 0644 "${RUNTIME_REPO}/factory/lords/collection_contract.py" "${FRONT}/collection_contract.py"
  fi
  echo "[nova] установлен frontend runtime из ${RUNTIME_REPO} (${RUNTIME_COMMIT:0:12})"
fi

# 1. Каталог из уже отрисованных страниц витрины.
if [ ! -s "${FRONT}/${SITE}-catalog.json" ]; then
  python3 "${REPO}/automation/host/lords-extract-catalog.py" \
    --site-root "/srv/lords/${SITE}/current/site" \
    --out "${FRONT}/${SITE}-catalog.json"
fi
chmod 644 "${FRONT}/${SITE}-catalog.json"

# 2. Манифест витрины: source_commit профиля и runtime_commit общего frontend.
python3 - "$SITE" "$PROFILE" "$COMMIT" "$RUNTIME_COMMIT" "$BUILD_ID" "$ART" "$DESIGN_VERSION" <<'PY'
import json, sys, time
from pathlib import Path
сайт, профиль, коммит, рантайм, сборка, арт, версия = sys.argv[1:8]
Path(f"/srv/lords/.frontend/template-manifest-{сайт}.json").write_text(json.dumps({
    "schema_version": 1,
    "template_family": "lords",
    "design_version": версия,
    "source_commit": коммит,
    "runtime_commit": рантайм,
    "build_id": сборка,
    "artifact_sha256": арт,
    "profile": профиль,
    "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[nova] манифест {сайт}: {версия} source={коммит[:12]} runtime={рантайм[:12]} {сборка}")
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
systemctl restart "nova-${SITE}.service"
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
