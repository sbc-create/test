#!/usr/bin/env bash
# Публичная приёмка канареечного релиза lords-02.
#
# Проверяется то, что видит посетитель, и то, чем выкладку можно сверить.
# Каждая строка — отдельное утверждение с числом, а не «выглядит хорошо».
#
# Имена переменных латиницей: bash не создаёт переменную с кириллическим
# именем и отвечает «command not found» на месте присваивания.
set -uo pipefail

SITE="${1:-https://lordserial33.biz}"
N1="${2:-https://lordfilm47.space}"
N2="${3:-https://1lordserials1.online}"
fails=0

ok()   { printf "  ok     %s\n" "$*"; }
bad()  { fails=$((fails + 1)); printf "  ПРОВАЛ %s\n" "$*"; }
check() { # check "имя" "значение" "условие"
  if eval "$3"; then ok "$1: $2"; else bad "$1: $2"; fi
}

echo "=== 1. здоровье и личность релиза"
health="$(curl -s -m 15 "$SITE/healthz")"
echo "  $health"
rel="$(printf '%s' "$health" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("release"))' 2>/dev/null)"
tpl="$(printf '%s' "$health" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("template_digest"))' 2>/dev/null)"
check "релиз назван" "$rel" '[ -n "$rel" ] && [ "$rel" != "None" ]'
check "отпечаток шаблона назван" "${tpl:0:16}" '[ -n "$tpl" ] && [ "$tpl" != "None" ]'

echo "=== 2. фасеты"
genres=$(curl -s -m 20 "$SITE/genres/" | grep -oE 'href="/genres/[^"]+"' | sort -u | wc -l)
countries=$(curl -s -m 20 "$SITE/countries/" | grep -oE 'href="/countries/[^"]+"' | sort -u | wc -l)
check "жанров" "$genres" '[ "$genres" -ge 50 ]'
check "стран" "$countries" '[ "$countries" -ge 40 ]'

echo "=== 3. поиск применяется"
for q in матрица матрца vfnhbwf; do
  body=$(curl -s -m 20 "$SITE/search/?q=$q")
  size=${#body}
  hits=$(printf '%s' "$body" | grep -c 'search-results' || true)
  check "поиск «$q» собран на сервере (${size} б)" "$hits" '[ "$hits" -ge 1 ]'
done
empty=$(curl -s -m 20 "$SITE/search/?q=" | grep -c 'search-results' || true)
check "пустой запрос не отдаёт каталог" "$empty" '[ "$empty" -eq 0 ]'
junk=$(curl -s -m 20 "$SITE/search/?q=щщъфывzzz" | grep -c 'ничего не найдено' || true)
check "мусор честно не найден" "$junk" '[ "$junk" -ge 1 ]'
api=$(curl -s -m 20 "$SITE/api/search?q=матрица" | python3 -c 'import json,sys;print(json.load(sys.stdin)["count"])' 2>/dev/null || echo 0)
check "api поиска отвечает" "$api" '[ "$api" -ge 1 ]'

echo "=== 4. карточка, длительности, плеер"
u=$(curl -s -m 20 "$SITE/catalog/" | grep -oE 'href="/title/[^"]+"' | head -1 | sed 's/href="//;s/"//')
curl -s -m 20 "$SITE$u" > /tmp/card.html
ptnone=$(grep -c "PTNoneM" /tmp/card.html || true)
zeromin=$(grep -oE ">0 мин<" /tmp/card.html | wc -l)
player=$(grep -c "video-player" /tmp/card.html || true)
check "PTNoneM на карточке $u" "$ptnone" '[ "$ptnone" -eq 0 ]'
check "«0 мин» на карточке" "$zeromin" '[ "$zeromin" -eq 0 ]'
check "плеер на карточке" "$player" '[ "$player" -ge 1 ]'

echo "=== 5. основные разделы"
for path in "/" "/catalog/" "/catalog/page/2/" "/genres/" "/countries/"; do
  code=$(curl -s -o /dev/null -m 20 -w "%{http_code}" "$SITE$path")
  check "GET $path" "$code" '[ "$code" = "200" ]'
done

echo "=== 6. соседние витрины не задеты"
for nb in "$N1" "$N2"; do
  code=$(curl -s -o /dev/null -m 20 -w "%{http_code}" "$nb/")
  check "GET $nb" "$code" '[ "$code" = "200" ]'
done

echo
echo "провалов: $fails"
exit $((fails > 0))
