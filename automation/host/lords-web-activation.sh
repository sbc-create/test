#!/usr/bin/env bash
# Одноразовая веб-активация живого каталога Lords.
#
# Открывает защищённую форму на https://lordfilm47.space/__lords-activate,
# принимает учётные данные из браузера, активирует живой каталог и убирает
# форму насовсем.
#
# Запускается через тонкий пускатель var/start-lords-web-activation.sh.
#
# Что НЕ делается:
#   * YummyAnime не трогается;
#   * Basic Auth основных сайтов не снимается — снимается только с временного
#     адреса, и вместо него там одноразовый код;
#   * сертификаты не выпускаются и не меняются: берётся существующий;
#   * индексация не включается, Метрика и Вебмастер не создаются;
#   * секреты не печатаются, не попадают в argv, окружение дочерних процессов,
#     журналы nginx и systemd.
#
# Форма живёт LORDS_INTAKE_TTL секунд (по умолчанию 15 минут) и исчезает раньше,
# если приём завершился.

set -Eeuo pipefail

readonly REPO=/srv/site-factory/repo/var/lords-deploy
readonly EXPECT_SHA="${LORDS_EXPECT_SHA:-}"
readonly APEX=lordfilm47.space
readonly LOCATION_PATH=/__lords-activate
readonly NGINX_DIR=/etc/nginx/lords
readonly ACTIVATION_DIR="${NGINX_DIR}/activation"
readonly SNIPPET="${ACTIVATION_DIR}/intake.conf"
readonly SECRET_DIR=/etc/site-factory/secrets/cdnvideohub/lords
readonly TOKEN_FILE="${SECRET_DIR}/api-token"
readonly PUBLISHER_FILE="${SECRET_DIR}/publisher-id"
readonly TTL="${LORDS_INTAKE_TTL:-900}"

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

WORKDIR=""
INTAKE_PID=""
TEARDOWN_DONE=""

teardown() {
  # Снятие формы обязано произойти ровно один раз и при любом исходе.
  [[ -n "${TEARDOWN_DONE}" ]] && return 0
  TEARDOWN_DONE=1

  if [[ -n "${INTAKE_PID}" ]] && kill -0 "${INTAKE_PID}" 2>/dev/null; then
    kill -TERM "${INTAKE_PID}" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "${INTAKE_PID}" 2>/dev/null || break
      sleep 0.5
    done
    kill -KILL "${INTAKE_PID}" 2>/dev/null || true
  fi

  if [[ -f "${SNIPPET}" ]]; then
    rm -f "${SNIPPET}"
    if nginx -t >/dev/null 2>&1; then
      systemctl reload nginx >/dev/null 2>&1 || true
      log "временный адрес снят, nginx перезагружен"
    else
      warn "после снятия адреса nginx -t не проходит; reload не выполнялся"
    fi
  fi

  # Код и сессии жили в памяти процесса; на диске остаются только служебные
  # файлы без секретов — их тоже убираем.
  [[ -n "${WORKDIR}" && -d "${WORKDIR}" ]] && rm -rf -- "${WORKDIR}"
  return 0
}
trap 'teardown' EXIT
trap 'warn "прервано на строке ${LINENO}"; teardown; exit 1' ERR

[[ ${EUID} -eq 0 ]] || die "нужен root: sudo bash $0"
[[ -n "${EXPECT_SHA}" ]] || die "не передан LORDS_EXPECT_SHA"
[[ -d "${REPO}" ]] || die "нет deployment worktree: ${REPO}"

HEAD_SHA="$(git -C "${REPO}" rev-parse HEAD 2>/dev/null || true)"
[[ "${HEAD_SHA}" == "${EXPECT_SHA}" ]] \
  || die "ожидался commit ${EXPECT_SHA}, в worktree ${HEAD_SHA:-неизвестно}"

PY="${REPO}/.venv/bin/python"
[[ -x "${PY}" ]] || PY="$(command -v python3)"
[[ -n "${PY}" ]] || die "python3 не найден"

# Сертификат уже существует: форма живёт на нём, ничего не выпускается.
[[ -s "/etc/letsencrypt/live/${APEX}/fullchain.pem" ]] \
  || die "нет сертификата ${APEX}; форма не поднимается без HTTPS"
[[ -d "${NGINX_DIR}" ]] || die "нет ${NGINX_DIR}: сначала должен работать fixture-стенд"

# --------------------------------------------------------------------------
# Уборка следов прошлого запуска
# --------------------------------------------------------------------------
# Прошлый запуск мог оборваться и оставить сниппет с портом уже мёртвого
# приёмника, а сам приёмник — висеть без конфигурации. Повторный запуск обязан
# начинаться с чистого состояния, а не поверх чужого.
if [[ -f "${SNIPPET}" ]]; then
  warn "найден сниппет прошлого запуска — убираю"
  rm -f "${SNIPPET}"
  if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx >/dev/null 2>&1 || true
  else
    die "nginx -t не проходит после уборки прошлого сниппета; разберитесь вручную"
  fi
fi
# Осиротевшие приёмники прошлых запусков. Имя модуля уникально, чужого не заденет.
if pgrep -f "factory.lords.web_intake_main" >/dev/null 2>&1; then
  warn "найден приёмный процесс прошлого запуска — останавливаю"
  pkill -TERM -f "factory.lords.web_intake_main" 2>/dev/null || true
  sleep 2
  pkill -KILL -f "factory.lords.web_intake_main" 2>/dev/null || true
fi
rm -rf -- /run/lords-activation.* 2>/dev/null || true

# --------------------------------------------------------------------------
# Код доступа и рабочий каталог
# --------------------------------------------------------------------------
WORKDIR="$(mktemp -d /run/lords-activation.XXXXXX)"
chmod 0700 "${WORKDIR}"
PORT_FILE="${WORKDIR}/port"
RESULT_FILE="${WORKDIR}/result.json"

# Код рождается здесь и печатается только в этой консоли. В argv дочернего
# процесса он попадёт, но это код доступа к форме, а не секрет владельца:
# он живёт минуты, одноразовый и без токена бесполезен.
ACCESS_CODE="$("${PY}" -c \
  'from factory.lords.web_intake import generate_code; print(generate_code())')"

PROBE_URL="$("${PY}" - "${REPO}" <<'PY'
import pathlib, sys, urllib.parse, yaml
raw = yaml.safe_load(
    (pathlib.Path(sys.argv[1]) / "knowledge/cdnvideohub/content-api.yaml")
    .read_text(encoding="utf-8")
)
base, path = raw["base_url"], raw["endpoints"]["titles"]["path"]
print(urllib.parse.urljoin(base, path) + f"?{raw['pagination']['size_param']}=1")
PY
)"

# --------------------------------------------------------------------------
# Приёмный процесс
# --------------------------------------------------------------------------
( cd "${REPO}" && "${PY}" -m factory.lords.web_intake_main \
    --code "${ACCESS_CODE}" \
    --ttl "${TTL}" \
    --token-file "${TOKEN_FILE}" \
    --publisher-file "${PUBLISHER_FILE}" \
    --probe-url "${PROBE_URL}" \
    --port-file "${PORT_FILE}" \
    --result-file "${RESULT_FILE}" \
    >"${WORKDIR}/intake.log" 2>&1 ) &
INTAKE_PID=$!

for _ in $(seq 1 40); do
  [[ -s "${PORT_FILE}" ]] && break
  kill -0 "${INTAKE_PID}" 2>/dev/null || die "приёмный процесс не запустился"
  sleep 0.25
done
[[ -s "${PORT_FILE}" ]] || die "приёмный процесс не сообщил порт"
INTAKE_PORT="$(cat "${PORT_FILE}")"

# --------------------------------------------------------------------------
# Временный адрес в nginx
# --------------------------------------------------------------------------
# Location внутри уже существующего серверного блока сайта.
#
# Отдельный server{} с тем же server_name на 443 не годится: nginx не считает
# это ошибкой, а молча оставляет первый блок — временный адрес просто не
# отвечал бы. Поэтому сайт содержит include пустого каталога, и сюда кладётся
# один файл только на время приёма.
install -d -m 0755 "${ACTIVATION_DIR}"

# Развёрнутая конфигурация сайта могла быть записана раньше, чем в шаблон
# добавили include. Тогда сниппет лежит в каталоге, который никто не читает,
# и адрес формы попадает в общий `location /` — то есть под Basic Auth.
# Именно так и вышло при первом запуске: файл был на месте, а include в
# /etc/nginx/lords/lords-01.conf отсутствовал.
#
# Поэтому наличие include проверяется, и при отсутствии конфигурация сайта
# переустанавливается из worktree — с сохранением прежней и откатом при отказе.
SITE_CONF="${NGINX_DIR}/lords-01.conf"
CONF_BACKUP=""
if ! grep -q "include ${ACTIVATION_DIR}/\*.conf;" "${SITE_CONF}" 2>/dev/null; then
  log "в развёрнутой конфигурации нет include временных адресов — обновляю её"
  ( cd "${REPO}" && "${PY}" -m factory lords-staging >/dev/null ) \
    || die "не удалось собрать конфигурацию сайта"
  GENERATED="${REPO}/artifacts/lords/staging/nginx/phase2/lords-01.conf"
  grep -q "include ${ACTIVATION_DIR}/\*.conf;" "${GENERATED}" \
    || die "в собранной конфигурации нет include: обновите deployment worktree"

  CONF_BACKUP="${WORKDIR}/lords-01.conf.before"
  cp -a "${SITE_CONF}" "${CONF_BACKUP}"
  install -m 0644 "${GENERATED}" "${SITE_CONF}"

  if ! nginx -t >/dev/null 2>&1; then
    install -m 0644 "${CONF_BACKUP}" "${SITE_CONF}"
    die "nginx -t не прошёл с обновлённой конфигурацией сайта; прежняя возвращена"
  fi
  log "конфигурация сайта обновлена, include подключён"
fi

cat > "${SNIPPET}" <<CONF
# Временный адрес одноразовой активации Lords. Удаляется сценарием.
#
# Basic Auth здесь намеренно нет: основной пароль в этот канал не передаётся.
# Вместо него одноразовый код, который проверяет приёмный процесс.
location = ${LOCATION_PATH} {
    # Точный location не наследует auth_basic из location /, но пароль мог бы
    # прийти с уровня server, если конфигурацию когда-нибудь перестроят.
    # Снимаем его явно и только здесь: на остальных адресах он остаётся.
    auth_basic off;

    access_log off;
    client_max_body_size 8k;
    client_body_buffer_size 8k;

    proxy_pass http://127.0.0.1:${INTAKE_PORT};
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_read_timeout 60s;
}
CONF
chmod 0644 "${SNIPPET}"

if ! nginx -t >/dev/null 2>&1; then
  rm -f "${SNIPPET}"
  [[ -n "${CONF_BACKUP}" ]] && install -m 0644 "${CONF_BACKUP}" "${SITE_CONF}"
  die "nginx -t не прошёл с временным адресом; ничего не изменено"
fi
systemctl reload nginx

# Убедиться, что форма действительно открыта без пароля, а сайт — нет.
# Проверяется поведение, а не конфигурация: именно здесь прошлый запуск и
# обманул сам себя, отрапортовав об установке адреса, которого не было.
FORM_CODE="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
  --resolve "${APEX}:443:127.0.0.1" "https://${APEX}${LOCATION_PATH}" 2>/dev/null)" \
  || FORM_CODE="curl-error"
MAIN_CODE="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
  --resolve "${APEX}:443:127.0.0.1" "https://${APEX}/" 2>/dev/null)" \
  || MAIN_CODE="curl-error"

if [[ "${FORM_CODE}" != "200" ]]; then
  die "форма отвечает ${FORM_CODE}, ожидался 200 без пароля. Временный адрес снят ловушкой."
fi
if [[ "${MAIN_CODE}" != "401" ]]; then
  die "главная отвечает ${MAIN_CODE}, ожидался 401: Basic Auth сайта нарушен"
fi
log "форма открыта без пароля (200), остальной сайт по-прежнему под паролем (401)"

# --------------------------------------------------------------------------
# То, что видит владелец
# --------------------------------------------------------------------------
echo
printf '  URL:   https://%s%s\n' "${APEX}" "${LOCATION_PATH}"
printf '  Код:   %s\n' "${ACCESS_CODE}"
printf '  Срок:  %s минут\n' "$((TTL / 60))"
printf '  Статус: ожидание ввода\n'
echo

# --------------------------------------------------------------------------
# Ожидание
# --------------------------------------------------------------------------
wait "${INTAKE_PID}" && INTAKE_RC=0 || INTAKE_RC=$?
INTAKE_PID=""

ACCEPTED="$("${PY}" - "${RESULT_FILE}" <<'PY'
import json, pathlib, sys
try:
    print("yes" if json.loads(pathlib.Path(sys.argv[1]).read_text())["accepted"] else "no")
except Exception:
    print("no")
PY
)"

if [[ "${ACCEPTED}" != "yes" ]]; then
  teardown
  die "учётные данные не приняты (код возврата ${INTAKE_RC}); ничего не изменено"
fi

log "учётные данные приняты и сохранены в ${SECRET_DIR} (0600, значения не печатались)"

# Форма больше не нужна: снимаем её до переключения, чтобы адрес не жил дольше
# необходимого, даже если активация окажется долгой. teardown идемпотентен,
# поэтому повторный вызов из ловушки EXIT ничего не сделает.
teardown

# --------------------------------------------------------------------------
# Активация
# --------------------------------------------------------------------------
log "переключаю каталог на живой источник"
if LORDS_NONINTERACTIVE=1 \
   LORDS_RIGHTS_CONFIRMED=yes \
   LORDS_KEEP_SECRETS_ON_ROLLBACK=1 \
   LORDS_EXPECT_SHA="${EXPECT_SHA}" \
   bash "${REPO}/automation/host/activate-lords-live.sh"; then
  log "живой каталог активирован"
else
  die "активация не прошла: стенд возвращён на fixture-релиз.
Сохранённые учётные данные не удалены и не печатались — повторный запуск
активатора не потребует их ввода заново."
fi
