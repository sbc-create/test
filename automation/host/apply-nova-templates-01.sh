#!/usr/bin/env bash
# Применение шаблонов nova на три закрытые витрины. Идемпотентно.
#
#   sudo bash apply-nova-templates-01.sh              # canary: animedia.icu
#   sudo bash apply-nova-templates-01.sh --next       # после PASS: animedia.space
#   sudo bash apply-nova-templates-01.sh --zona       # после PASS: zonafilm.space
#   sudo bash apply-nova-templates-01.sh --rollback   # вернуть прежний артефакт всем трём
#
# Что делает: сверяет сумму источника, сохраняет точку отката ДО первой
# записи, подменяет общий артефакт, перезапускает РОВНО ОДИН юнит и проверяет
# его вывод. При любом отказе возвращает прежний артефакт и перезапускает
# юнит обратно.
#
# Чего не делает: не трогает nginx, сертификаты, DNS, манифесты, каталоги и
# юниты нецелевых витрин. Массового restart нет.
#
# Blast radius. Артефакт один на шесть витрин, но ветку отрисовки выбирает
# `design_version` манифеста. Правка сидит в ветках animedia-portal, zona-rail
# и zona-top; ветки Lords не тронуты — это проверено побайтовым сличением
# вывода с работающей витриной lords-nova-01 на /, /catalog/, /catalog/?page=3
# и /new/ при полном окружении юнита. До собственного перезапуска витрины
# Lords подмены вообще не замечают.
#
# Имена переменных ASCII: bash разбирает кириллическое имя не как
# присваивание, а как команду.
set -Eeuo pipefail

FRONT=/srv/lords/.frontend
ARTIFACT="${FRONT}/lords-frontend.py"
ROLLBACKS="${FRONT}/.rollback"
SOURCE="${SOURCE:-/home/claude/wt-yummy-013/automation/host/lords-frontend.py}"

#: Сумма проверенного артефакта. Несовпадение — отказ: применять этим
#: скриптом произвольный файл, который исполняют шесть витрин, нельзя.
EXPECTED_SHA=0e47d31dd373565603f3590544532261de0e74483b128ad2ac6523d8ac853357

PREVIOUS=""

log()  { printf '[nova-templates] %s\n' "$*"; }
fail() { printf '[nova-templates] ОТКАЗ: %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || fail "нужен root: sudo bash $0"

check_output() {  # порт имя -> 0 если чисто
  local port="$1" name="$2" body bad=0 marker
  body="$(curl -fsS --max-time 25 "http://127.0.0.1:${port}/" 2>/dev/null || true)"
  [[ -n ${body} ]] || { log "  ${name}: пустой ответ"; return 1; }
  for marker in 'Template:' 'тестовая витрина' 'закрыта от индексации' \
                'data-build-id' 'data-template-version' 'site-factory-build-id' \
                'SITE_LEGAL_NAME' 'SITE_CONTACT_EMAIL'; do
    if grep -qF "${marker}" <<<"${body}"; then
      log "  ${name}: в HTML осталось «${marker}»"
      bad=1
    fi
  done
  grep -q 'mailto:sbc.claude@yandex.ru' <<<"${body}" || { log "  ${name}: нет адреса связи"; bad=1; }
  # Индексация обязана остаться закрытой: это не то, что меняет эта выкладка.
  grep -q 'name="robots" content="noindex' <<<"${body}" || { log "  ${name}: витрина не закрыта от индексации"; bad=1; }
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
  systemctl restart nova-animedia-01.service nova-animedia-02.service nova-zona-01.service || true
  log "прежний артефакт возвращён, три юнита перезапущены"
}

deploy_one() {  # unit port name
  local unit="$1" port="$2" name="$3"
  systemctl restart "${unit}"
  if ! wait_ready "${port}"; then
    restore
    fail "${unit} не отвечает"
  fi
  if ! check_output "${port}" "${name}"; then
    restore
    fail "${name} не проходит проверку"
  fi
  log "${name}: PASS"
}

if [[ ${1:-} == --rollback ]]; then
  last="$(find "${ROLLBACKS}" -maxdepth 1 -type d -name 'pre-nova-templates-*' | sort | tail -1)"
  [[ -n ${last} && -s ${last}/lords-frontend.py ]] || fail "точки отката нет"
  install -m 0755 -o root -g root "${last}/lords-frontend.py" "${ARTIFACT}"
  systemctl restart nova-animedia-01.service nova-animedia-02.service nova-zona-01.service
  wait_ready 9121 || fail "после отката animedia.icu не отвечает"
  log "откат выполнен из ${last}"
  exit 0
fi

[[ -f ${SOURCE} ]] || fail "нет исходного артефакта ${SOURCE}"
source_sha="$(sha256sum "${SOURCE}" | cut -d' ' -f1)"
[[ ${source_sha} == "${EXPECTED_SHA}" ]] \
  || fail "сумма ${SOURCE} = ${source_sha}, ожидалась ${EXPECTED_SHA}"
log "источник сверен: ${source_sha}"

current_sha="$(sha256sum "${ARTIFACT}" | cut -d' ' -f1)"

case "${1:-}" in
  --next)
    [[ ${current_sha} == "${EXPECTED_SHA}" ]] || fail "артефакт не применён — сначала прогон без флага"
    check_output 9121 animedia.icu || fail "canary animedia.icu не проходит; следующая витрина не трогается"
    deploy_one nova-animedia-02.service 9122 animedia.space
    exit 0
    ;;
  --zona)
    [[ ${current_sha} == "${EXPECTED_SHA}" ]] || fail "артефакт не применён — сначала прогон без флага"
    check_output 9121 animedia.icu || fail "animedia.icu не проходит; zona не трогается"
    check_output 9122 animedia.space || fail "animedia.space не проходит; zona не трогается"
    deploy_one nova-zona-01.service 9120 zonafilm.space
    exit 0
    ;;
esac

if [[ ${current_sha} == "${EXPECTED_SHA}" ]]; then
  log "артефакт уже применён, запись пропущена"
else
  stamp="pre-nova-templates-$(date -u +%Y%m%dT%H%M%SZ)"
  install -d -m 0755 "${ROLLBACKS}/${stamp}"
  cp -a "${ARTIFACT}" "${ROLLBACKS}/${stamp}/lords-frontend.py"
  [[ -s ${ROLLBACKS}/${stamp}/lords-frontend.py ]] \
    || fail "точка отката не сохранилась — выкладка не начинается"
  PREVIOUS="${ROLLBACKS}/${stamp}/lords-frontend.py"
  log "точка отката: ${ROLLBACKS}/${stamp}"
  install -m 0755 -o root -g root "${SOURCE}" "${ARTIFACT}"
  log "артефакт заменён"
fi

deploy_one nova-animedia-01.service 9121 animedia.icu
log "следующая витрина: sudo bash $0 --next"
