#!/usr/bin/env bash
# Установка читающего API каталога для приложения. Одна команда владельца.
#
#   sudo bash automation/host/install-app-read-api.sh            # установить
#   sudo bash automation/host/install-app-read-api.sh --rollback  # откатить
#        bash automation/host/install-app-read-api.sh --dry-run    # показать
#
# Что ставится
# ------------
#
#   /etc/systemd/system/app-read-api-animedia-01.service   служба (только чтение)
#   /etc/site-factory/secrets/app_client_key               ключ клиента (0640)
#   /etc/nginx/snippets/app-read-api-animedia-01.conf      маршрут /api/app/v1/
#   одна строка include в HTTPS-блок /etc/nginx/lords/animedia-01.conf
#
# Чего НЕ делается: ни один существующий маршрут сайта не меняется и не
# удаляется; TLS, DNS, firewall и витрины не затрагиваются; платных ресурсов не
# создаётся. Служба никуда не пишет и в сеть не выходит.
#
# Откат (`--rollback`) снимает РОВНО эти изменения: восстанавливает файл сайта
# из копии, снятой этой же установкой, убирает сниппет, останавливает и
# отключает службу. Ключ клиента остаётся: его удаление закрыло бы доступ
# приложению, а это отдельное решение владельца.
set -Eeuo pipefail

SITE_ID="animedia-01"
DOMAIN="animedia.icu"
DATA_DIR="/srv/animedia-icu/data"
PORT="9180"
BIND="127.0.0.1"
RUN_USER="claude"
KEY_FILE="/etc/site-factory/secrets/app_client_key"
UNIT="app-read-api-${SITE_ID}.service"
UNIT_PATH="/etc/systemd/system/${UNIT}"
SNIPPET="/etc/nginx/snippets/app-read-api-${SITE_ID}.conf"
SITE_CONF="/etc/nginx/lords/${SITE_ID}.conf"
SRC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVICE_SCRIPT="${SRC_ROOT}/automation/host/app-read-api.py"
# Служба обязана жить НЕ в рабочем дереве сессии: дерево может быть снято
# (`git worktree remove`), и тогда юнит остался бы без ExecStart. Код
# копируется в ту же раскладку, где уже живут хостовые сценарии фабрики.
INSTALL_DIR="/usr/local/lib/site-factory"
INSTALLED_SCRIPT="${INSTALL_DIR}/app-read-api-${SITE_ID}.py"
MARK="app-read-api-${SITE_ID}"

dry_run=0
rollback=0
case "${1:-}" in
  --dry-run) dry_run=1 ;;
  --rollback) rollback=1 ;;
  "") : ;;
  *) printf 'неизвестный аргумент %s\n' "$1" >&2; exit 2 ;;
esac

die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 2; }
log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
ok()  { printf '   \033[32mOK\033[0m   %s\n' "$*"; }
run() { if [ "$dry_run" = 1 ]; then printf '   [сухой прогон] %s\n' "$*"; else "$@"; fi; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"

# --- откат ------------------------------------------------------------------
if [ "$rollback" = 1 ]; then
  log "откат только изменений этой установки"
  if [ -f "$SITE_CONF" ] && grep -q "$MARK" "$SITE_CONF"; then
    BACKUP="$(ls -1t "${SITE_CONF}.before-${MARK}".* 2>/dev/null | head -1 || true)"
    if [ -n "$BACKUP" ]; then
      run cp -p "$BACKUP" "$SITE_CONF"
      ok "файл сайта восстановлен из $BACKUP"
    else
      # Копии нет — убирается РОВНО наша строка, остальное не трогается.
      run sed -i "\|include ${SNIPPET};|d" "$SITE_CONF"
      ok "строка include убрана (копии не нашлось)"
    fi
  else
    ok "в файле сайта наших изменений нет"
  fi
  run rm -f "$SNIPPET"
  run nginx -t
  run systemctl reload nginx
  run systemctl disable --now "$UNIT"
  run rm -f "$UNIT_PATH"
  run rm -f "$INSTALLED_SCRIPT" "${INSTALL_DIR}/app-read-api-${SITE_ID}.doc.md"
  run systemctl daemon-reload
  ok "служба остановлена и отключена; ключ клиента оставлен на месте"
  exit 0
fi

# --- проверки до изменений --------------------------------------------------
log "проверки до изменений"
[ -f "$SERVICE_SCRIPT" ] || die "нет файла службы: $SERVICE_SCRIPT"
"${PYTHON:-/usr/bin/python3}" -m py_compile "$SERVICE_SCRIPT" >/dev/null \
  || die "файл службы не компилируется"
ok "файл службы компилируется"

[ -d "$DATA_DIR" ] || die "нет каталога данных: $DATA_DIR"
for name in "${SITE_ID}-catalog.json" "${SITE_ID}-details.json"; do
  [ -r "${DATA_DIR}/${name}" ] || die "не читается ${DATA_DIR}/${name}"
done
# Чтение проверяется ИМЕННО учётной записью службы, а не root: у root права
# есть всегда, и проверка от него ничего не доказывает. Способ зависит от того,
# кто запустил: root переключается через su, а сама учётная запись проверяет
# напрямую — su от неё спрашивал бы пароль и валил сухой прогон.
as_run_user() {
  if [ "$(id -un)" = "$RUN_USER" ]; then sh -c "$1"; else su -s /bin/sh -c "$1" "$RUN_USER"; fi
}
as_run_user "test -r '${DATA_DIR}/${SITE_ID}-details.json'" \
  || die "учётная запись ${RUN_USER} не читает снимок ${DATA_DIR}"
ok "снимок читается учётной записью ${RUN_USER}"

[ -f "$SITE_CONF" ] || die "нет конфигурации сайта: $SITE_CONF"
grep -q "server_name ${DOMAIN}" "$SITE_CONF" \
  || die "в $SITE_CONF нет server_name ${DOMAIN}: не тот файл"
grep -q "listen 443 ssl" "$SITE_CONF" \
  || die "в $SITE_CONF нет блока HTTPS: открывать API по HTTP нельзя"
ok "конфигурация сайта найдена, HTTPS-блок на месте"

UPSTREAM_CONF="/etc/nginx/conf.d/site-cells-upstreams.conf"
grep -q "cell_${SITE_ID//-/_}" "$UPSTREAM_CONF" 2>/dev/null \
  && ok "upstream витрины объявлен (её маршруты не затрагиваются)" \
  || log "[!] upstream витрины не найден в $UPSTREAM_CONF — маршруты сайта не трогаются всё равно"

if grep -q "$MARK" "$SITE_CONF"; then
  ok "include уже стоит: повторная установка ничего не удвоит"
fi

# --- ключ клиента -----------------------------------------------------------
#
# Ключ создаётся ЗДЕСЬ, если его нет: без него служба данные не отдаёт вовсе, и
# «поставил, но не работает» было бы худшим исходом установки. Значение
# печатается ОДИН раз и только при создании — в отчёты и журналы оно не идёт.
log "ключ клиента"
run install -d -m 0750 -o root -g "$RUN_USER" "$(dirname "$KEY_FILE")"
if [ -s "$KEY_FILE" ]; then
  ok "ключ уже существует: не перезаписываю"
else
  if [ "$dry_run" = 1 ]; then
    printf '   [сухой прогон] создать %s (0640 root:%s) со случайным значением\n' \
      "$KEY_FILE" "$RUN_USER"
  else
    umask 027
    "${PYTHON:-/usr/bin/python3}" -c \
      "import secrets,sys; sys.stdout.write(secrets.token_urlsafe(32))" > "$KEY_FILE"
    chown "root:${RUN_USER}" "$KEY_FILE"
    chmod 0640 "$KEY_FILE"
    ok "ключ создан: $KEY_FILE (0640 root:${RUN_USER})"
    printf '   ЗНАЧЕНИЕ КЛЮЧА (показывается один раз, в отчёты не попадает):\n   %s\n' \
      "$(cat "$KEY_FILE")"
  fi
fi
if [ "$dry_run" = 0 ]; then
  as_run_user "test -r '${KEY_FILE}'" \
    || die "учётная запись ${RUN_USER} не читает ключ ${KEY_FILE}"
  ok "ключ читается учётной записью ${RUN_USER}"
fi

# --- код службы в стабильное место ------------------------------------------
log "код службы ${INSTALLED_SCRIPT}"
run install -d -m 0755 -o root -g root "$INSTALL_DIR"
run install -m 0644 -o root -g root "$SERVICE_SCRIPT" "$INSTALLED_SCRIPT"
# Контракт рядом с кодом: иначе Documentation юнита указывал бы в снятое дерево.
run install -m 0644 -o root -g root "${SRC_ROOT}/docs/APP_READ_API.md" \
    "${INSTALL_DIR}/app-read-api-${SITE_ID}.doc.md"
ok "код службы и контракт не зависят от рабочего дерева сессии"

# --- служба -----------------------------------------------------------------
log "служба ${UNIT}"
TMP_UNIT="$(mktemp)"
cat > "$TMP_UNIT" <<UNITFILE
[Unit]
Description=Читающее API каталога ${DOMAIN} для мобильного/TV-клиента
Documentation=file://${INSTALL_DIR}/app-read-api-${SITE_ID}.doc.md
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALLED_SCRIPT} --site ${SITE_ID} \\
    --data-dir ${DATA_DIR} --bind ${BIND} --port ${PORT} --key-file ${KEY_FILE}
Restart=on-failure
RestartSec=3

# Служба только читает. Запись запрещена целиком, а не обещана в описании:
# ProtectSystem=strict делает файловую систему доступной только на чтение, и
# ни одного ReadWritePaths здесь нет намеренно.
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
LockPersonality=yes
MemoryDenyWriteExecute=yes
ReadOnlyPaths=${DATA_DIR} ${INSTALL_DIR}
# Измерено на снимке 8547 тайтлов: 108 МиБ. Предел с запасом, чтобы утечка
# добирала память не у витрин и не у редактора.
MemoryMax=512M
# Слушает только петлю: наружу выводит nginx того же домена.
IPAddressAllow=localhost
IPAddressDeny=any

[Install]
WantedBy=multi-user.target
UNITFILE
if [ "$dry_run" = 1 ]; then
  printf '   [сухой прогон] записать %s:\n' "$UNIT_PATH"
  sed 's/^/      /' "$TMP_UNIT"
else
  install -m 0644 -o root -g root "$TMP_UNIT" "$UNIT_PATH"
  ok "юнит записан: $UNIT_PATH"
fi
rm -f "$TMP_UNIT"
run systemctl daemon-reload
run systemctl enable --now "$UNIT"

if [ "$dry_run" = 0 ]; then
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
    sleep 5
    if curl -fsS "http://${BIND}:${PORT}/healthz" >/dev/null 2>&1; then break; fi
  done
  curl -fsS "http://${BIND}:${PORT}/healthz" >/dev/null \
    || die "служба не ответила на /healthz за минуту; маршрут nginx не ставлю"
  ok "служба отвечает на http://${BIND}:${PORT}/healthz"
fi

# --- маршрут nginx ----------------------------------------------------------
log "маршрут /api/app/v1/ для ${DOMAIN}"
TMP_SNIP="$(mktemp)"
cat > "$TMP_SNIP" <<SNIPFILE
# Маршрут читающего API каталога для приложения. Ставит
# automation/host/install-app-read-api.sh; снимается тем же сценарием с
# --rollback. Существующие маршруты витрины здесь не упоминаются и не
# меняются.
location /api/app/v1/ {
    proxy_pass http://${BIND}:${PORT};
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    # Ключ клиента приходит заголовком и обязан доезжать до службы.
    proxy_set_header X-App-Key \$http_x_app_key;
    proxy_read_timeout 15s;
    proxy_buffering on;

    # add_header в location ЗАМЕНЯЕТ унаследованный набор, поэтому
    # X-Robots-Tag серверного блока здесь пришлось бы потерять. Для API это и
    # нужно — но закрытым, а не отсутствующим: иначе путь стал бы
    # индексируемым.
    add_header X-Robots-Tag "noindex, nofollow" always;

    # Служба считает частоту сама (120 запросов в минуту на адрес); здесь
    # ограничение на размер запроса, чтобы до неё не доходил мусор.
    client_max_body_size 1k;
    limit_except GET HEAD { deny all; }
}
SNIPFILE
if [ "$dry_run" = 1 ]; then
  printf '   [сухой прогон] записать %s:\n' "$SNIPPET"
  sed 's/^/      /' "$TMP_SNIP"
else
  install -d -m 0755 /etc/nginx/snippets
  install -m 0644 -o root -g root "$TMP_SNIP" "$SNIPPET"
  ok "сниппет записан: $SNIPPET"
fi
rm -f "$TMP_SNIP"

if grep -q "$MARK" "$SITE_CONF"; then
  ok "include уже стоял — файл сайта не меняю"
else
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  run cp -p "$SITE_CONF" "${SITE_CONF}.before-${MARK}.${STAMP}"
  # Вставка в блок HTTPS: строка ставится перед `location = /healthz` ПОСЛЕДНЕГО
  # серверного блока, то есть внутри него. Так существующие location остаются
  # как есть, а новый оказывается в том же блоке, что и TLS.
  if [ "$dry_run" = 1 ]; then
    printf '   [сухой прогон] вставить include %s в HTTPS-блок %s (копия .before-%s)\n' \
      "$SNIPPET" "$SITE_CONF" "$MARK"
  else
    "${PYTHON:-/usr/bin/python3}" - "$SITE_CONF" "$SNIPPET" <<'PYINS'
import sys, pathlib
путь, сниппет = pathlib.Path(sys.argv[1]), sys.argv[2]
текст = путь.read_text(encoding="utf-8")
# Последний серверный блок — HTTPS: он объявлен после HTTP в этом файле.
начало = текст.rfind("server {")
if начало < 0:
    raise SystemExit("в файле нет серверного блока")
конец = текст.rindex("}")
блок = текст[начало:конец]
строка = f"\n    include {сниппет};\n"
путь.write_text(текст[:начало] + блок + строка + текст[конец:], encoding="utf-8")
print("   include вставлен в HTTPS-блок")
PYINS
    ok "копия снята: ${SITE_CONF}.before-${MARK}.${STAMP}"
  fi
fi

run nginx -t
run systemctl reload nginx
ok "nginx проверен и перезагружен"

log "готово; проверить снаружи"
cat <<HINT
   1. состояние:   curl -s https://${DOMAIN}/api/app/v1/../../healthz   (служебный путь закрыт — см. п.2)
   2. без ключа:   curl -s -o /dev/null -w '%{http_code}\\n' https://${DOMAIN}/api/app/v1/titles/01915145-2c16-7ba4-8353-42b73d657fdc
                   ожидается 401
   3. с ключом:    curl -s -H "X-App-Key: <значение>" https://${DOMAIN}/api/app/v1/titles/01915145-2c16-7ba4-8353-42b73d657fdc
                   ожидается 200 и JSON карточки
   4. страницы витрины обязаны отвечать как прежде:
                   curl -s -o /dev/null -w '%{http_code}\\n' https://${DOMAIN}/
   Откат только этих изменений: sudo bash $0 --rollback
HINT
