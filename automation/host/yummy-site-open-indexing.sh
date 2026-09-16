#!/usr/bin/env bash
# Открыть индексацию ТОЛЬКО для yummyani.site.
#
# Зачем нужен отдельный сценарий. Решение владельца от 2026-09-15 уже выложено в
# приложение (SEO_INDEXING_ENABLED=true для одной службы), но в силу не вступило:
# перед приложением стоит посредник /srv/lords/.frontend/yummy-frontend.py,
# который независимо от приложения слал `X-Robots-Tag: noindex, nofollow` и
# отдавал собственный `robots.txt` с `Disallow: /`. Правится именно посредник.
#
# Чего сценарий НЕ делает:
#   * не трогает nginx — в 443-блоке yummyani.site заголовка уже нет;
#   * не перезапускает службы yummyani.org и yummyani.biz: они продолжают
#     работать на прежнем коде и остаются закрытыми;
#   * ничего не отправляет в поисковые системы.
#
# Идемпотентность: повторный запуск на уже применённой версии ничего не
# выкладывает, а только перепроверяет результат.
#
# Откат: при любой неуспешной проверке возвращается копия, служба
# перезапускается, состояние проверяется ещё раз. Ненулевой выход означает, что
# открытие НЕ состоялось.

set -euo pipefail

# Пути и пороги переопределяемы ради проверяемости: умолчания боевые и не
# менялись, а тест подставляет свою песочницу и прогоняет все ветки, включая
# откат, не касаясь production.
TARGET=${TARGET:-/srv/lords/.frontend/yummy-frontend.py}
# Артефакт политики индексации. Посредник читает его и ничего не решает сам,
# поэтому выложить посредник без артефакта — значит закрыть все витрины: файла
# нет, решения нет, по умолчанию закрыто. Оба файла кладутся одним шагом.
POLICY_TARGET=${POLICY_TARGET:-/srv/lords/.frontend/indexing-policy.json}
PROFILES_DIR=${PROFILES_DIR:-$(dirname "$(readlink -f "$0")")/../../config/site-profiles}
UNIT=${UNIT:-nova-yummy-site.service}
OPEN_DOMAIN=yummyani.site
# Объявленная политика витрины. Её тоже надо привести к решению владельца:
# иначе объявление («индексация запрещена») будет противоречить факту, а
# суточная проверка согласованности будет вечно показывать расхождение — и
# настоящее расхождение в этом шуме потеряется.
PROFILE=${PROFILE:-/srv/site-factory/repo/config/site-profiles/yummyani-site.json}
CLOSED_DOMAINS=(yummyani.org yummyani.biz lordfilm47.space lordserial33.biz
                1lordserials1.online zonafilm.space animedia.icu animedia.space)

SOURCE=${SOURCE:-$(dirname "$(readlink -f "$0")")/yummy-frontend.py}
# Слепок версии, поверх которой сделана правка. Если на хосте лежит другое
# содержимое, значит файл меняли после подготовки — выкладка отменяется, чтобы
# не затереть чужую работу.
EXPECTED_BEFORE=${EXPECTED_BEFORE:-97e4f1933de57aff65053253c0546ebbed478c180250b36d28b725d6d74200d7}
# Внешние команды вынесены в переменные, чтобы сценарий можно было проверить
# целиком, не трогая production: тест подставляет свои curl и systemctl и
# прогоняет все ветки, включая откат. Умолчания — настоящие команды, поэтому в
# бою поведение не меняется.
CURL=${CURL:-curl}
SYSTEMCTL=${SYSTEMCTL:-systemctl}
# Владение целевым файлом задаётся отдельно: под root это root:root, а тест
# запускается обычной учётной записью и передаёт пустую строку. Массив, а не
# строка: строку пришлось бы оставлять без кавычек ради разбиения на аргументы,
# а это ровно тот приём, который однажды подставит лишний аргумент из имени
# файла. Подстановка `-` вместо `:-` намеренна: пустая строка здесь осмысленна
# и означает «владение не менять».
read -r -a INSTALL_OWNERSHIP <<< "${INSTALL_OWNERSHIP--o root -g root}"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="${TARGET}.before-open-indexing.${STAMP}"

step() { printf '\n== %s\n' "$*"; }
fail() { printf '!! %s\n' "$*" >&2; }

check_open() {
  # Страница берётся ОДНИМ запросом вместе с заголовками: прежде их брали
  # разными, и проверки могли судить о разных ответах. Плюс `-f` и повтор —
  # без них неудачный запрос давал пустое тело, `|| true` его проглатывал, и
  # отсутствие canonical в пустоте объявлялось дефектом страницы. Именно так
  # выкладка 2026-09-15T20:42Z откатилась при фактически верном результате.
  local errors=0 code headers_file body_file
  headers_file=$(mktemp)
  body_file=$(mktemp)

  if ! "$CURL" -fsS -D "$headers_file" -o "$body_file" \
       --retry 3 --retry-delay 3 --retry-all-errors \
       --max-time "$REQUEST_TIMEOUT" "https://${OPEN_DOMAIN}/"; then
    fail "${OPEN_DOMAIN}: страница не получена за ${REQUEST_TIMEOUT}s"
    rm -f "$headers_file" "$body_file"
    return 1
  fi
  if [ ! -s "$body_file" ]; then
    # Пустое тело — отдельная причина отказа, а не «на странице нет canonical».
    fail "${OPEN_DOMAIN}: ответ получен, но тело пустое"
    rm -f "$headers_file" "$body_file"
    return 1
  fi

  # Возврат каретки из CRLF срезается до сравнения: иначе код приходит как
  # "200\r", сравнение с "200" не совпадает, и проверка сообщает «код 200» как
  # об ошибке. Поймано офлайн-прогоном, а не на живом сайте.
  code=$(tr -d '\r' < "$headers_file" | awk 'toupper($1) ~ /^HTTP/ {c=$2} END{print c}')
  [ "$code" = "200" ] || { fail "${OPEN_DOMAIN}: код ${code:-нет ответа}"; errors=1; }
  if grep -qi '^x-robots-tag' "$headers_file"; then
    fail "${OPEN_DOMAIN}: заголовок X-Robots-Tag всё ещё отдаётся"; errors=1
  fi
  if grep -qi 'name="robots"[^>]*content="[^"]*noindex' "$body_file"; then
    fail "${OPEN_DOMAIN}: meta robots всё ещё noindex"; errors=1
  fi
  if ! grep -qi "rel=\"canonical\"[^>]*href=\"https://${OPEN_DOMAIN}" "$body_file"; then
    fail "${OPEN_DOMAIN}: canonical не указывает на собственный домен"; errors=1
  fi
  rm -f "$headers_file" "$body_file"

  local robots
  if ! robots=$("$CURL" -fsS --retry 3 --retry-delay 3 --retry-all-errors \
                --max-time "$REQUEST_TIMEOUT" "https://${OPEN_DOMAIN}/robots.txt"); then
    fail "${OPEN_DOMAIN}: robots.txt не получен"; return 1
  fi
  if printf '%s' "$robots" | grep -qE '^[[:space:]]*Disallow:[[:space:]]*/[[:space:]]*$'; then
    fail "${OPEN_DOMAIN}: robots.txt всё ещё содержит Disallow: /"; errors=1
  fi
  return $errors
}

check_closed() {
  local errors=0 d headers robots
  for d in "${CLOSED_DOMAINS[@]}"; do
    # Здесь `|| true` недопустим по той же причине: неполученный ответ
    # означал бы «запрет пропал» и валил выкладку, которая ни при чём.
    if ! headers=$("$CURL" -fsSI --retry 3 --retry-delay 3 --retry-all-errors \
                   --max-time "$REQUEST_TIMEOUT" "https://${d}/"); then
      fail "${d}: заголовки не получены — состояние домена не измерено"; errors=1; continue
    fi
    if ! printf '%s' "$headers" | grep -qi 'x-robots-tag.*noindex'; then
      fail "${d}: пропал X-Robots-Tag: noindex — домен не должен был открыться"; errors=1
    fi
    if ! robots=$("$CURL" -fsS --retry 3 --retry-delay 3 --retry-all-errors \
                  --max-time "$REQUEST_TIMEOUT" "https://${d}/robots.txt"); then
      fail "${d}: robots.txt не получен — состояние домена не измерено"; errors=1; continue
    fi
    if ! printf '%s' "$robots" | grep -qE '^[[:space:]]*Disallow:[[:space:]]*/[[:space:]]*$'; then
      fail "${d}: robots.txt больше не запрещает обход"; errors=1
    fi
  done
  return $errors
}

# Сколько ждать готовности и сколько отводить одному запросу.
#
# Обе величины измерены, а не выбраны. `"$SYSTEMCTL" restart` при Type=simple
# возвращается сразу после fork и готовности не дожидается. Порт витрина
# занимает мгновенно, но ПЕРВЫЙ запрос после старта идёт 44 секунды: прогреваются
# модель чтения и кеш вышестоящего приложения. Прежние 25 секунд на запрос и
# ожидание без требования кода 200 приводили к тому, что проверки шли по ещё не
# прогретой службе и видели 502 — именно на этом выкладка 2026-09-15T20:16Z
# откатилась, хотя сама правка верна.
REQUEST_TIMEOUT=${REQUEST_TIMEOUT:-90}
READINESS_ATTEMPTS=${READINESS_ATTEMPTS:-6}

wait_for_service() {
  local n=0
  # `-f` обязателен: без него curl считает успехом и 502, и ожидание готовности
  # становится холостым — оно завершалось на первом же ответе шлюза.
  until "$CURL" -fsS -o /dev/null --max-time "$REQUEST_TIMEOUT" "https://${OPEN_DOMAIN}/" 2>/dev/null; do
    n=$((n + 1))
    if [ "$n" -ge "$READINESS_ATTEMPTS" ]; then
      return 1
    fi
    printf '   прогрев, попытка %s из %s\n' "$n" "$READINESS_ATTEMPTS"
    sleep 5
  done
  return 0
}

[ -r "$SOURCE" ] || { fail "нет исходного файла: $SOURCE"; exit 2; }
NEW_SHA=$(sha256sum "$SOURCE" | cut -d' ' -f1)
CURRENT_SHA=$(sha256sum "$TARGET" | cut -d' ' -f1)

if [ "$CURRENT_SHA" = "$NEW_SHA" ]; then
  step "версия уже выложена — только проверяю"
  if check_open && check_closed; then
    step "состояние верное"
    printf 'YUMMYANI_SITE_PUBLIC_INDEXING=OPEN_PASS\n'
    printf 'OTHER_DOMAINS_INDEXING=LOCKED_PASS\n'
    exit 0
  fi
  fail "выложена нужная версия, но проверки не проходят"
  exit 1
fi

if [ "$CURRENT_SHA" != "$EXPECTED_BEFORE" ]; then
  fail "на хосте не та версия, поверх которой готовилась правка."
  fail "  ожидалось: $EXPECTED_BEFORE"
  fail "  фактически: $CURRENT_SHA"
  fail "файл меняли после подготовки. Выкладка отменена, чтобы её не затереть."
  exit 3
fi

step "копия: $BACKUP"
cp -p "$TARGET" "$BACKUP"

step "проверка синтаксиса новой версии"
python3 -m py_compile "$SOURCE"

step "объявленная политика витрины приводится к решению владельца"
if [ -w "$PROFILE" ] || [ -w "$(dirname "$PROFILE")" ]; then
  PROFILE_BACKUP="${PROFILE}.before-open-indexing.${STAMP}"
  cp -p "$PROFILE" "$PROFILE_BACKUP"
  PROFILE_OWNER=$(stat -c '%U:%G' "$PROFILE")
  python3 - "$PROFILE" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    profile = json.load(fh)
profile.setdefault("seo_profile", {})["indexing_enabled"] = True
with open(path, "w", encoding="utf-8") as fh:
    json.dump(profile, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY
  if [ "${#INSTALL_OWNERSHIP[@]}" -gt 0 ]; then chown "$PROFILE_OWNER" "$PROFILE"; fi
  printf '   копия профиля: %s\n' "$PROFILE_BACKUP"
else
  PROFILE_BACKUP=""
  fail "профиль недоступен на запись, объявленная политика останется прежней: $PROFILE"
fi

step "сборка артефакта политики и ворота релиза"
POLICY_BUILT=$(mktemp)
if ! python3 - "$PROFILES_DIR" "$POLICY_BUILT" <<'PYGATE'
import sys, pathlib
профили, цель = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path.insert(0, str(профили.resolve().parent.parent))
from factory.indexing.artifact import build, write
from factory.indexing.gate import check, require
from factory.indexing.policy import compile_policy

артефакт = build(профили)
матрица = артефакт["matrix"]
# Разрешённая владельцем матрица: один открытый домен, восемь закрытых.
require(check(
    compile_policy(профили),
    allowed_open={"yummyani.site"},
    allowed_closed=set(матрица["closed"]),
    live={d: "open" for d in матрица["open"]} | {d: "closed" for d in матрица["closed"]},
))
write(артефакт, цель)
print(f"   матрица: открыт {матрица['open_count']}, закрыт {матрица['closed_count']}")
print(f"   policy_sha256: {артефакт['manifest']['policy_sha256']}")
PYGATE
then
  fail "ворота релиза не пропустили выкладку — ничего не изменено"
  rm -f "$POLICY_BUILT"
  exit 4
fi

step "установка и перезапуск ${UNIT} (службы .org и .biz не трогаются)"
POLICY_BACKUP=""
if [ -f "$POLICY_TARGET" ]; then
  POLICY_BACKUP="${POLICY_TARGET}.before-open-indexing.${STAMP}"
  cp -p "$POLICY_TARGET" "$POLICY_BACKUP"
fi
install "${INSTALL_OWNERSHIP[@]}" -m 0644 "$POLICY_BUILT" "$POLICY_TARGET"
rm -f "$POLICY_BUILT"
install "${INSTALL_OWNERSHIP[@]}" -m 0755 "$SOURCE" "$TARGET"
"$SYSTEMCTL" restart "$UNIT"

step "ожидание готовности (первый запрос после старта идёт до минуты)"
READY=0
if wait_for_service; then
  READY=1
else
  fail "служба не отдала 200 после перезапуска"
fi

step "проверка на публичном адресе"
if [ "$READY" = "1" ] && check_open && check_closed; then
  step "готово: ${OPEN_DOMAIN} открыт, остальные восемь закрыты"
  printf 'YUMMYANI_SITE_PUBLIC_INDEXING=OPEN_PASS\n'
  printf 'OTHER_DOMAINS_INDEXING=LOCKED_PASS\n'
  printf 'BACKUP=%s\n' "$BACKUP"
  exit 0
fi

fail "проверки не прошли — откатываю"
install "${INSTALL_OWNERSHIP[@]}" -m 0755 "$BACKUP" "$TARGET"
if [ -n "${POLICY_BACKUP:-}" ]; then
  install "${INSTALL_OWNERSHIP[@]}" -m 0644 "$POLICY_BACKUP" "$POLICY_TARGET"
fi
if [ -n "${PROFILE_BACKUP:-}" ]; then
  cp -p "$PROFILE_BACKUP" "$PROFILE"
fi
"$SYSTEMCTL" restart "$UNIT"
if wait_for_service; then
  fail "откат выполнен и подтверждён: витрина снова отвечает 200"
else
  fail "ВНИМАНИЕ: после отката витрина не отдала 200 за отведённое время."
  fail "Проверьте вручную: curl -sSI https://${OPEN_DOMAIN}/ и systemctl status ${UNIT}"
fi
fail "копии сохранены: $BACKUP ${PROFILE_BACKUP:-}"
exit 1
