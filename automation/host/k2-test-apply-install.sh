#!/usr/bin/env bash
# НАСТОЯЩАЯ установка доставленного каталога — в отдельном каталоге, без root.
#
# Зачем отдельно от k2-test-apply-cycle.sh. Тот проверяет РАЗБОР комплекта:
# что годный принят, а порченый отвергнут. Но «принят» и «установлен» — разные
# утверждения: установка переносит файлы, выставляет владельца и режим,
# сохраняет прежний снимок и обязана быть идемпотентной. Проверить это можно
# только выполнив её.
#
# Как без root: приёмщик спрашивает не «я root», а «можно ли писать в каталог
# данных». В производстве каталог 0750 и принадлежит витрине — значит только
# root; здесь каталог создаёт сам тест и владеет им, поэтому установка идёт
# тем же кодом и теми же вызовами `install`.
#
# Производство не затрагивается: своя опись, свой входящий каталог, свой корень
# данных во временном каталоге.
#
# Имена переменных только ASCII.
#
# Запуск на узле:  k2-test-apply-install.sh <site_id>
set -uo pipefail

site="${1:?нужен site_id}"
stage="/home/k2deploy/stage"
src="$stage/data/$site"
apply="$stage/k2-catalog-apply.sh"
work="$(mktemp -d)"
account="$(id -un)"
data="$work/srv/$account/data"
inbox="$work/incoming"
ok=0
fail=0

note() { printf '%-46s %s\n' "$1" "$2"; }

mkdir -p "$data" "$inbox/$site"
# Опись с учётной записью текущего пользователя: установка пойдёт «с правами
# витрины», где витрина — это я. Значения порта и юнита здесь не важны.
python3 - "$stage/MANIFEST.json" "$site" "$account" "$work/MANIFEST.json" <<'PY'
import json, sys
опись = json.load(open(sys.argv[1], encoding="utf-8"))
ячейка = dict((опись.get("cells") or {})[sys.argv[2]])
ячейка["account"] = sys.argv[3]
json.dump({"cells": {sys.argv[2]: ячейка}}, open(sys.argv[4], "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
PY

kit() {
  rm -rf "$inbox/$site"; mkdir -p "$inbox/$site"
  cp "$src/$site-catalog.json" "$src/$site-details.json" "$inbox/$site/"
  ( cd "$inbox/$site" && sha256sum ./*.json > SHA256SUMS )
}

run_install() {
  K2_INCOMING="$inbox" K2_MANIFEST="$work/MANIFEST.json" K2_SRV_ROOT="$work/srv" \
    "$apply" "$site" >"$work/out.txt" 2>&1
  echo $?
}

echo "=== установка 1: пустой каталог данных"
kit
before_items=$(ls -1 "$data" | wc -l)
rc=$(run_install)
after_items=$(ls -1 "$data" | wc -l)
if [ "$rc" = 0 ] && [ "$after_items" -ge 2 ]; then
  note "комплект установлен" "OK (файлов было $before_items, стало $after_items)"; ok=$((ok+1))
else
  note "комплект установлен" "ПРОВАЛ (код $rc, файлов $after_items)"; fail=$((fail+1))
  sed 's/^/   /' "$work/out.txt"
fi
mode=$(stat -c '%a %U:%G' "$data/$site-catalog.json" 2>/dev/null)
if [ "$mode" = "640 $account:$account" ]; then
  note "режим и владелец каталога" "OK ($mode)"; ok=$((ok+1))
else
  note "режим и владелец каталога" "ПРОВАЛ ($mode)"; fail=$((fail+1))
fi
if [ ! -d "$inbox/$site" ]; then
  note "входящий комплект убран" "OK"; ok=$((ok+1))
else
  note "входящий комплект убран" "ПРОВАЛ: остался"; fail=$((fail+1))
fi

echo "=== установка 2: повтор без нового комплекта (идемпотентность)"
rc=$(run_install)
if [ "$rc" = 0 ] && grep -q "установлено витрин: 0" "$work/out.txt"; then
  note "повтор ничего не ставит" "OK"; ok=$((ok+1))
else
  note "повтор ничего не ставит" "ПРОВАЛ (код $rc)"; fail=$((fail+1))
  sed 's/^/   /' "$work/out.txt"
fi

echo "=== установка 3: новый комплект поверх прежнего"
# Метка внутри данных, чтобы различить прежний снимок и новый.
python3 - "$data/$site-catalog.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["_test_marker"] = "previous"
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PY
kit
rc=$(run_install)
prev_marker=$(python3 - "$data/$site-catalog.json.prev" <<'PY'
import json, sys
try:
    print(json.load(open(sys.argv[1], encoding="utf-8")).get("_test_marker", ""))
except Exception:
    print("")
PY
)
new_marker=$(python3 - "$data/$site-catalog.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("_test_marker", ""))
PY
)
if [ "$rc" = 0 ] && [ "$prev_marker" = "previous" ] && [ -z "$new_marker" ]; then
  note "прежний снимок сохранён в .prev" "OK"; ok=$((ok+1))
else
  note "прежний снимок сохранён в .prev" "ПРОВАЛ (prev='$prev_marker', new='$new_marker', код $rc)"
  fail=$((fail+1))
fi

echo "=== установка 4: порченый комплект не затирает установленное"
kit
printf '\n' >> "$inbox/$site/$site-details.json"   # суммы перестают сходиться
sum_before=$(sha256sum "$data/$site-details.json" | cut -d' ' -f1)
rc=$(run_install)
sum_after=$(sha256sum "$data/$site-details.json" | cut -d' ' -f1)
if [ "$rc" != 0 ] && [ "$sum_before" = "$sum_after" ] && [ -d "$inbox/$site" ]; then
  note "порченый отвергнут, данные целы" "OK"; ok=$((ok+1))
else
  note "порченый отвергнут, данные целы" "ПРОВАЛ (код $rc, суммы $sum_before/$sum_after)"
  fail=$((fail+1))
fi

rm -rf "$work"
echo "итог: пройдено $ok, провалено $fail"
[ "$fail" = 0 ] || exit 1
