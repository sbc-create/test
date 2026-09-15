#!/usr/bin/env bash
# Применение исправленного подвала витрин Animedia. Одна команда, идемпотентна.
#
#   sudo bash /srv/site-factory/repo/automation/host/apply-animedia-footer-013.sh           # canary: animedia.icu
#   sudo bash /srv/site-factory/repo/automation/host/apply-animedia-footer-013.sh --rollout # после PASS: animedia.space
#   sudo bash /srv/site-factory/repo/automation/host/apply-animedia-footer-013.sh --rollback
#
# Что делает:
#   * сохраняет точку отката ДО первой записи — без неё не начинает;
#   * подменяет общий артефакт /srv/lords/.frontend/lords-frontend.py;
#   * перезапускает ОДИН юнит и проверяет его вывод;
#   * при любом отказе возвращает прежний артефакт и перезапускает юнит обратно.
#
# Чего не делает: не трогает nginx, сертификаты, DNS, каталоги содержимого,
# манифесты и юниты соседних витрин. Витрины lords и zona исполняют свои ветки
# отрисовки и до собственного перезапуска подмены не замечают; их отметки
# выпуска в новом артефакте сохранены дословно — проверено по файлу: четыре
# места с data-template-version, три вызова _мета_версии и четыре бейджа
# Template: остались на месте, убрана только ветка animedia-portal.
#
# Имена переменных — ASCII. Кириллическое имя bash разбирает не как
# присваивание, а как команду: `ФРОНТ=/srv/...` даёт «No such file or
# directory», а `${ФРОНТ}` — «bad substitution». Проверено запуском.
#
# Почему это отдельный скрипт, а не lords-nova-canary.py: в реестре ВИТРИНЫ
# того инструмента есть только lords-01 и zona-01, animedia нет ни в одной его
# ревизии, а расширять перечень он прямо запрещает.
set -Eeuo pipefail

FRONT=/srv/lords/.frontend
ARTIFACT="${FRONT}/lords-frontend.py"
ROLLBACKS="${FRONT}/.rollback"
SOURCE="${SOURCE:-/srv/site-factory/repo/automation/host/lords-frontend.py}"

#: Ожидаемая сумма исправленного артефакта. Несовпадение — отказ: применять
#: «какой-то другой файл» этим скриптом нельзя, иначе он превращается в
#: произвольную запись в файл, который исполняют шесть витрин.
EXPECTED_SHA=c2230def39bd47b49bd23244dca617c2210ad2562eeae59fb6cd010b210fed9e

UNIT_1=nova-animedia-01.service
PORT_1=9121
UNIT_2=nova-animedia-02.service
PORT_2=9122
PREVIOUS=""

log()  { printf '[animedia-013] %s\n' "$*"; }
fail() { printf '[animedia-013] ОТКАЗ: %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || fail "нужен root: sudo bash $0"

check_output() {  # порт имя -> 0 если чисто
  local port="$1" name="$2" body bad=0
  body="$(curl -fsS --max-time 20 "http://127.0.0.1:${port}/" 2>/dev/null || true)"
  [[ -n ${body} ]] || { log "  ${name}: пустой ответ"; return 1; }
  local marker
  for marker in 'Template:' 'тестовая витрина' 'закрыта от индексации' \
                'data-build-id' 'data-template-version' 'site-factory-build-id'; do
    if grep -qF "${marker}" <<<"${body}"; then
      log "  ${name}: в HTML осталось «${marker}»"
      bad=1
    fi
  done
  grep -q 'mailto:' <<<"${body}" || { log "  ${name}: нет строки связи"; bad=1; }
  return "${bad}"
}

wait_ready() {  # порт
  local port="$1" _i
  for _i in $(seq 1 30); do
    curl -fsS --max-time 3 "http://127.0.0.1:${port}/" >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

restore() {
  [[ -n ${PREVIOUS} && -s ${PREVIOUS} ]] || return 0
  install -m 0755 -o root -g root "${PREVIOUS}" "${ARTIFACT}"
  systemctl restart "${UNIT_1}" || true
  log "прежний артефакт возвращён"
}

# ---------------------------------------------------------------- откат
if [[ ${1:-} == --rollback ]]; then
  last="$(find "${ROLLBACKS}" -maxdepth 1 -type d -name 'pre-013-*' | sort | tail -1)"
  [[ -n ${last} ]] || fail "точек отката pre-013-* нет"
  [[ -s ${last}/lords-frontend.py ]] || fail "в ${last} нет артефакта"
  install -m 0755 -o root -g root "${last}/lords-frontend.py" "${ARTIFACT}"
  systemctl restart "${UNIT_1}" "${UNIT_2}"
  wait_ready "${PORT_1}" || fail "после отката ${UNIT_1} не отвечает"
  log "откат выполнен из ${last}"
  exit 0
fi

# ---------------------------------------------------------------- источник
[[ -f ${SOURCE} ]] || fail "нет исходного артефакта ${SOURCE}"
source_sha="$(sha256sum "${SOURCE}" | cut -d' ' -f1)"
[[ ${source_sha} == "${EXPECTED_SHA}" ]] \
  || fail "сумма ${SOURCE} = ${source_sha}, ожидалась ${EXPECTED_SHA}"
log "источник сверен: ${source_sha}"

current_sha="$(sha256sum "${ARTIFACT}" | cut -d' ' -f1)"

# ---------------------------------------------------------------- rollout
if [[ ${1:-} == --rollout ]]; then
  [[ ${current_sha} == "${EXPECTED_SHA}" ]] \
    || fail "артефакт ещё не применён — сначала прогон без --rollout"
  check_output "${PORT_1}" animedia.icu \
    || fail "canary animedia.icu не проходит, вторая витрина не трогается"
  systemctl restart "${UNIT_2}"
  wait_ready "${PORT_2}" || fail "${UNIT_2} не отвечает"
  if ! check_output "${PORT_2}" animedia.space; then
    systemctl restart "${UNIT_2}"
    fail "animedia.space не проходит проверку"
  fi
  log "animedia.space: PASS"
  exit 0
fi

# ---------------------------------------------------------------- canary
if [[ ${current_sha} == "${EXPECTED_SHA}" ]]; then
  log "артефакт уже применён, запись пропущена"
else
  stamp="pre-013-$(date -u +%Y%m%dT%H%M%SZ)"
  install -d -m 0755 "${ROLLBACKS}/${stamp}"
  cp -a "${ARTIFACT}" "${ROLLBACKS}/${stamp}/lords-frontend.py"
  [[ -s ${ROLLBACKS}/${stamp}/lords-frontend.py ]] \
    || fail "точка отката не сохранилась — выкладка не начинается"
  PREVIOUS="${ROLLBACKS}/${stamp}/lords-frontend.py"
  log "точка отката: ${ROLLBACKS}/${stamp}"
  install -m 0755 -o root -g root "${SOURCE}" "${ARTIFACT}"
  log "артефакт заменён"
fi

systemctl restart "${UNIT_1}"
if ! wait_ready "${PORT_1}"; then
  restore
  fail "${UNIT_1} не отвечает"
fi

if ! check_output "${PORT_1}" animedia.icu; then
  restore
  fail "animedia.icu не проходит проверку"
fi

log "animedia.icu: PASS (служебных строк нет, адрес связи на месте)"
log "вторая витрина: sudo bash $0 --rollout"
