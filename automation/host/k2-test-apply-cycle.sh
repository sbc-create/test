#!/usr/bin/env bash
# Проверка цикла приёма каталога на изолированном комплекте — без root.
#
# Что проверяется: приёмщик (`k2-catalog-apply.sh`) принимает годный комплект и
# ОТКАЗЫВАЕТ на каждом виде порчи — неполный набор, битая сумма, чужой `site`,
# слишком мало элементов. Иначе «проверка комплекта» была бы словами: принять
# можно и мусор, если никто не пробовал подсунуть мусор.
#
# Всё происходит во временном каталоге: ни данные витрин, ни входящий каталог
# производства не трогаются.
#
# Имена переменных только ASCII.
#
# Запуск на узле:  k2-test-apply-cycle.sh <site_id>
set -uo pipefail

site="${1:?нужен site_id}"
stage="/home/k2deploy/stage"
src="$stage/data/$site"
apply="$stage/k2-catalog-apply.sh"
work="$(mktemp -d)"
inbox="$work/incoming"
ok=0
fail=0

note() { printf '%-44s %s\n' "$1" "$2"; }

kit() {   # kit <имя случая>  — собрать годный комплект в $inbox/$site
  rm -rf "$inbox/$site"; mkdir -p "$inbox/$site"
  cp "$src/$site-catalog.json" "$src/$site-details.json" "$inbox/$site/"
  [ -f "$src/$site-data-provenance.json" ] && \
    cp "$src/$site-data-provenance.json" "$inbox/$site/"
  ( cd "$inbox/$site" && sha256sum ./*.json > SHA256SUMS )
}

run() {   # run — запустить приёмщик в режиме проверки, вернуть код
  K2_INCOMING="$inbox" K2_MANIFEST="$stage/MANIFEST.json" \
  K2_SRV_ROOT="$work/srv" "$apply" --check-only "$site" >"$work/out.txt" 2>&1
  echo $?
}

# Каталог данных витрины в песочнице: приёмщик обязан его видеть.
account=$(python3 - "$stage/MANIFEST.json" "$site" <<'PY'
import json, sys
cells = json.load(open(sys.argv[1], encoding="utf-8")).get("cells") or {}
print((cells.get(sys.argv[2]) or {}).get("account", ""))
PY
)
[ -n "$account" ] || { echo "в описи нет $site"; exit 2; }
mkdir -p "$work/srv/$account/data"

echo "=== случай 1: годный комплект"
kit
rc=$(run)
if [ "$rc" = 0 ]; then note "годный принят" "OK"; ok=$((ok+1)); else
  note "годный принят" "ПРОВАЛ (код $rc)"; fail=$((fail+1)); sed 's/^/   /' "$work/out.txt"; fi
grep -E "элементов|ревизия" "$work/out.txt" | head -2 | sed 's/^/   /'

echo "=== случай 2: нет файла подробностей"
kit; rm -f "$inbox/$site/$site-details.json"
rc=$(run)
if [ "$rc" != 0 ]; then note "неполный отвергнут" "OK"; ok=$((ok+1)); else
  note "неполный отвергнут" "ПРОВАЛ: принят"; fail=$((fail+1)); fi

echo "=== случай 3: битая сумма"
kit; printf '\n' >> "$inbox/$site/$site-catalog.json"
rc=$(run)
if [ "$rc" != 0 ]; then note "битая сумма отвергнута" "OK"; ok=$((ok+1)); else
  note "битая сумма отвергнута" "ПРОВАЛ: принят"; fail=$((fail+1)); fi

echo "=== случай 4: чужой site внутри файла"
kit
python3 - "$inbox/$site/$site-catalog.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["site"] = "lords-01"
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PY
( cd "$inbox/$site" && sha256sum ./*.json > SHA256SUMS )
rc=$(run)
if [ "$rc" != 0 ]; then note "чужой site отвергнут" "OK"; ok=$((ok+1)); else
  note "чужой site отвергнут" "ПРОВАЛ: принят"; fail=$((fail+1)); fi
grep -E "problem" "$work/out.txt" | head -2 | sed 's/^/   /'

echo "=== случай 5: пустой каталог"
kit
python3 - "$inbox/$site/$site-catalog.json" "$site" <<'PY'
import json, sys
p, site = sys.argv[1], sys.argv[2]
json.dump({"site": site, "count": 0, "items": [], "revision": "0" * 32},
          open(p, "w", encoding="utf-8"), ensure_ascii=False)
PY
( cd "$inbox/$site" && sha256sum ./*.json > SHA256SUMS )
rc=$(run)
if [ "$rc" != 0 ]; then note "пустой каталог отвергнут" "OK"; ok=$((ok+1)); else
  note "пустой каталог отвергнут" "ПРОВАЛ: принят"; fail=$((fail+1)); fi

rm -rf "$work"
echo "итог: пройдено $ok, провалено $fail"
[ "$fail" = 0 ] || exit 1
