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

TARGET=/srv/lords/.frontend/yummy-frontend.py
UNIT=nova-yummy-site.service
OPEN_DOMAIN=yummyani.site
# Объявленная политика витрины. Её тоже надо привести к решению владельца:
# иначе объявление («индексация запрещена») будет противоречить факту, а
# суточная проверка согласованности будет вечно показывать расхождение — и
# настоящее расхождение в этом шуме потеряется.
PROFILE=/srv/site-factory/repo/config/site-profiles/yummyani-site.json
CLOSED_DOMAINS=(yummyani.org yummyani.biz lordfilm47.space lordserial33.biz
                1lordserials1.online zonafilm.space animedia.icu animedia.space)

SOURCE=${SOURCE:-$(dirname "$(readlink -f "$0")")/yummy-frontend.py}
# Слепок версии, поверх которой сделана правка. Если на хосте лежит другое
# содержимое, значит файл меняли после подготовки — выкладка отменяется, чтобы
# не затереть чужую работу.
EXPECTED_BEFORE=97e4f1933de57aff65053253c0546ebbed478c180250b36d28b725d6d74200d7
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="${TARGET}.before-open-indexing.${STAMP}"

step() { printf '\n== %s\n' "$*"; }
fail() { printf '!! %s\n' "$*" >&2; }

check_open() {
  local errors=0 code headers robots html
  headers=$(curl -sSI --max-time 25 "https://${OPEN_DOMAIN}/" || true)
  code=$(printf '%s' "$headers" | awk 'NR==1{print $2}')
  [ "$code" = "200" ] || { fail "${OPEN_DOMAIN}: код ${code:-нет ответа}"; errors=1; }
  if printf '%s' "$headers" | grep -qi 'x-robots-tag'; then
    fail "${OPEN_DOMAIN}: заголовок X-Robots-Tag всё ещё отдаётся"; errors=1
  fi
  robots=$(curl -sS --max-time 25 "https://${OPEN_DOMAIN}/robots.txt" || true)
  if printf '%s' "$robots" | grep -qE '^[[:space:]]*Disallow:[[:space:]]*/[[:space:]]*$'; then
    fail "${OPEN_DOMAIN}: robots.txt всё ещё содержит Disallow: /"; errors=1
  fi
  html=$(curl -sS --max-time 30 "https://${OPEN_DOMAIN}/" || true)
  if printf '%s' "$html" | grep -qi 'name="robots"[^>]*content="[^"]*noindex'; then
    fail "${OPEN_DOMAIN}: meta robots всё ещё noindex"; errors=1
  fi
  if ! printf '%s' "$html" | grep -qi "rel=\"canonical\"[^>]*href=\"https://${OPEN_DOMAIN}"; then
    fail "${OPEN_DOMAIN}: canonical не указывает на собственный домен"; errors=1
  fi
  return $errors
}

check_closed() {
  local errors=0 d headers robots
  for d in "${CLOSED_DOMAINS[@]}"; do
    headers=$(curl -sSI --max-time 25 "https://${d}/" || true)
    if ! printf '%s' "$headers" | grep -qi 'x-robots-tag.*noindex'; then
      fail "${d}: пропал X-Robots-Tag: noindex — домен не должен был открыться"; errors=1
    fi
    robots=$(curl -sS --max-time 25 "https://${d}/robots.txt" || true)
    if ! printf '%s' "$robots" | grep -qE '^[[:space:]]*Disallow:[[:space:]]*/[[:space:]]*$'; then
      fail "${d}: robots.txt больше не запрещает обход"; errors=1
    fi
  done
  return $errors
}

wait_for_service() {
  local n=0
  until curl -sS -o /dev/null --max-time 10 "https://${OPEN_DOMAIN}/" 2>/dev/null; do
    n=$((n + 1))
    [ "$n" -ge 30 ] && return 1
    sleep 2
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
  chown "$PROFILE_OWNER" "$PROFILE"
  printf '   копия профиля: %s\n' "$PROFILE_BACKUP"
else
  PROFILE_BACKUP=""
  fail "профиль недоступен на запись, объявленная политика останется прежней: $PROFILE"
fi

step "установка и перезапуск ${UNIT} (службы .org и .biz не трогаются)"
install -o root -g root -m 0755 "$SOURCE" "$TARGET"
systemctl restart "$UNIT"
wait_for_service || fail "служба не отвечает после перезапуска"

step "проверка на публичном адресе"
if check_open && check_closed; then
  step "готово: ${OPEN_DOMAIN} открыт, остальные восемь закрыты"
  printf 'YUMMYANI_SITE_PUBLIC_INDEXING=OPEN_PASS\n'
  printf 'OTHER_DOMAINS_INDEXING=LOCKED_PASS\n'
  printf 'BACKUP=%s\n' "$BACKUP"
  exit 0
fi

fail "проверки не прошли — откатываю"
install -o root -g root -m 0755 "$BACKUP" "$TARGET"
if [ -n "${PROFILE_BACKUP:-}" ]; then
  cp -p "$PROFILE_BACKUP" "$PROFILE"
fi
systemctl restart "$UNIT"
wait_for_service || true
fail "откат выполнен, копии сохранены: $BACKUP ${PROFILE_BACKUP:-}"
exit 1
