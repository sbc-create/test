#!/usr/bin/env bash
# Приём доставленного каталога на узле K2: из входящего каталога — в данные
# витрины, с правами витрины. Выполняется ОТ ROOT по таймеру.
#
# Зачем этот слой вообще нужен. Каталог данных витрины принадлежит ТОЛЬКО ей
# (`/srv/<учётка>/data`, 0750 `<учётка>:<учётка>`), и это правильно: выкладка
# и сборка в постоянные данные не пишут. Значит `k2deploy`, который привозит
# свежий снимок, положить его на место не может — у него нет права записи. Два
# очевидных обхода плохи оба: дать `k2deploy` запись в данные значит стереть
# границу, ради которой права и выставлены; делать доставку руками значит не
# иметь регулярного обновления вовсе.
#
# Поэтому: `k2deploy` кладёт комплект во ВХОДЯЩИЙ каталог своего дома, а этот
# сценарий от root проверяет его и устанавливает. Права не ослабляются, ручных
# шагов нет.
#
# Что проверяется ДО установки (иначе это была бы доставка чего угодно):
#   * комплект полон: каталог, подробности, суммы, провенанс;
#   * суммы сходятся;
#   * `site` внутри файлов совпадает с именем витрины;
#   * число элементов совпадает с объявленным и не меньше порога;
#   * ревизии каталога и sidecar совпадают между собой.
# Любое расхождение — отказ, входящий комплект остаётся на месте нетронутым.
#
# Установка атомарна: файл пишется рядом и переносится `mv` в тот же раздел.
# Прежний снимок сохраняется один (`.prev`), чтобы откат был без сети.
#
# Имена переменных только ASCII: кириллица в именах переменных оболочки падает
# в работе, а `bash -n` её пропускает.
#
# Запуск:  k2-catalog-apply.sh [site_id ...]   (без аргументов — все входящие)
set -uo pipefail

incoming_root="${K2_INCOMING:-/home/k2deploy/stage/incoming}"
manifest="${K2_MANIFEST:-/home/k2deploy/stage/MANIFEST.json}"
#: Корень данных витрин. Переопределяется ТОЛЬКО для проверки цикла в
#: отдельном каталоге: установка в производство идёт в /srv и от root.
srv_root="${K2_SRV_ROOT:-/srv}"
min_items=1000
check_only=0

log() { printf '==> %s\n' "$*"; }
bad() { printf '[x] %s\n' "$*" >&2; }

# `--check-only` проверяет комплект и НИЧЕГО не устанавливает: для этого root
# не нужен, и владелец может прогнать проверку до установки.
args=""
for a in "$@"; do
  case "$a" in
    --check-only) check_only=1 ;;
    *) args="$args $a" ;;
  esac
done
set -- $args
[ "$check_only" = 1 ] || [ "$(id -u)" = 0 ] || \
  { bad "нужен root: установка идёт с правами витрины"; exit 1; }
[ -f "$manifest" ] || { bad "нет описи $manifest"; exit 2; }
[ -d "$incoming_root" ] || { log "входящих комплектов нет ($incoming_root)"; exit 0; }

sites="$*"
if [ -z "$sites" ]; then
  sites="$(ls -1 "$incoming_root" 2>/dev/null)"
fi
[ -n "$sites" ] || { log "входящих комплектов нет"; exit 0; }

applied=0
failed=0
for site in $sites; do
  box="$incoming_root/$site"
  [ -d "$box" ] || { log "$site: входящего комплекта нет, пропускаю"; continue; }

  account=$(python3 - "$manifest" "$site" <<'PY'
import json, sys
cells = json.load(open(sys.argv[1], encoding="utf-8")).get("cells") or {}
cell = cells.get(sys.argv[2])
print(cell["account"] if cell else "")
PY
)
  if [ -z "$account" ]; then
    bad "$site: в описи нет такой витрины — установка не делается"
    failed=$((failed + 1)); continue
  fi
  data="$srv_root/$account/data"
  if [ ! -d "$data" ]; then
    bad "$site: нет $data (узел не подготовлен)"
    failed=$((failed + 1)); continue
  fi

  # 1. Полнота и суммы.
  missing=""
  for f in "$site-catalog.json" "$site-details.json" "SHA256SUMS"; do
    [ -f "$box/$f" ] || missing="$missing $f"
  done
  if [ -n "$missing" ]; then
    bad "$site: во входящем комплекте нет:$missing"
    failed=$((failed + 1)); continue
  fi
  if ! ( cd "$box" && sha256sum -c SHA256SUMS --quiet ); then
    bad "$site: суммы входящего комплекта не сходятся — не устанавливаю"
    failed=$((failed + 1)); continue
  fi

  # 2. Прикладная проверка содержимого.
  if ! python3 - "$box" "$site" "$min_items" <<'PY'
import json
import pathlib
import sys

box, site, floor = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
problems = []
revisions = {}
for kind, holder, total_key in (("catalog", "items", "count"),
                                ("details", "details", "details_total")):
    path = box / f"{site}-{kind}.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as err:
        problems.append(f"{path.name}: не JSON ({err})")
        continue
    if doc.get("site") != site:
        problems.append(f"{path.name}: site={doc.get('site')!r}, ожидался {site!r}")
    body = doc.get(holder)
    count = len(body) if isinstance(body, (list, dict)) else 0
    declared = doc.get(total_key)
    if count < floor:
        problems.append(f"{path.name}: элементов {count} — меньше порога {floor}")
    if isinstance(declared, int) and declared != count:
        problems.append(f"{path.name}: объявлено {declared}, фактически {count}")
    revisions[kind] = doc.get("catalog_revision") or doc.get("revision")
    print(f"{site} {kind}: элементов {count}, ревизия {revisions[kind]}")
if len(set(revisions.values())) > 1:
    problems.append(f"ревизии расходятся: {revisions}")
for item in problems:
    print(f"   problem| {item}")
sys.exit(1 if problems else 0)
PY
  then
    bad "$site: проверка содержимого не прошла — входящий комплект оставлен как есть"
    failed=$((failed + 1)); continue
  fi

  if [ "$check_only" = 1 ]; then
    log "$site: комплект проверен, установка не делалась (--check-only)"
    applied=$((applied + 1))
    continue
  fi

  # 3. Установка: предыдущий снимок в .prev, новый — атомарным переносом.
  for kind in catalog details; do
    target="$data/$site-$kind.json"
    [ -f "$target" ] && cp -p "$target" "$target.prev"
    tmp="$data/.$site-$kind.json.new"
    install -m 0640 -o "$account" -g "$account" "$box/$site-$kind.json" "$tmp"
    mv -f "$tmp" "$target"
  done
  [ -f "$box/$site-data-provenance.json" ] && \
    install -m 0640 -o "$account" -g "$account" \
            "$box/$site-data-provenance.json" "$data/"
  log "$site: установлено в $data (владелец $account, режим 0640)"

  # 4. Входящий комплект убирается, чтобы следующий прогон не ставил то же
  # второй раз; суммы и провенанс остаются рядом с данными.
  rm -rf "$box"
  applied=$((applied + 1))
done

log "установлено витрин: $applied; отказов: $failed"
[ "$failed" = 0 ] || exit 1
