#!/usr/bin/env bash
# Установка читающего API каталога для приложения. Одна команда владельца.
#
#   sudo bash automation/host/install-app-read-api.sh            # установить
#   sudo bash automation/host/install-app-read-api.sh --rollback  # откатить
#   sudo bash automation/host/install-app-read-api.sh --rollback-release # прежний выпуск кода
#   sudo bash automation/host/install-app-read-api.sh --rotate-key # сменить ключ
#        bash automation/host/install-app-read-api.sh --dry-run    # показать
#
# Что ставится
# ------------
#
#   /etc/systemd/system/app-read-api-animedia-01.service   служба (только чтение)
#   /etc/app-read-api/                                     каталог ключа (0710 root:claude)
#   /etc/app-read-api/client-key                           ключ клиента (0640 root:claude)
#   /etc/nginx/snippets/app-read-api-animedia-01.conf      маршрут /api/app/v1/
#   одна строка include в HTTPS-блок /etc/nginx/lords/animedia-01.conf
#
# Чего НЕ делается: ни один существующий маршрут сайта не меняется и не
# удаляется; TLS, DNS, firewall и витрины не затрагиваются; платных ресурсов не
# создаётся. Служба никуда не пишет и в сеть не выходит.
#
# Откат выпуска (`--rollback-release`) возвращает ПРЕЖНИЙ код службы и прежний
# юнит, сохранённые этой же установкой при замене (`*.previous`), и
# перезапускает службу. Маршрут, ключ и данные не трогаются. Это путь «новый код
# службы оказался плохим»; он отличается и от снятия службы целиком, и от отката
# конфигурации главной приложения (указатель канала в админке).
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
# Ключ клиента живёт в СВОЁМ каталоге, а не вместе с серверными секретами.
#
# Почему не `/etc/site-factory/secrets/`: этот каталог и его родитель —
# `0700 root:root`, то есть учётная запись службы не может даже ПРОЙТИ по пути.
# Установка 2026-10-11 на этом и остановилась: файл был создан верно
# (`0640 root:claude`), а прочитать его было нельзя — мешал не файл, а путь.
# Выдать группе проход по `/etc/site-factory` значило бы открыть дорогу и к
# настоящим серверным секретам, которые там лежат. А этот ключ серверным
# секретом НЕ является: он уезжает в APK (см. docs/APP_READ_API.md §2).
# Поэтому у него собственный каталог с проходом ровно для нужной учётной
# записи: `0710 root:<RUN_USER>` — проход есть, перечисление и доступ
# остальным закрыты, права чужих секретов не меняются вовсе.
KEY_DIR="/etc/app-read-api"
KEY_FILE="${KEY_DIR}/client-key"
#: Прежнее место. Ключ, созданный там 2026-10-11, был напечатан установщиком и
#: попал в переписку, то есть считается раскрытым. Служба его больше не читает;
#: удаление файла — отдельное решение владельца, сценарий лишь напоминает.
LEAKED_KEY_FILE="/etc/site-factory/secrets/app_client_key"
ROTATION_LOG="${KEY_DIR}/rotations.log"
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
# Опубликованные ревизии главной приложения «Кинатека» (контракт
# kinateka-config/1). Пишет Control API (учётная запись RUN_USER), служба только
# читает. Каталог в общем состоянии фабрики, а не в релизе: откат кода не должен
# уносить опубликованные ревизии.
CONFIG_DIR="/srv/site-factory/repo/var/app-config/${SITE_ID}"

dry_run=0
rollback=0
rollback_release=0
rotate_key=0
# Разбираются ВСЕ аргументы, а не только первый. Прежняя форма читала `$1` и
# молча отбрасывала остальное: `--dry-run --rotate-key` выполнялся как один
# `--dry-run`, то есть поворот ключа «проходил» ничего не сделав, а опечатка во
# втором аргументе не вызывала отказа. Поймано пробой ветки поворота.
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1; shift ;;
    --rollback) rollback=1; shift ;;
    --rollback-release) rollback_release=1; shift ;;
    --rotate-key) rotate_key=1; shift ;;
    *) printf 'неизвестный аргумент %s\n' "$1" >&2; exit 2 ;;
  esac
done
if [ "$rollback" = 1 ] && [ "$rotate_key" = 1 ]; then
  printf '%s\n' "--rollback и --rotate-key вместе не имеют смысла: откат снимает службу" >&2
  exit 2
fi

die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 2; }
log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
ok()  { printf '   \033[32mOK\033[0m   %s\n' "$*"; }
run() { if [ "$dry_run" = 1 ]; then printf '   [сухой прогон] %s\n' "$*"; else "$@"; fi; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"
if [ "$rollback_release" = 1 ] && { [ "$rollback" = 1 ] || [ "$rotate_key" = 1 ]; }; then
  die "--rollback-release выполняется отдельно"
fi

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

# --- откат выпуска кода -----------------------------------------------------
if [ "$rollback_release" = 1 ]; then
  log "возврат прежнего выпуска кода службы"
  [ -f "${INSTALLED_SCRIPT}.previous" ] || die "прежнего выпуска нет: ${INSTALLED_SCRIPT}.previous"
  # Текущий становится «прежним»: повторный вызов возвращает обратно, а не теряет выпуск.
  run cp -p "$INSTALLED_SCRIPT" "${INSTALLED_SCRIPT}.rollback-tmp"
  run cp -p "${INSTALLED_SCRIPT}.previous" "$INSTALLED_SCRIPT"
  run mv "${INSTALLED_SCRIPT}.rollback-tmp" "${INSTALLED_SCRIPT}.previous"
  if [ -f "${UNIT_PATH}.previous" ]; then
    # Юнит вместе с кодом: аргументы запуска нового выпуска (--config-dir)
    # прежний код не знает и упал бы на старте.
    run cp -p "$UNIT_PATH" "${UNIT_PATH}.rollback-tmp"
    run cp -p "${UNIT_PATH}.previous" "$UNIT_PATH"
    run mv "${UNIT_PATH}.rollback-tmp" "${UNIT_PATH}.previous"
    run systemctl daemon-reload
  fi
  run systemctl reload-or-restart "$UNIT"   # у службы нет reload: это перезапуск
  ok "служба перезапущена на прежнем выпуске; sha256 кода:"
  run sha256sum "$INSTALLED_SCRIPT"
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

# Почему файл не читается — путь или сам файл. Прежняя проверка говорила
# «учётная запись не читает ключ», и владелец не мог отличить неверные права
# файла от непроходимого каталога выше. 2026-10-11 это стоило остановленной
# установки: файл был создан правильно, а непроходим был `/etc/site-factory`
# (`0700 root:root`). Теперь называется ИМЕННО та составляющая пути, на которой
# доступ кончается.
why_unreadable() {
  _file="$1"
  _dir="$(dirname -- "$_file")"
  _walk=""
  _oldifs="$IFS"
  IFS="/"
  for _part in $_dir; do
    [ -n "$_part" ] || continue
    _walk="${_walk}/${_part}"
    if ! as_run_user "test -x '${_walk}'"; then
      IFS="$_oldifs"
      printf 'каталог %s непроходим для %s (права %s, владелец %s)' \
        "$_walk" "$RUN_USER" \
        "$(stat -c '%a' "$_walk" 2>/dev/null || echo '?')" \
        "$(stat -c '%U:%G' "$_walk" 2>/dev/null || echo '?')"
      return 0
    fi
  done
  IFS="$_oldifs"
  if ! as_run_user "test -r '${_file}'"; then
    printf 'путь проходим, но сам файл не читается (права %s, владелец %s)' \
      "$(stat -c '%a' "$_file" 2>/dev/null || echo '?')" \
      "$(stat -c '%U:%G' "$_file" 2>/dev/null || echo '?')"
    return 0
  fi
  printf 'файл читается'
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
# «поставил, но не работает» было бы худшим исходом установки.
#
# ЗНАЧЕНИЕ НЕ ПЕЧАТАЕТСЯ. Напечатанный один раз ключ 2026-10-11 попал в
# переписку и тем самым стал раскрытым. Передача — через файл: владелец читает
# его `sudo cat` ровно в тот момент, когда вносит значение в секрет CI
# приложения, и значение не остаётся ни в выводе установки, ни в истории
# оболочки, ни в отчётах.
log "ключ клиента"
run install -d -m 0710 -o root -g "$RUN_USER" "$KEY_DIR"
ok "каталог ключа: $KEY_DIR (0710 root:${RUN_USER} — проход только нужной записи)"

ROTATED=0
if [ -s "$KEY_FILE" ] && [ "$rotate_key" != 1 ]; then
  ok "ключ уже существует: не перезаписываю"
else
  if [ "$dry_run" = 1 ]; then
    printf '   [сухой прогон] создать %s (0640 root:%s) со случайным значением\n' \
      "$KEY_FILE" "$RUN_USER"
    if [ -s "$KEY_FILE" ]; then
      printf '   [сухой прогон] прежнее значение заменяется; копия НЕ сохраняется\n'
    fi
  else
    # Прежнее значение НЕ сохраняется копией. Копия раскрытого ключа на диске —
    # это тот же раскрытый ключ, только дольше живущий; а для возврата доступа
    # достаточно нового значения из файла.
    if [ -s "$KEY_FILE" ]; then ROTATED=1; fi
    umask 027
    "${PYTHON:-/usr/bin/python3}" -c \
      "import secrets,sys; sys.stdout.write(secrets.token_urlsafe(32))" > "$KEY_FILE"
    chown "root:${RUN_USER}" "$KEY_FILE"
    chmod 0640 "$KEY_FILE"
    ok "ключ записан: $KEY_FILE (0640 root:${RUN_USER}); значение не печатается"
    # В журнал поворотов идёт только ОТМЕТКА, без значения.
    printf '%s key-%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      "$([ "$ROTATED" = 1 ] && echo rotated || echo created)" >> "$ROTATION_LOG"
    chown "root:${RUN_USER}" "$ROTATION_LOG"
    chmod 0640 "$ROTATION_LOG"
  fi
fi

# Раскрытый ключ прежнего размещения: служба его больше не читает, но файл
# остаётся на диске. Удаление под `/etc` — решение владельца, поэтому сценарий
# только называет команду.
if [ -e "$LEAKED_KEY_FILE" ]; then
  log "[!] прежний файл ключа ещё на диске: $LEAKED_KEY_FILE"
  printf '   Служба его НЕ читает. Он был напечатан установкой и попал в\n'
  printf '   переписку, то есть раскрыт. Удалить (решение владельца):\n'
  printf '       sudo rm -f %s\n' "$LEAKED_KEY_FILE"
elif [ "$(id -u)" != "0" ]; then
  # Путь к прежнему файлу непроходим для не-root, поэтому его отсутствие здесь
  # ничего не доказывает: сказать об этом честнее, чем промолчать.
  printf '   (наличие прежнего файла %s проверяется только от root)\n' \
    "$LEAKED_KEY_FILE"
fi
if [ "$dry_run" = 0 ]; then
  as_run_user "test -r '${KEY_FILE}'" \
    || die "учётная запись ${RUN_USER} не читает ключ ${KEY_FILE}: $(why_unreadable "$KEY_FILE")"
  ok "ключ читается учётной записью ${RUN_USER}"
fi

# --- код службы в стабильное место ------------------------------------------
log "код службы ${INSTALLED_SCRIPT}"
# Смена кода без перезапуска — это выложенный файл при работающем прежнем
# процессе. Поймано 2026-10-11: исправление разбора пути скопировалось бы, а
# служба продолжала бы отвечать 404 на `%3A`, и выглядело бы это как
# «исправление не работает».
CODE_CHANGED=0
if [ ! -f "$INSTALLED_SCRIPT" ]; then
  CODE_CHANGED=1
elif ! cmp -s "$SERVICE_SCRIPT" "$INSTALLED_SCRIPT"; then
  CODE_CHANGED=1
fi
run install -d -m 0755 -o root -g root "$INSTALL_DIR"
if [ "$CODE_CHANGED" = 1 ] && [ -f "$INSTALLED_SCRIPT" ]; then
  # Прежний выпуск остаётся рядом: без него «откатить код» значило бы снять
  # службу целиком (--rollback), а это другой путь.
  run cp -p "$INSTALLED_SCRIPT" "${INSTALLED_SCRIPT}.previous"
  ok "прежний выпуск сохранён: ${INSTALLED_SCRIPT}.previous"
fi
run install -m 0644 -o root -g root "$SERVICE_SCRIPT" "$INSTALLED_SCRIPT"
if [ "$CODE_CHANGED" = 1 ]; then
  ok "код службы отличался от выложенного — потребуется перезапуск"
else
  ok "код службы тот же: перезапуск не нужен"
fi
# Контракт рядом с кодом: иначе Documentation юнита указывал бы в снятое дерево.
run install -m 0644 -o root -g root "${SRC_ROOT}/docs/APP_READ_API.md" \
    "${INSTALL_DIR}/app-read-api-${SITE_ID}.doc.md"
ok "код службы и контракт не зависят от рабочего дерева сессии"

# --- каталог ревизий главной приложения --------------------------------------
# Создаётся до юнита: ReadOnlyPaths с несуществующим путём не даёт службе
# стартовать. Владелец — учётная запись Control API, которая в него пишет.
log "каталог ревизий главной ${CONFIG_DIR}"
run install -d -m 0755 -o "$RUN_USER" -g "$RUN_USER" "$(dirname "$CONFIG_DIR")" "$CONFIG_DIR"
ok "каталог есть; содержимое не трогается"

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
    --data-dir ${DATA_DIR} --bind ${BIND} --port ${PORT} --key-file ${KEY_FILE} \\
    --config-dir ${CONFIG_DIR}
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
ReadOnlyPaths=${DATA_DIR} ${INSTALL_DIR} ${CONFIG_DIR}
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
  if [ -f "$UNIT_PATH" ] && ! cmp -s "$TMP_UNIT" "$UNIT_PATH"; then
    cp -p "$UNIT_PATH" "${UNIT_PATH}.previous"
    CODE_CHANGED=1
    ok "прежний юнит сохранён: ${UNIT_PATH}.previous"
  fi
  install -m 0644 -o root -g root "$TMP_UNIT" "$UNIT_PATH"
  ok "юнит записан: $UNIT_PATH"
fi
rm -f "$TMP_UNIT"
run systemctl daemon-reload
run systemctl enable --now "$UNIT"
# `enable --now` уже запущенную службу не перезапускает, а ключ читается при
# старте: без перезапуска поворот ключа ничего бы не изменил, и это выглядело
# бы успехом.
if [ "$CODE_CHANGED" = 1 ] && [ "$rotate_key" != 1 ] && [ "$ROTATED" != 1 ]; then
  run systemctl restart "$UNIT"
  ok "служба перезапущена: выложен новый код"
fi
if [ "$rotate_key" = 1 ] || [ "$ROTATED" = 1 ]; then
  run systemctl restart "$UNIT"
  ok "служба перезапущена: новый ключ прочитан"
  printf '   ВНИМАНИЕ: прежний ключ больше не принимается. Сборка приложения с\n'
  printf '   прежним ключом перестанет получать данные — внесите НОВОЕ значение\n'
  printf '   в секрет CI приложения и выпустите новую сборку. Значение читается\n'
  printf '   из файла ровно в этот момент и нигде не печатается:\n'
  printf '       sudo cat %s\n' "$KEY_FILE"
fi

if [ "$dry_run" = 0 ]; then
  # Спрашиваем СРАЗУ, потом ждём: измеренная готовность службы на полном
  # снимке — 1,0 с, а прежний порядок («сначала sleep 5») добавлял пять секунд
  # к каждой установке и к каждому повтору на пустом месте.
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
    if curl -fsS "http://${BIND}:${PORT}/healthz" >/dev/null 2>&1; then break; fi
    sleep 5
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
   1. ВСЯ приёмка одной командой (состояние, отказы, список, поиск, карточка,
      обложки, сезоны, серии, честное отсутствие прямого потока). Ключ она
      читает из файла и нигде не печатает; root не нужен — файл доступен
      учётной записи ${RUN_USER}:
        python3 ${SRC_ROOT}/automation/local/app-api-acceptance.py \\
            --base https://${DOMAIN} --key-file ${KEY_FILE}
      ожидается «расхождений: 0» и код выхода 0
   2. состояние вручную (ключ не нужен):
        curl -s https://${DOMAIN}/api/app/v1/healthz
      ожидается 200 и {"ready":true,…}. Если пришёл 308 на тот же путь со
      слешем, а за ним 404 — маршрута нет, то есть установка не состоялась:
      это перенаправление самой витрины, а не ответ службы
   3. без ключа:   curl -s -o /dev/null -w '%{http_code}\\n' https://${DOMAIN}/api/app/v1/titles/01915145-2c16-7ba4-8353-42b73d657fdc
                   ожидается 401
   4. страницы витрины обязаны отвечать как прежде:
                   curl -s -o /dev/null -w '%{http_code}\\n' https://${DOMAIN}/
                   ожидается 200
   Смена ключа клиента (он лежит в APK и секретом не является):
     sudo bash $0 --rotate-key
   Откат только этих изменений: sudo bash $0 --rollback
HINT
