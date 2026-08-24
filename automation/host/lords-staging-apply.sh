#!/usr/bin/env bash
# Публикация fixture-staging направления Lords на управляющем сервере.
#
# Сценарий идемпотентен: повторный запуск не создаёт второй сайт, второй
# сертификат, второго пользователя и второй юнит. Каждый шаг сначала смотрит на
# фактическое состояние и только потом решает, нужно ли что-то делать.
#
# Что он НЕ делает — и это так же важно, как то, что он делает:
#   * не трогает конфигурацию, контейнеры, базы и бэкапы YummyAnime;
#   * не занимает портов вне 9101-9103;
#   * не включает индексацию, не создаёт Метрику и не добавляет хосты в Вебмастер;
#   * не выкатывает production: пакеты объявлены staging и не авторизованы;
#   * не печатает значения секретов — только пути к ним.
#
# Запуск:
#   sudo bash automation/host/lords-staging-apply.sh
#
# Переменные окружения (все необязательны):
#   LORDS_ACME_EMAIL   адрес для уведомлений Let's Encrypt о продлении.
#                      По умолчанию — LORDS_ACME_EMAIL_DEFAULT ниже.
#   LORDS_EXPECT_SHA   commit, который обязан быть выложен. Не совпал — отказ до
#                      единой мутации. Пустая строка отключает проверку.
#   LORDS_SKIP_CERTS=1 остановиться после фазы 1 (сертификаты не выпускать).
#
# Откат: всё, что сценарий меняет в nginx и systemd, сохраняется до первой
# мутации и возвращается на место при любой ошибке — включая провал публичной
# приёмки в конце. Каталоги релизов при этом не удаляются: прежний релиз обязан
# пережить откат, иначе откатываться будет не на что.

set -Eeuo pipefail

readonly NGINX_DIR=/etc/nginx/lords
readonly NGINX_INCLUDE=/etc/nginx/conf.d/lords.conf
readonly RUNTIME_ROOT=/srv/lords
readonly ACME_ROOT=/var/www/lords-acme
readonly HTPASSWD="${NGINX_DIR}/.htpasswd"
readonly CREDENTIALS=/root/lords-staging-credentials
readonly DEFAULT_CERT="${NGINX_DIR}/default-self-signed"
readonly SERVICE_USER=lords
readonly PORTS=(9101 9102 9103)
readonly UNITS=(lords-01.service lords-02.service lords-03.service)
readonly BACKUP_ROOT=/var/backups/lords-staging
readonly LORDS_ACME_EMAIL_DEFAULT=sb@adcamp.ru

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Пока ничего не изменено, откатывать нечего: до снимка ERR только сообщает.
ROLLBACK_READY=0
BACKUP_DIR=""

rollback() {
  [[ "${ROLLBACK_READY}" -eq 1 ]] || return 0
  ROLLBACK_READY=0  # откат не откатывают повторно

  warn "откат: возвращаю nginx и systemd в состояние до запуска"

  for unit in "${UNITS[@]}"; do
    systemctl stop "${unit}" >/dev/null 2>&1 || true
    if [[ -f "${BACKUP_DIR}/systemd/${unit}" ]]; then
      install -m 0644 "${BACKUP_DIR}/systemd/${unit}" "/etc/systemd/system/${unit}"
    else
      rm -f "/etc/systemd/system/${unit}"
      systemctl disable "${unit}" >/dev/null 2>&1 || true
    fi
  done
  systemctl daemon-reload >/dev/null 2>&1 || true

  # Конфигурация Lords: возвращаем ровно то, что лежало до запуска.
  # Проверка перед rm -rf намеренная: пустая переменная превратила бы уборку
  # каталога Lords в уборку корня.
  [[ -n "${NGINX_DIR}" && "${NGINX_DIR}" == /etc/nginx/* ]] \
    || die "NGINX_DIR испорчен: ${NGINX_DIR}"
  rm -rf -- "${NGINX_DIR}"
  if [[ -d "${BACKUP_DIR}/nginx-lords" ]]; then
    cp -a "${BACKUP_DIR}/nginx-lords" "${NGINX_DIR}"
  fi
  if [[ -f "${BACKUP_DIR}/lords-include.conf" ]]; then
    install -m 0644 "${BACKUP_DIR}/lords-include.conf" "${NGINX_INCLUDE}"
  else
    rm -f "${NGINX_INCLUDE}"
  fi

  # Соседей не трогаем: если после отката конфигурация неверна, причина не в
  # Lords, и молча перезагружать nginx в таком виде нельзя.
  if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx >/dev/null 2>&1 || true
    warn "откат выполнен, nginx перезагружен с прежней конфигурацией"
  else
    warn "ВНИМАНИЕ: после отката nginx -t не проходит. Reload НЕ выполнялся."
    warn "Конфигурация Lords снята; разбирайте вручную: nginx -t"
  fi

  # Юниты, которые работали до запуска, поднимаем обратно.
  if [[ -f "${BACKUP_DIR}/active-units" ]]; then
    while read -r unit; do
      [[ -n "${unit}" ]] || continue
      systemctl start "${unit}" >/dev/null 2>&1 || \
        warn "не удалось поднять обратно ${unit}"
    done < "${BACKUP_DIR}/active-units"
  fi

  warn "снимок сохранён: ${BACKUP_DIR}"
}

on_error() {
  local line="$1"
  printf '\033[31m[x]\033[0m прервано на строке %s\n' "${line}" >&2
  rollback
  exit 1
}

trap 'on_error "${LINENO}"' ERR

[[ ${EUID} -eq 0 ]] || die "нужен root: sudo bash $0"

# --------------------------------------------------------------------------
# 0. Где мы и чем собирать
# --------------------------------------------------------------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
[[ -f "${REPO_ROOT}/config/directions/lords.json" ]] \
  || die "не похоже на репозиторий фабрики: ${REPO_ROOT}"

if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PY="${REPO_ROOT}/.venv/bin/python"
else
  PY="$(command -v python3 || true)"
fi
[[ -n "${PY}" ]] || die "python3 не найден"
command -v nginx >/dev/null || die "nginx не установлен"

log "репозиторий: ${REPO_ROOT}"
log "интерпретатор: ${PY}"
log "nginx: $(nginx -v 2>&1)"

# --------------------------------------------------------------------------
# 0a. Тот ли это commit
# --------------------------------------------------------------------------
# Выкатывать «то, что сейчас в рабочем каталоге» — значит выкатывать чужую
# незакоммиченную правку вместе с релизом. Поэтому SHA сверяется явно, а
# грязное дерево останавливает сценарий до первой мутации.
HEAD_SHA="$(git -C "${REPO_ROOT}" rev-parse HEAD 2>/dev/null || true)"
[[ -n "${HEAD_SHA}" ]] || die "не удалось прочитать commit: ${REPO_ROOT} не git-репозиторий"
log "commit: ${HEAD_SHA}"

EXPECT_SHA="${LORDS_EXPECT_SHA-unset}"
if [[ "${EXPECT_SHA}" == "unset" ]]; then
  warn "LORDS_EXPECT_SHA не задан: выкладывается текущий HEAD без сверки."
elif [[ -n "${EXPECT_SHA}" ]]; then
  if [[ "${HEAD_SHA}" != "${EXPECT_SHA}"* ]]; then
    die "ожидался commit ${EXPECT_SHA}, в рабочем каталоге ${HEAD_SHA}; ничего не изменено"
  fi
  log "commit совпал с ожидаемым"
fi

if [[ -n "$(git -C "${REPO_ROOT}" status --porcelain --untracked-files=no 2>/dev/null)" ]]; then
  die "рабочее дерево грязное: выкладывался бы не тот код, что в commit ${HEAD_SHA}"
fi

# --------------------------------------------------------------------------
# 1. Сборка конфигурации и пакетов. Ничего ещё не применяется.
# --------------------------------------------------------------------------
log "собираю конфигурацию и пакеты стенда"
( cd "${REPO_ROOT}" && "${PY}" -m factory lords-staging ) \
  || die "сборка стенда не прошла — на сервере ничего не изменено"

STAGING_DIR="${REPO_ROOT}/artifacts/lords/staging"
BUNDLE_DIR="${REPO_ROOT}/artifacts/lords/bundle"
[[ -f "${STAGING_DIR}/staging.json" ]] || die "нет ${STAGING_DIR}/staging.json"

mapfile -t SITES < <("${PY}" -c '
import json, sys
data = json.load(open(sys.argv[1]))
for s in data["sites"]:
    print(f"{s[\"site_id\"]}\t{s[\"apex\"]}\t{s[\"www\"]}\t{s[\"port\"]}\t{s[\"unit\"]}\t{s[\"runtime_root\"]}")
' "${STAGING_DIR}/staging.json")
[[ ${#SITES[@]} -eq 3 ]] || die "ожидалось три сайта, получено ${#SITES[@]}"

# --------------------------------------------------------------------------
# 2. Чужое не трогаем: порты и сервер по умолчанию
# --------------------------------------------------------------------------
log "проверяю, что не мешаю соседям"

# PID главного процесса юнита; пусто, если юнит не запущен.
unit_main_pid() {
  local pid; pid="$(systemctl show -p MainPID --value "$1" 2>/dev/null || echo 0)"
  [[ "${pid}" =~ ^[0-9]+$ && "${pid}" -gt 0 ]] && printf '%s' "${pid}"
}

# Порт свободен — или принадлежит именно нашему юниту. Прежняя проверка
# пропускала любой процесс с именем python3: под это описание попадает
# посторонний сервис, который сценарий затем молча перетёр бы своим.
for index in "${!PORTS[@]}"; do
  port="${PORTS[${index}]}"
  unit="${UNITS[${index}]}"
  holder="$(ss -ltnpH "sport = :${port}" 2>/dev/null | head -1)"
  [[ -n "${holder}" ]] || { log "  порт ${port} свободен"; continue; }

  holder_pid="$(grep -oE 'pid=[0-9]+' <<<"${holder}" | head -1 | cut -d= -f2)"
  expected_pid="$(unit_main_pid "${unit}")"

  if [[ -n "${expected_pid}" && "${holder_pid}" == "${expected_pid}" ]]; then
    log "  порт ${port} держит ${unit} — это повторный запуск"
    continue
  fi

  # Юнит мог перезапуститься между вызовами: сверяем по cgroup, а не только PID.
  if [[ -n "${holder_pid}" ]] \
     && grep -qs "${unit}" "/proc/${holder_pid}/cgroup" 2>/dev/null; then
    log "  порт ${port} держит ${unit} (по cgroup) — это повторный запуск"
    continue
  fi

  die "порт ${port} занят посторонним процессом: ${holder}"
done

INSTALL_DEFAULT=1
if grep -rlsE '^\s*listen[^;]*default_server' /etc/nginx --include='*.conf' 2>/dev/null \
     | grep -v "^${NGINX_DIR}/" | grep -q .; then
  INSTALL_DEFAULT=0
  warn "в /etc/nginx уже объявлен default_server вне ${NGINX_DIR}."
  warn "Свой сервер по умолчанию не ставлю: два default_server на одном порту —"
  warn "это отказ nginx -t. Ответ 421 на неизвестный Host остаётся за существующей"
  warn "конфигурацией; проверьте её отдельно."
fi

# --------------------------------------------------------------------------
# 2a. Снимок состояния. Дальше начинаются мутации.
# --------------------------------------------------------------------------
# Снимок делается до первой правки и только после того, как все отказные
# проверки выше пройдены: откатывать имеет смысл лишь то, что успели изменить.
BACKUP_DIR="${BACKUP_ROOT}/$(date +%Y%m%d-%H%M%S)-${HEAD_SHA:0:12}"
install -d -m 0700 "${BACKUP_ROOT}" "${BACKUP_DIR}"

# Полная копия /etc/nginx — на случай, если разбирать придётся руками.
tar -czf "${BACKUP_DIR}/etc-nginx.tar.gz" -C /etc nginx 2>/dev/null \
  || warn "полный бэкап /etc/nginx не собрался; точечный снимок ниже всё равно сделан"

# Точечный снимок того, что сценарий действительно меняет.
[[ -d "${NGINX_DIR}" ]] && cp -a "${NGINX_DIR}" "${BACKUP_DIR}/nginx-lords"
[[ -f "${NGINX_INCLUDE}" ]] && cp -a "${NGINX_INCLUDE}" "${BACKUP_DIR}/lords-include.conf"

install -d -m 0700 "${BACKUP_DIR}/systemd"
: > "${BACKUP_DIR}/active-units"
for unit in "${UNITS[@]}"; do
  [[ -f "/etc/systemd/system/${unit}" ]] \
    && cp -a "/etc/systemd/system/${unit}" "${BACKUP_DIR}/systemd/${unit}"
  systemctl is-active --quiet "${unit}" 2>/dev/null \
    && printf '%s\n' "${unit}" >> "${BACKUP_DIR}/active-units"
done

ROLLBACK_READY=1
log "снимок для отката: ${BACKUP_DIR}"

# --------------------------------------------------------------------------
# 3. Пользователь, каталоги, права
# --------------------------------------------------------------------------
if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  log "создаю системного пользователя ${SERVICE_USER}"
  useradd --system --home-dir "${RUNTIME_ROOT}" --shell /usr/sbin/nologin "${SERVICE_USER}"
else
  log "пользователь ${SERVICE_USER} уже есть"
fi

install -d -m 0755 "${NGINX_DIR}" "${RUNTIME_ROOT}" "${ACME_ROOT}"
install -d -m 0755 -o "${SERVICE_USER}" -g "${SERVICE_USER}" "${RUNTIME_ROOT}"

# --------------------------------------------------------------------------
# 4. Basic Auth. Пароль рождается здесь и в вывод не попадает.
# --------------------------------------------------------------------------
# Формат хеша — bcrypt, и запасного пути в слабый формат нет. APR1-MD5, который
# htpasswd ставит по умолчанию, — это MD5 с 1000 итераций: для пароля, лежащего
# на публичном хосте, запас прочности неприемлемый. Поэтому при отсутствии
# htpasswd сценарий доставляет apache2-utils, а не переходит на APR1 молча.
if ! command -v htpasswd >/dev/null; then
  log "htpasswd не найден — ставлю apache2-utils"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq >/dev/null 2>&1 \
    || warn "apt-get update не прошёл; пробую установку с имеющимися списками"
  apt-get install -y -qq apache2-utils >/dev/null 2>&1 \
    || die "не удалось поставить apache2-utils; bcrypt недоступен, слабый формат не используется"
fi
command -v htpasswd >/dev/null \
  || die "htpasswd отсутствует после установки apache2-utils"

if [[ -s "${HTPASSWD}" ]]; then
  # Повторный запуск не меняет пароль. Но если файл остался от прежней версии
  # сценария в формате APR1, он переписывается: bcrypt-строка начинается с $2y$.
  if grep -q '^lords:\$2[aby]\$' "${HTPASSWD}"; then
    log "файл Basic Auth уже есть, формат bcrypt — пароль не меняю"
    REGENERATE_AUTH=0
  else
    warn "файл Basic Auth не в формате bcrypt — перевыпускаю пароль"
    REGENERATE_AUTH=1
  fi
else
  REGENERATE_AUTH=1
fi

if [[ "${REGENERATE_AUTH}" -eq 1 ]]; then
  log "создаю пароль Basic Auth (bcrypt, cost 12)"
  # 32 символа из ~62-символьного алфавита: около 190 бит энтропии.
  password="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)"
  [[ ${#password} -eq 32 ]] || die "не удалось получить пароль нужной длины"

  # Пароль передаётся htpasswd аргументом только в пределах этого процесса;
  # -C 12 задаёт стоимость bcrypt.
  htpasswd -bcB -C 12 "${HTPASSWD}" lords "${password}" >/dev/null 2>&1 \
    || die "htpasswd не создал bcrypt-хеш"
  grep -q '^lords:\$2[aby]\$' "${HTPASSWD}" \
    || die "htpasswd записал не bcrypt; слабый формат не принимается"

  umask 077
  { printf 'Lords staging — Basic Auth\n'
    printf 'создано: %s\n' "$(date -Is)"
    printf 'формат: bcrypt (htpasswd -B, cost 12)\n'
    printf 'логин: lords\n'
    printf 'пароль: %s\n' "${password}"
  } > "${CREDENTIALS}"
  chmod 0600 "${CREDENTIALS}"
  log "пароль записан в ${CREDENTIALS} (права 0600). В этот вывод он не попал."
fi
chown root:www-data "${HTPASSWD}" 2>/dev/null || chown root:root "${HTPASSWD}"
chmod 0640 "${HTPASSWD}"

# --------------------------------------------------------------------------
# 5. Раскладка релизов. Переключение симлинка — атомарное.
# --------------------------------------------------------------------------
for row in "${SITES[@]}"; do
  IFS=$'\t' read -r site_id apex www port unit runtime <<<"${row}"
  archive="${BUNDLE_DIR}/${site_id}.tar"
  [[ -f "${archive}" ]] || die "нет пакета ${archive}"
  release="$(sha256sum "${archive}" | cut -c1-12)"
  target="${runtime}/releases/${release}"

  install -d -m 0755 -o "${SERVICE_USER}" -g "${SERVICE_USER}" \
    "${runtime}" "${runtime}/releases" "${runtime}/data"

  if [[ -d "${target}" ]]; then
    log "${site_id}: релиз ${release} уже разложен"
  else
    log "${site_id}: раскладываю релиз ${release}"
    install -d -m 0755 "${target}.tmp"
    tar -xf "${archive}" -C "${target}.tmp"
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${target}.tmp"
    mv "${target}.tmp" "${target}"
  fi

  # Симлинк переставляется через временное имя: в каталоге нет момента,
  # когда current отсутствует.
  ln -sfn "${target}" "${runtime}/.current.new"
  mv -Tf "${runtime}/.current.new" "${runtime}/current"
  chown -h "${SERVICE_USER}:${SERVICE_USER}" "${runtime}/current"

  # Предыдущие релизы: держим три последних, остальное удаляем.
  # Удаляется только то, что лежит под нашим же releases/ и не является текущим.
  mapfile -t old < <(ls -1dt "${runtime}/releases/"*/ 2>/dev/null | tail -n +4)
  for stale in "${old[@]:-}"; do
    [[ -n "${stale}" && "${stale}" != "${target}/" ]] || continue
    log "${site_id}: убираю старый релиз $(basename "${stale}")"
    rm -rf -- "${stale}"
  done

  install -m 0644 "${STAGING_DIR}/systemd/${unit}" "/etc/systemd/system/${unit}"
done

systemctl daemon-reload

# --------------------------------------------------------------------------
# 6. Фаза 1: только HTTP, чтобы выпустить сертификаты
# --------------------------------------------------------------------------
install_phase() {
  local phase="$1"
  log "устанавливаю конфигурацию nginx (${phase})"
  rm -f "${NGINX_DIR}"/*.conf
  for conf in "${STAGING_DIR}/nginx/${phase}"/*.conf; do
    local name; name="$(basename "${conf}")"
    if [[ "${name}" == "00-default.conf" && "${INSTALL_DEFAULT}" -eq 0 ]]; then
      continue
    fi
    install -m 0644 "${conf}" "${NGINX_DIR}/${name}"
  done

  if ! grep -qrs "include ${NGINX_DIR}/\*.conf;" /etc/nginx/nginx.conf; then
    if [[ -d /etc/nginx/conf.d ]]; then
      printf 'include %s/*.conf;\n' "${NGINX_DIR}" > /etc/nginx/conf.d/lords.conf
      log "подключил ${NGINX_DIR} через /etc/nginx/conf.d/lords.conf"
    else
      die "не нашёл, куда подключить ${NGINX_DIR}: нет /etc/nginx/conf.d"
    fi
  fi

  # Настоящая проверка. Пока она не прошла, ничего не перезагружается.
  nginx -t || die "nginx -t не прошёл на фазе ${phase}; reload не выполнялся"
  systemctl reload nginx || systemctl start nginx
  log "nginx перезагружен (${phase})"
}

# Самоподписанный сертификат сервера по умолчанию: ssl_reject_handshake
# появился только в 1.19.4, а цель — 1.18.
if [[ "${INSTALL_DEFAULT}" -eq 1 && ! -s "${DEFAULT_CERT}.crt" ]]; then
  log "создаю самоподписанный сертификат для сервера по умолчанию"
  openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
    -keyout "${DEFAULT_CERT}.key" -out "${DEFAULT_CERT}.crt" \
    -subj "/CN=invalid.invalid" >/dev/null 2>&1
  chmod 0600 "${DEFAULT_CERT}.key"
fi

install_phase phase1

for row in "${SITES[@]}"; do
  IFS=$'\t' read -r site_id apex www port unit runtime <<<"${row}"
  log "${site_id}: запускаю ${unit}"
  systemctl enable --now "${unit}" >/dev/null 2>&1 || systemctl restart "${unit}"
done

log "жду готовности рантаймов"
for row in "${SITES[@]}"; do
  IFS=$'\t' read -r site_id apex www port unit runtime <<<"${row}"
  for attempt in $(seq 1 30); do
    if curl -fsS --max-time 3 "http://127.0.0.1:${port}/readyz" >/dev/null 2>&1; then
      log "  ${site_id} готов на 127.0.0.1:${port}"
      break
    fi
    [[ ${attempt} -eq 30 ]] && die "${site_id}: /readyz не ответил за 30 попыток"
    sleep 1
  done
done

if [[ "${LORDS_SKIP_CERTS:-0}" == "1" ]]; then
  warn "LORDS_SKIP_CERTS=1 — останавливаюсь после фазы 1. HTTPS не настроен."
  exit 0
fi

# --------------------------------------------------------------------------
# 7. Сертификаты Let's Encrypt
# --------------------------------------------------------------------------
command -v certbot >/dev/null || die "certbot не установлен"

ACME_EMAIL="${LORDS_ACME_EMAIL:-${LORDS_ACME_EMAIL_DEFAULT}}"
acme_account_args=()
if [[ -n "${ACME_EMAIL}" ]]; then
  acme_account_args=(--email "${ACME_EMAIL}")
  log "ACME-адрес для уведомлений о продлении: ${ACME_EMAIL}"
else
  acme_account_args=(--register-unsafely-without-email)
  warn "адрес ACME пуст: писем об истечении сертификата не будет."
fi

for row in "${SITES[@]}"; do
  IFS=$'\t' read -r site_id apex www port unit runtime <<<"${row}"
  if [[ -s "/etc/letsencrypt/live/${apex}/fullchain.pem" ]]; then
    log "${apex}: сертификат уже есть"
    continue
  fi
  log "${apex}: выпускаю сертификат на apex и www"
  certbot certonly --webroot -w "${ACME_ROOT}" \
    -d "${apex}" -d "${www}" \
    --non-interactive --agree-tos --keep-until-expiring \
    "${acme_account_args[@]}" \
    || die "certbot не смог выпустить сертификат для ${apex}; HTTPS не включён, фаза 1 работает"
done

# Продление с перезагрузкой nginx. Хук идемпотентен: файл просто перезаписывается.
install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/lords-nginx-reload.sh <<'HOOK'
#!/usr/bin/env bash
# Перезагрузка nginx после успешного продления сертификата Lords.
set -Eeuo pipefail
nginx -t
systemctl reload nginx
HOOK
chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/lords-nginx-reload.sh

systemctl enable --now certbot.timer >/dev/null 2>&1 \
  || warn "certbot.timer не включился: проверьте, чем настроено автопродление"
certbot renew --dry-run >/dev/null 2>&1 \
  && log "пробное продление прошло" \
  || warn "пробное продление не прошло — проверьте certbot renew --dry-run вручную"

# --------------------------------------------------------------------------
# 8. Фаза 2: HTTPS
# --------------------------------------------------------------------------
install_phase phase2

# --------------------------------------------------------------------------
# 9. Проверка того, что получилось
# --------------------------------------------------------------------------
log "публичная приёмка"
failures=0

# Пароль читается из файла, а не из переменной: на повторном запуске пароль не
# перевыпускался, и в памяти его нет. В вывод он не попадает ни здесь, ни ниже.
AUTH_PASSWORD=""
if [[ -r "${CREDENTIALS}" ]]; then
  AUTH_PASSWORD="$(sed -n 's/^пароль: //p' "${CREDENTIALS}" | head -1)"
fi

for row in "${SITES[@]}"; do
  IFS=$'\t' read -r site_id apex www port unit runtime <<<"${row}"

  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "https://${apex}/" || echo 000)"
  [[ "${code}" == "401" ]] \
    && log "  ${apex}: 401 без пароля — Basic Auth работает" \
    || { warn "  ${apex}: ожидался 401, получен ${code}"; failures=$((failures + 1)); }

  # С паролем сайт обязан открыться: 401 на всё подряд — это тоже отказ стенда.
  if [[ -n "${AUTH_PASSWORD}" ]]; then
    authed="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
      -u "lords:${AUTH_PASSWORD}" "https://${apex}/" || echo 000)"
    [[ "${authed}" == "200" ]] \
      && log "  ${apex}: 200 с паролем — стенд открывается" \
      || { warn "  ${apex}: с паролем ожидался 200, получен ${authed}"; failures=$((failures + 1)); }

    # Индексация закрыта на публичном ответе, а не только в конфигурации.
    headers="$(curl -sS -D - -o /dev/null --max-time 15 \
      -u "lords:${AUTH_PASSWORD}" "https://${apex}/" || true)"
    grep -qi '^x-robots-tag:.*noindex' <<<"${headers}" \
      && log "  ${apex}: X-Robots-Tag noindex на публичном ответе" \
      || { warn "  ${apex}: нет X-Robots-Tag noindex"; failures=$((failures + 1)); }

    robots_body="$(curl -sS --max-time 15 -u "lords:${AUTH_PASSWORD}" \
      "https://${apex}/robots.txt" || true)"
    grep -q 'Disallow: /' <<<"${robots_body}" \
      && log "  ${apex}: robots.txt закрывает сайт целиком" \
      || { warn "  ${apex}: robots.txt не содержит Disallow: /"; failures=$((failures + 1)); }
  else
    warn "  ${apex}: пароль недоступен, проверки под аутентификацией пропущены"
    failures=$((failures + 1))
  fi

  redirect="$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 15 \
    "https://${www}/" || echo '000 -')"
  grep -q '^308 ' <<<"${redirect}" \
    && log "  ${www}: ${redirect}" \
    || { warn "  ${www}: ожидался 308, получено ${redirect}"; failures=$((failures + 1)); }

  robots="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 \
    "http://127.0.0.1:${port}/robots.txt" || echo 000)"
  [[ "${robots}" == "200" ]] \
    && log "  ${site_id}: robots.txt отдаётся рантаймом" \
    || { warn "  ${site_id}: robots.txt вернул ${robots}"; failures=$((failures + 1)); }

  # Рантайм обязан держать параллель: однопоточный сервер здесь и вставал.
  parallel_codes="$(for _ in 1 2 3 4 5 6 7 8; do
      curl -sS -o /dev/null -w '%{http_code}\n' --max-time 10 \
        "http://127.0.0.1:${port}/" &
    done; wait)"
  if grep -qv '^200$' <<<"${parallel_codes}"; then
    warn "  ${site_id}: параллельные запросы вернули $(tr '\n' ' ' <<<"${parallel_codes}")"
    failures=$((failures + 1))
  else
    log "  ${site_id}: восемь параллельных запросов — все 200"
  fi
done

# Неизвестный Host. Свой сервер по умолчанию сценарий ставит, только если чужого
# нет; если чужой есть — проверяется он, а не предположение о нём.
unknown="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 \
  -H 'Host: no-such-host.invalid' http://127.0.0.1/ || echo 000)"
if [[ "${INSTALL_DEFAULT}" -eq 1 ]]; then
  [[ "${unknown}" == "421" ]] \
    && log "  неизвестный Host: 421 (сервер по умолчанию Lords)" \
    || { warn "  неизвестный Host вернул ${unknown}, ожидался 421"; failures=$((failures + 1)); }
else
  # Существующий default-deny соседа: он обязан отказать, но код у него свой.
  # Требовать от чужой конфигурации ровно 421 нельзя — она написана не нами.
  # Недопустимо одно: чтобы неизвестное имя открыло сайт Lords.
  if [[ "${unknown}" =~ ^(421|404|403|444|000)$ ]]; then
    log "  неизвестный Host: ${unknown} — существующий default-deny соседа отказывает"
  else
    warn "  неизвестный Host вернул ${unknown}: чужой default_server не отказывает"
    failures=$((failures + 1))
  fi

  # И главное: неизвестное имя не должно отдавать контент Lords.
  leaked="$(curl -sS --max-time 10 -H 'Host: no-such-host.invalid' \
    http://127.0.0.1/ 2>/dev/null | head -c 2000 || true)"
  if grep -qiE 'lords|lordfilm|lordserial' <<<"${leaked}"; then
    warn "  неизвестный Host отдаёт содержимое Lords — сайт развешен по чужим именам"
    failures=$((failures + 1))
  else
    log "  неизвестный Host не отдаёт содержимое Lords"
  fi
fi

AUTH_PASSWORD=""  # в отчёт и журнал пароль не попадает

# Приёмка — такой же повод для отката, как и падение на любом шаге выше.
# Стенд, который применился, но отвечает не тем, оставлять работающим нельзя.
if [[ "${failures}" -gt 0 ]]; then
  warn "публичная приёмка не прошла: отказов ${failures}"
  rollback
  die "стенд откачен в состояние до запуска; ничего не опубликовано"
fi

ROLLBACK_READY=0  # дальше только вывод: откатывать успешный выкат не нужно

echo
log "готово"
"${PY}" -c '
import json, sys
data = json.load(open(sys.argv[1]))
for s in data["sites"]:
    print(f"  {s[\"url\"]:38} {s[\"site_id\"]}  {s[\"profile\"]:14} :{s[\"port\"]}")
' "${STAGING_DIR}/staging.json"
echo
log "commit: ${HEAD_SHA}"
log "снимок для отката: ${BACKUP_DIR}"
log "учётные данные Basic Auth: ${CREDENTIALS} (bcrypt, значение в вывод не печатается)"
log "индексация выключена, X-Robots-Tag: noindex, nofollow, robots.txt: Disallow: /"
log "Метрика не создавалась, хосты в Вебмастер не добавлялись, боевой выкат не авторизован"
