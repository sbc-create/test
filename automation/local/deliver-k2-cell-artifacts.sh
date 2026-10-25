#!/usr/bin/env bash
# Доставка заготовок ячеек на узел K2: юниты, конфигурации nginx, включаемые
# файлы режима индексации и точки upstream — в домашний каталог k2deploy, без
# root. Ничего не устанавливается и не включается: установка на место — блок
# владельца.
#
# Почему не `copy` всего каталога заготовок. Общий файл объявлений
# `site-cells-upstreams.conf` один на узел, и заготовка, собранная только под
# новые ячейки, объявляет ТОЛЬКО их: установка такого файла сняла бы upstream'ы
# действующих витрин, то есть положила бы работающие сайты. Поэтому файл
# требуется собранным на ВЕСЬ состав узла, и это здесь проверяется, а не
# предполагается. Опись узла по той же причине сливается, а не заменяется.
#
# Имена переменных только ASCII: кириллица в именах переменных оболочки падает
# в работе, а `bash -n` её пропускает.
#
# Запуск:  deliver-k2-cell-artifacts.sh <site_id[,site_id...]> [каталог_заготовок]
set -uo pipefail

sites="${1:?нужны site_id через запятую}"
stage_dir="${2:-var/k2-stage-13}"
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
host_ref="k2-zomro-01"
inventory="$repo_root/var/ansible/hosts.yml"
remote="/home/k2deploy/stage"
work="${TMPDIR:-/tmp}/k2-deliver-$$"

cd "$repo_root" || exit 1
mkdir -p "$work"
trap 'rm -rf "$work"' EXIT

echo "==> 1. опись узла"
ansible -i "$inventory" "$host_ref" -m slurp -a "src=$remote/MANIFEST.json" 2>/dev/null \
  | python3 -c '
import sys, json, base64, pathlib
t = sys.stdin.read(); t = t[t.index("{"):]
pathlib.Path(sys.argv[1]).write_bytes(base64.b64decode(json.loads(t)["content"]))' "$work/node.json" \
  || { echo "опись узла не прочитана"; exit 1; }

python3 - "$work" "$stage_dir" "$sites" <<'PY' || exit 1
import json, pathlib, sys

work, stage_dir, sites = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3].split(",")
узел = json.loads((work / "node.json").read_text(encoding="utf-8"))
заготовка = json.loads((stage_dir / "MANIFEST.json").read_text(encoding="utf-8"))

нет = [s for s in sites if s not in заготовка["cells"]]
if нет:
    sys.exit(f"ОТКАЗ: в заготовке нет ячеек: {', '.join(нет)}")

# Общий файл объявлений обязан покрывать ВЕСЬ состав узла после доставки.
будет = set(узел["cells"]) | set(sites)
покрыто = set(заготовка["cells"])
если_нет = будет - покрыто
if если_нет:
    sys.exit("ОТКАЗ: общий site-cells-upstreams.conf собран без ячеек "
             f"{', '.join(sorted(если_нет))}; установка сняла бы их upstream. "
             "Собери заготовку на весь состав узла (--sites со всеми).")

# Прежние записи переносятся дословно: доставка добавляет, а не правит.
слито = {"cells": dict(узел["cells"]), "upstreams_file": заготовка["upstreams_file"]}
for s in sites:
    слито["cells"][s] = заготовка["cells"][s]
assert all(слито["cells"][s] == узел["cells"][s] for s in узел["cells"] if s not in sites)

(work / "MANIFEST.json").write_text(
    json.dumps(слито, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

# Перечень доставляемого и суммы — только названные ячейки плюс общий файл.
пути = []
for s in sites:
    пути.extend(заготовка["cells"][s]["files"])
пути.extend(заготовка["upstreams_file"])
(work / "paths").write_text("\n".join(пути) + "\n", encoding="utf-8")
суммы = {**{ф: с for s in sites for ф, с in заготовка["cells"][s]["files"].items()},
         **заготовка["upstreams_file"]}
(work / "sums").write_text("".join(f"{с}  {ф}\n" for ф, с in sorted(суммы.items())),
                           encoding="utf-8")
print(f"   ячеек на узле было {len(узел['cells'])}, станет {len(слито['cells'])};"
       f" файлов к доставке {len(пути)}")
PY

echo "==> 2. доставка файлов"
while read -r rel; do
  [ -n "$rel" ] || continue
  ansible -i "$inventory" "$host_ref" -m copy \
    -a "src=$stage_dir/$rel dest=$remote/$rel mode=0644" >/dev/null \
    || { echo "не доставлен: $rel"; exit 1; }
done < "$work/paths"
ansible -i "$inventory" "$host_ref" -m copy \
  -a "src=$work/sums dest=$remote/new-cells.sha256 mode=0644" >/dev/null || exit 1

echo "==> 3. сверка сумм НА УЗЛЕ"
out="$(ansible -i "$inventory" "$host_ref" -m raw \
      -a "cd $remote; sha256sum -c new-cells.sha256; echo rc=\$?" 2>&1)"
printf '%s\n' "$out" | grep -cE ': OK' | sed 's/^/   файлов OK: /'
printf '%s\n' "$out" | grep -E 'FAILED|rc=' | sed 's/^/   /'
printf '%s\n' "$out" | grep -q "rc=0" || { echo "СВЕРКА НЕ ПРОШЛА: опись НЕ обновляю"; exit 1; }

echo "==> 4. опись узла (сливается только после сверки файлов)"
ansible -i "$inventory" "$host_ref" -m copy \
  -a "src=$work/MANIFEST.json dest=$remote/MANIFEST.json mode=0644" >/dev/null || exit 1

echo "==> 5. проверка описи на узле"
ansible -i "$inventory" "$host_ref" -m raw \
  -a "python3 -c \"import json;o=json.load(open('$remote/MANIFEST.json'));print('ячеек',len(o['cells']),sorted(o['cells']))\"" 2>/dev/null \
  | grep -v "^k2-" | sed 's/^/   /'
echo "готово: $sites"
echo "ни один файл НЕ установлен на место и ни одна служба НЕ включена"
