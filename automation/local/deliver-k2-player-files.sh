#!/usr/bin/env bash
# Файлы плеера восьми витрин K2 — в место, которое ждёт сценарий запуска.
#
# Где их ждут. `automation/host/k2-launch-site.sh` (root, на узле) берёт файл по
# пути `$HOME/stage/player/<site>-player.json` и ставит его в выпуск как
# `config/player.json` с правами 0640 и владельцем витрины. Путь в домашнем
# каталоге выбран намеренно: доставка туда root не требует, а установка в
# `/srv/<витрина>/` — требует, и это разные операции.
#
# Что проверяется ДО доставки: номер берётся из учёта реестра ячеек и
# сверяется с объявлением пакета витрины (`config/site.json`,
# `publisher_id_expected`). Расхождение — отказ: подставлять одно из двух
# значений инструмент не вправе (D177, D214).
#
# Что проверяется ПОСЛЕ доставки: файл на узле читается как JSON, и номер в нём
# совпадает с учётом. Сумма доказывает, что байты доехали, а разбор — что
# доехал файл плеера, а не что-нибудь другого размера.
#
# Значение публично по устройству (атрибут `data-publisher-id`, D89/D138), но в
# вывод не печатается: привычка не печатать номер дешевле разбирательства,
# какой из номеров где можно показывать.
#
# Имена переменных только ASCII: кириллица в именах переменных оболочки падает
# в работе, а `bash -n` её пропускает.
#
# Запуск:  deliver-k2-player-files.sh <site_id> [site_id ...]
set -uo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root" || exit 1
inventory="var/ansible/hosts.yml"
host_ref="k2-zomro-01"
work="var/k2-data/player"
mkdir -p "$work"

[ -f "$inventory" ] || { echo "нет инвентаря $inventory" >&2; exit 2; }
[ "$#" -gt 0 ] || { echo "нужен хотя бы один site_id" >&2; exit 2; }

ok=0
bad=0
for site in "$@"; do
  number="$(python3 - "$site" <<'PY'
import json, pathlib, sys
site = sys.argv[1]
корень = pathlib.Path(".")
реестр = json.loads((корень / "config" / "site-cells.json").read_text(encoding="utf-8"))
ячейка = next((c for c in реестр["cells"] if c["site_id"] == site), None)
if ячейка is None:
    print("ОТКАЗ:нет такой ячейки в реестре")
    raise SystemExit(0)
учёт = str((ячейка.get("publisher") or {}).get("publisher_id") or "").strip()
путь = str((ячейка.get("repo") or {}).get("path") or "").strip()
if not учёт:
    print("ОТКАЗ:в учёте реестра нет publisher_id")
    raise SystemExit(0)
конфиг = корень / путь / "config" / "site.json"
объявлено = ""
if конфиг.is_file():
    объявлено = str(json.loads(конфиг.read_text(encoding="utf-8"))
                    .get("publisher_id_expected") or "").strip()
if объявлено != учёт:
    print("ОТКАЗ:учёт и объявление пакета расходятся")
    raise SystemExit(0)
if not учёт.isdigit() or учёт.startswith("0"):
    print("ОТКАЗ:номер в учёте непригоден")
    raise SystemExit(0)
print(учёт)
PY
)"
  case "$number" in
    ОТКАЗ:*)
      echo "[x] $site: ${number#ОТКАЗ:}"
      bad=$((bad + 1))
      continue
      ;;
  esac

  file="$work/$site-player.json"
  printf '{\n  "publisher_id": "%s",\n  "source_mode": "provider-id",\n  "_note": "значение витрины; ставится в выпуск сценарием k2-launch-site.sh"\n}\n' \
    "$number" > "$file"
  chmod 0600 "$file"

  if ! ansible -i "$inventory" "$host_ref" -m file \
        -a "path=/home/k2deploy/stage/player state=directory mode=0750" >/dev/null; then
    echo "[x] $site: каталог плееров на узле не создан"
    bad=$((bad + 1))
    continue
  fi
  if ! ansible -i "$inventory" "$host_ref" -m copy \
        -a "src=$file dest=/home/k2deploy/stage/player/$site-player.json mode=0600" \
        >/dev/null; then
    echo "[x] $site: доставка не удалась"
    bad=$((bad + 1))
    continue
  fi

  # Проверка на узле: разбор и совпадение номера, без печати значения.
  check="$(ansible -i "$inventory" "$host_ref" -m shell -a "
    python3 -c \"
import json,sys
loaded=json.load(open('/home/k2deploy/stage/player/$site-player.json',encoding='utf-8'))
print('match' if str(loaded.get('publisher_id'))=='$number' else 'mismatch',
      loaded.get('source_mode'))
\"" 2>/dev/null | tail -1)"
  case "$check" in
    "match provider-id")
      echo "[v] $site: файл плеера на узле, номер сходится с учётом"
      ok=$((ok + 1))
      ;;
    *)
      echo "[x] $site: на узле не подтвердилось ($check)"
      bad=$((bad + 1))
      ;;
  esac
done

echo "итог: доставлено $ok, отказов $bad"
[ "$bad" = 0 ]
