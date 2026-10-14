#!/usr/bin/env python3
"""Заготовки для нового узла: юниты и конфигурации nginx восьми ячеек.

Зачем отдельный инструмент. На узле K2 у `k2deploy` нет sudo, а штатные
установщики (`install-cell-units.py`, `install-site-nginx.sh`) работают от root
и живут в репозитории управляющего узла. Чтобы ручные действия владельца
свелись к ОДНОМУ проверяемому блоку, файлы готовятся здесь, кладутся в домашний
каталог `k2deploy` обычной доставкой (без root), а блок владельца только
устанавливает их на место.

Шаблон юнита НЕ копируется: он импортируется из `install-cell-units.py`, иначе
две копии разойдутся, и узел получит юнит, которого фабрика не знает.

Ничего не устанавливается и не запускается: инструмент пишет только в
`var/k2-stage/` и считает SHA-256 каждого файла в опись.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

КОРЕНЬ = Path(__file__).resolve().parents[2]
ВЫХОД = КОРЕНЬ / "var" / "k2-stage"
ЗАГОТОВКИ_NGINX = КОРЕНЬ / "automation" / "host" / "nginx-site"
ВОСЕМЬ = tuple(f"lords-{n}" for n in range(10, 18))


def модуль_юнитов():
    путь = КОРЕНЬ / "automation" / "host" / "install-cell-units.py"
    spec = importlib.util.spec_from_file_location("install_cell_units", путь)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


def перечитывание_из_реестра() -> dict[str, str]:
    """site_id → `runtime.reload` прямо из реестра.

    Через `install-cell-units.ячейки()` это поле не приходит: оно ему не нужно.
    Брать его оттуда значило бы получать `None` у всех и не заметить этого.
    """
    данные = json.loads((КОРЕНЬ / "config" / "site-cells.json")
                        .read_text(encoding="utf-8"))
    итог: dict[str, str] = {}
    for c in данные.get("cells") or []:
        значение = (c.get("runtime") or {}).get("reload")
        if значение:
            итог[c["site_id"]] = str(значение)
    return итог


def сумма(путь: Path) -> str:
    return hashlib.sha256(путь.read_bytes()).hexdigest()


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--sites", default=",".join(ВОСЕМЬ),
                   help="список site_id через запятую")
    р.add_argument("--out", default=str(ВЫХОД))
    а = р.parse_args()

    нужны = [с.strip() for с in а.sites.split(",") if с.strip()]
    м = модуль_юнитов()
    по_id = {я["site_id"]: я for я in м.ячейки()}
    нет = [с for с in нужны if с not in по_id]
    if нет:
        print(f"ОТКАЗ: в реестре нет ячеек: {', '.join(нет)}", file=sys.stderr)
        return 2

    выход = Path(а.out)
    (выход / "units").mkdir(parents=True, exist_ok=True)
    (выход / "nginx").mkdir(parents=True, exist_ok=True)
    (выход / "cells").mkdir(parents=True, exist_ok=True)
    опись: dict[str, dict] = {"cells": {}}

    for site_id in нужны:
        я = по_id[site_id]
        файлы: list[str] = []
        пары = (
            (я["unit"], "current", я["port"]),
            (я["unit"].replace(".service", "-candidate.service"), "candidate",
             я["port"] + 1000),
        )
        for имя, каталог, порт in пары:
            тело = м.ШАБЛОН.format(домен=я["domain"], учётка=я["account"],
                                   каталог=каталог, порт=порт)
            п = выход / "units" / имя
            п.write_text(тело, encoding="utf-8")
            файлы.append(f"units/{имя}")
        for хвост in ("", "-tls"):
            источник = ЗАГОТОВКИ_NGINX / f"{site_id}{хвост}.conf"
            if not источник.is_file():
                print(f"ОТКАЗ: нет заготовки nginx {источник}", file=sys.stderr)
                return 2
            цель = выход / "nginx" / источник.name
            shutil.copy(источник, цель)
            файлы.append(f"nginx/{источник.name}")
        # Режим индексации приходит ВКЛЮЧАЕМЫМ ФАЙЛОМ, и новая витрина
        # рождается ЗАКРЫТОЙ: открытие — отдельное решение владельца и
        # отдельная операция. Тело берётся у фабрики, а не пишется руками.
        from factory.cell import nginx_indexing as ни

        роботы = выход / "cells" / f"{site_id}.robots"
        роботы.write_text(ни.тело_включаемого("CLOSED"), encoding="utf-8")
        файлы.append(f"cells/{роботы.name}")
        # Точка переключения трафика: содержимое меняет исполнитель при
        # выкладке, здесь только начальное значение.
        апстрим = выход / "cells" / f"{site_id}.upstream"
        апстрим.write_text(f"server 127.0.0.1:{я['port']};\n", encoding="utf-8")
        файлы.append(f"cells/{апстрим.name}")
        # Как витрина подхватывает новый снимок: `mtime` — сама, `restart` —
        # только перезапуском службы. Поле приходит из реестра; отсутствие
        # трактуется как `restart`, потому что устаревший каталог при живом
        # ответе 200 — это молчащая неправда, а лишний перезапуск — всего лишь
        # лишний перезапуск.
        перечитывание = (перечитывание_из_реестра().get(site_id) or "restart")
        опись["cells"][site_id] = {
            "domain": я["domain"], "account": я["account"], "port": я["port"],
            "unit": я["unit"], "reload": перечитывание,
            "files": {ф: сумма(выход / ф) for ф in файлы},
        }

    # Объявления upstream одним файлом: имя получается из site_id той же
    # заменой, что в install-site-nginx.sh (`tr '.-' '__'`).
    строки = ["# Объявления upstream ячеек узла K2. Содержимое include-файлов\n",
              "# меняет исполнитель при выкладке; здесь только объявления.\n"]
    for site_id in нужны:
        имя = "cell_" + site_id.replace(".", "_").replace("-", "_")
        строки.append(f"\nupstream {имя} {{\n"
                      f"    include /etc/nginx/cells/{site_id}.upstream;\n}}\n")
    апстримы = выход / "nginx" / "site-cells-upstreams.conf"
    апстримы.write_text("".join(строки), encoding="utf-8")
    опись["upstreams_file"] = {
        "nginx/site-cells-upstreams.conf": сумма(апстримы)}

    (выход / "MANIFEST.json").write_text(
        json.dumps(опись, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    всего = sum(len(c["files"]) for c in опись["cells"].values())
    print(f"ячеек: {len(опись['cells'])}; файлов: {всего}; опись: "
          f"{выход / 'MANIFEST.json'}")
    print("ни один файл не установлен и ни одна служба не включена")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
