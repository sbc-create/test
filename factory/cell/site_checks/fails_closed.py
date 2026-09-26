"""Запуск отказывает, а не подставляет чужое."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

r = subprocess.run([sys.executable, str(ROOT / "run.py"), "--check"],
                   capture_output=True, text=True, cwd=ROOT)
if r.returncode == 0:
    print("запуск без --data-dir не отказал", file=sys.stderr)
    sys.exit(1)

cfg = json.loads((ROOT / "config" / "site.json").read_text(encoding="utf-8"))
if "neighbour_site_ids" not in cfg:
    print("в config/site.json нет поля neighbour_site_ids", file=sys.stderr)
    sys.exit(1)

# Отказ проверяется ИСПОЛНЕНИЕМ, а не наличием списка соседей.
#
# Раньше требовался непустой список — и у сайта, заведённого из шаблона, его
# взяться неоткуда: соседей на машине ещё нет. Но защита нужна ему ровно так
# же: умолчания рантайма этого семейства указывают на чужую ячейку, и одна
# незаданная переменная означала бы витрину, молча отдающую каталог соседа.
# Поэтому проверяется то, ради чего защита написана: запуск с каталогом
# данных ЧУЖОГО сайта обязан отказать.
чужой = cfg.get("neighbour_site_ids") or ["lords-01"]
подстава = f"/srv/{чужой[0]}/data"
if cfg["site_id"] in подстава:
    подстава = "/srv/chuzhoy-sayt/data"
r = subprocess.run([sys.executable, str(ROOT / "run.py"), "--check",
                    "--data-dir", подстава],
                   capture_output=True, text=True, cwd=ROOT)
if r.returncode == 0:
    print(f"запуск с чужим каталогом данных {подстава} не отказал", file=sys.stderr)
    sys.exit(1)
