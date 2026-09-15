#!/usr/bin/env bash
# Применение доменной политики индексации витрины Yummy.
#
# Выкладывает automation/host/yummy-frontend.py на управляющий сервер и
# перезапускает ОДИН юнит — nova-yummy-site.service. После этого yummyani.site
# перестаёт получать глобальный `X-Robots-Tag: noindex, nofollow`, а
# `/robots.txt` уходит приложению.
#
# Сценарий идемпотентен: если выложенный файл уже совпадает с репозиторием, он
# ничего не выкладывает и не перезапускает юнит — только проводит приёмку.
#
# Что он НЕ делает — и это так же важно, как то, что он делает:
#   * не трогает nova-yummy-org и nova-yummy-biz: их политику задание прямо
#     запретило пересматривать, и приёмка ниже проверяет, что они не изменились;
#   * не трогает Lords, Zona и Animedia — ни файлов, ни юнитов;
#   * не меняет nginx, DNS и сертификаты;
#   * не включает Метрику, плееры и рейтинги;
#   * не применяет вторую половину правки — `SEO_INDEXING_ENABLED` живёт в
#     compose репозитория sbc-create/yummyani и выкладывается пересозданием
#     контейнера web-site. Без неё приложение продолжит отдавать `noindex` и
#     пустой sitemap: см. «ПАРНАЯ ПРАВКА» ниже.
#
# Запуск:
#   sudo bash automation/host/yummy-indexing-apply.sh
#
# Переменные окружения (все необязательны):
#   YUMMY_APPLY_DRY_RUN=1        показать план и выйти до первой мутации.
#   YUMMY_APPLY_ROLLBACK=<путь>  вернуть указанный снапшот и выйти.
#
# Откат: текущий файл сохраняется ДО первой мутации и при любой ошибке —
# включая провал приёмки — возвращается на место вместе с перезапуском юнита.
# Снапшоты не удаляются: откатываться должно быть на что.
#
# ПАРНАЯ ПРАВКА. Полный эффект даёт только пара:
#   sbc-create/test#68      — этот файл (слой витрины);
#   sbc-create/yummyani#14  — SEO_INDEXING_ENABLED=true у тенанта web-site.
# По отдельности каждая половина дефект не снимает.

set -Eeuo pipefail

readonly FRONTEND_DIR=/srv/lords/.frontend
readonly TARGET="${FRONTEND_DIR}/yummy-frontend.py"
readonly UNIT=nova-yummy-site.service
readonly SNAPSHOT_ROOT="${FRONTEND_DIR}/.rollback"

# Порты витрин на loopback. Открытым объявлен только site; org и biz здесь
# присутствуют исключительно ради приёмки «они не изменились».
readonly PORT_SITE=9132
readonly PORT_ORG=9131
readonly PORT_BIZ=9130

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly SOURCE="${ROOT_DIR}/automation/host/yummy-frontend.py"

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

digest() { sha256sum "$1" | cut -d' ' -f1; }

# Заголовки ответа витрины. Пустая строка, если витрина не ответила.
head_of() {
  local port="$1" host="$2"
  curl -sS -D - -o /dev/null --max-time 20 -H "Host: ${host}" \
       "http://127.0.0.1:${port}/" 2>/dev/null || true
}

robots_of() {
  local port="$1" host="$2"
  curl -sS --max-time 20 -H "Host: ${host}" \
       "http://127.0.0.1:${port}/robots.txt" 2>/dev/null || true
}

wait_unit() {
  local attempt
  for attempt in $(seq 1 30); do
    : "${attempt}"
    if curl -sS -o /dev/null --max-time 5 \
            "http://127.0.0.1:${PORT_SITE}/healthz" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# ---------------------------------------------------------------- приёмка ---
#
# Проверяется то, что увидит краулер, а не то, что написано в конфигурации.
acceptance() {
  local failed=0

  local head_site; head_site="$(head_of "${PORT_SITE}" yummyani.site)"
  if [ -z "${head_site}" ]; then
    warn "yummyani.site не ответил"
    return 1
  fi

  # На открытом домене заголовка не должно быть вовсе.
  #
  # Проверяется отсутствие, а не значение: `noindex` закрыл бы сайт, а
  # глобальный `index` перекрыл бы точечные запреты приложения — при конфликте
  # директив побеждает строгая. Верен ровно один исход: заголовка нет.
  if grep -qi '^X-Robots-Tag:' <<<"${head_site}"; then
    warn "yummyani.site отдаёт X-Robots-Tag — на открытом домене его быть не должно:"
    warn "  $(grep -i '^X-Robots-Tag:' <<<"${head_site}" | head -1)"
    failed=1
  fi

  # robots.txt обязан прийти от приложения, а не от витрины. Признак ответа
  # витрины — две строки без единого комментария: у приложения есть и шапка,
  # и точечные запреты, и строка Sitemap.
  local robots_site; robots_site="$(robots_of "${PORT_SITE}" yummyani.site)"
  if [ "$(printf '%s' "${robots_site}" | grep -c .)" -le 2 ] \
     && ! grep -q '^#' <<<"${robots_site}"; then
    warn "robots.txt всё ещё отдаёт витрина, а не приложение"
    failed=1
  fi

  # Соседние площадки обязаны остаться закрытыми. Это не формальность:
  # политику .org и .biz задание прямо запретило пересматривать.
  local pair host port head_other
  for pair in "yummyani.org:${PORT_ORG}" "yummyani.biz:${PORT_BIZ}"; do
    host="${pair%%:*}"
    port="${pair##*:}"
    head_other="$(head_of "${port}" "${host}")"
    if [ -z "${head_other}" ]; then
      warn "${host} не ответил — состояние соседней площадки неизвестно"
      failed=1
    elif ! grep -qi '^X-Robots-Tag:.*noindex' <<<"${head_other}"; then
      warn "${host} ПЕРЕСТАЛ быть закрытым — правка задела соседнюю площадку"
      failed=1
    fi
  done

  return "${failed}"
}

restore() {
  local snapshot="$1"
  warn "откат на ${snapshot}"
  install -m 0755 -o root -g root "${snapshot}" "${TARGET}"
  systemctl restart "${UNIT}"
  wait_unit || warn "после отката витрина не поднялась — нужен оператор"
}

# ------------------------------------------------------------------ старт ---

[ -r "${SOURCE}" ] || die "нет исходника: ${SOURCE}"

if [ -n "${YUMMY_APPLY_ROLLBACK:-}" ]; then
  [ -r "${YUMMY_APPLY_ROLLBACK}" ] || die "снапшот не читается: ${YUMMY_APPLY_ROLLBACK}"
  [ "$(id -u)" -eq 0 ] || die "откат требует root"
  restore "${YUMMY_APPLY_ROLLBACK}"
  if acceptance; then
    log "откат применён, приёмка пройдена"
  else
    warn "откат применён, приёмка не пройдена — разбирается оператором"
  fi
  exit 0
fi

[ -f "${TARGET}" ] || die "витрина не выложена: ${TARGET} не найден"

SOURCE_SUM="$(digest "${SOURCE}")"
TARGET_SUM="$(digest "${TARGET}")"

log "источник: ${SOURCE_SUM}"
log "выложено: ${TARGET_SUM}"

if [ "${SOURCE_SUM}" = "${TARGET_SUM}" ]; then
  log "файл уже совпадает — мутаций не требуется"
  if acceptance; then
    log "приёмка пройдена: yummyani.site открыт, соседние площадки закрыты"
    exit 0
  fi
  die "файл совпадает, но приёмка не пройдена — разбирается оператором"
fi

if [ -n "${YUMMY_APPLY_DRY_RUN:-}" ]; then
  log "DRY RUN: был бы выложен ${SOURCE} и перезапущен ${UNIT}"
  log "DRY RUN: мутаций не произведено"
  exit 0
fi

[ "$(id -u)" -eq 0 ] || die "выкладка требует root: sudo bash $0"

# --------------------------------------------------------------- снапшот ---
#
# Точки отката для yummy на хосте до сих пор не было: в .rollback лежат только
# lords-01 и zona-01, LKG-копий yummy-frontend.py ноль. Снимок делается ДО
# первой мутации, иначе откатываться будет не на что.
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SNAPSHOT_DIR="${SNAPSHOT_ROOT}/${STAMP}-yummy-site"
mkdir -p "${SNAPSHOT_DIR}"
SNAPSHOT="${SNAPSHOT_DIR}/yummy-frontend.py"
cp -a "${TARGET}" "${SNAPSHOT}"
printf '%s  yummy-frontend.py\n' "${TARGET_SUM}" > "${SNAPSHOT_DIR}/SHA256SUMS"
log "снапшот: ${SNAPSHOT}"

trap 'restore "${SNAPSHOT}"' ERR

# --------------------------------------------------------------- выкладка ---
install -m 0755 -o root -g root "${SOURCE}" "${TARGET}"
log "выложен ${SOURCE_SUM}"

systemctl restart "${UNIT}"
wait_unit || die "витрина не поднялась после перезапуска"

if ! acceptance; then
  trap - ERR
  restore "${SNAPSHOT}"
  die "приёмка не пройдена — возвращён прежний файл"
fi

trap - ERR
log "готово: yummyani.site открыт, yummyani.org и yummyani.biz не изменились"
log "откат при необходимости: YUMMY_APPLY_ROLLBACK=${SNAPSHOT} sudo -E bash $0"
log "ПОМНИТЬ: без sbc-create/yummyani#14 приложение продолжит отдавать noindex"
