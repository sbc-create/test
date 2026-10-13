#!/usr/bin/env bash
# Прикладная проверка доставленного комплекта витрины НА УЗЛЕ.
#
# Суммы доказывают, что байты доехали. Они не доказывают, что доехал КАТАЛОГ:
# файл нужного размера может быть пустым снимком или снимком другой витрины.
# Поэтому здесь — проверки содержимого: поле `site`, число элементов, ревизия,
# совпадение ревизии каталога и sidecar, и собственные проверки проекта кода.
#
# Имена переменных только ASCII (кириллица в именах переменных оболочки падает
# в работе, `bash -n` её пропускает).
#
# Запуск на узле:  k2-verify-payload.sh <site_id>
set -uo pipefail

site="${1:?нужен site_id}"
stage="$HOME/stage"
data="$stage/data/$site"
bundle="$stage/bundles/$site.bundle"
trial="$HOME/trial/$site"

echo "site=$site"
[ -d "$data" ] || { echo "error=нет данных $data"; exit 2; }
[ -f "$bundle" ] || { echo "error=нет бандла $bundle"; exit 2; }

python3 - "$data" "$site" <<'PY'
import json
import pathlib
import sys

data_dir, site = pathlib.Path(sys.argv[1]), sys.argv[2]
problems = []
rev = {}
for kind in ("catalog", "details"):
    path = data_dir / f"{site}-{kind}.json"
    if not path.is_file():
        problems.append(f"нет {path.name}")
        continue
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as err:
        problems.append(f"{path.name} не читается как JSON: {err}")
        continue
    if doc.get("site") != site:
        problems.append(f"{path.name}: site={doc.get('site')!r}, ожидался {site!r}")
    # Каталог несёт СПИСОК items, sidecar подробностей — СЛОВАРЬ details
    # (идентификатор → запись). Первая редакция ждала список у обоих и
    # объявляла правильный файл пустым.
    items = doc.get("items") if kind == "catalog" else doc.get("details")
    count = len(items) if isinstance(items, (list, dict)) else None
    declared = doc.get("items_total") if kind == "catalog" else doc.get("details_total")
    if isinstance(declared, int) and count is not None and declared != count:
        problems.append(f"{path.name}: объявлено {declared}, фактически {count}")
    if not count:
        problems.append(f"{path.name}: список пуст или отсутствует")
    rev[kind] = doc.get("catalog_revision") or doc.get("revision")
    print(f"{kind}_items={count} {kind}_revision={rev[kind]} "
          f"{kind}_mib={path.stat().st_size // 2**20}")
if rev.get("catalog") and rev.get("details") and rev["catalog"] != rev["details"]:
    problems.append(f"ревизии расходятся: каталог {rev['catalog']}, "
                    f"подробности {rev['details']}")
prov = data_dir / f"{site}-data-provenance.json"
if prov.is_file():
    p = json.loads(prov.read_text(encoding="utf-8"))
    print(f"provenance_donor={p.get('donor')} provenance_family={p.get('family')}")
else:
    problems.append("нет файла провенанса данных")
print(f"data_problems={len(problems)}")
for item in problems:
    print(f"   problem| {item}")
sys.exit(1 if problems else 0)
PY
data_rc=$?
echo "data_rc=$data_rc"

# Код: клон бандла и собственные проверки проекта. Клон в отдельный каталог,
# чтобы ничего не трогать в доставленном.
rm -rf "$trial/verify"
mkdir -p "$trial/verify"
if ! git clone --quiet "$bundle" "$trial/verify/src" 2>"$trial/verify/clone.log"; then
  echo "code_rc=1"
  echo "   problem| клон бандла не удался"
  exit 1
fi
echo "branch=$(git -C "$trial/verify/src" rev-parse --abbrev-ref HEAD)"
echo "head=$(git -C "$trial/verify/src" rev-parse --short=12 HEAD)"
echo "tracked_files=$(git -C "$trial/verify/src" ls-files | wc -l)"
out="$("$trial/verify/src/checks/run.sh" 2>&1)"
# Считаются только СТРОКИ ПРОВЕРОК («имя   PASS/FAIL»), а не любое вхождение
# слова: «ИТОГ: FAIL» внутри подробностей попадал в счёт отказов вторым разом.
pass=$(printf '%s\n' "$out" | grep -cE "^[a-z0-9][a-z0-9-]* +PASS$")
fail=$(printf '%s\n' "$out" | grep -cE "^[a-z0-9][a-z0-9-]* +FAIL$")
echo "checks_pass=$pass checks_fail=$fail"
printf '%s\n' "$out" | grep -E "^[a-z0-9][a-z0-9-]* +FAIL$" | sed 's/^/   fail| /'
printf '%s\n' "$out" | grep -A 1 "ЗАМЕЧАНИЕ" | head -2 | sed 's/^/   note| /'
rm -rf "$trial/verify"
[ "$data_rc" = 0 ] || exit 1
[ "$fail" = 0 ] || exit 3
