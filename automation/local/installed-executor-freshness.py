#!/usr/bin/env python3
"""Тот ли код у установленного исполнителя ячеек, что в дереве. Только чтение.

Операции над ячейками (`factory cell …`, прогрев, выпуск, активация) исполняет
НЕ наше рабочее дерево, а установленная копия
`/usr/local/lib/site-factory-cell`. Про процессы у нас уже есть проверка
(`service-code-freshness.py`: запущен раньше, чем правлен файл). Про
установленную копию её не было, и 19.10 это стоило разбора: правка прогрева
лежала в ветке, установленная копия была от 10.10, и повтор активации пошёл бы
по старому коду.

Что печатается: откуда копия поставлена и когда (`cell-install.json`), сколько
файлов совпадает, сколько различается, сколько есть только в одном из деревьев.
Различия перечисляются по именам — по ним видно, чего именно нет у исполнителя.

Третий исход обязателен: нет установленной копии или нет источника — «не
измерено» с причиной, а не «всё совпадает».

    python3 automation/local/installed-executor-freshness.py
    python3 automation/local/installed-executor-freshness.py --tree /path/to/worktree
    python3 automation/local/installed-executor-freshness.py --json

Коды: 0 — различий нет; 1 — есть различия; 2 — не измерено.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

УСТАНОВЛЕННАЯ = pathlib.Path("/usr/local/lib/site-factory-cell")
#: Что сравнивать: код, который исполняет операции ячеек. Данные и журналы
#: установленной копии (var/, artifacts/) намеренно не сравниваются — они
#: принадлежат исполнителю и в дереве их нет.
ПОДДЕРЕВЬЯ = ("factory", "schemas")


def цифра(п: pathlib.Path) -> str:
    return hashlib.sha256(п.read_bytes()).hexdigest()


def собрать(корень: pathlib.Path) -> dict[str, str]:
    итог: dict[str, str] = {}
    for поддерево in ПОДДЕРЕВЬЯ:
        основа = корень / поддерево
        if not основа.is_dir():
            continue
        for п in основа.rglob("*"):
            if not п.is_file() or "__pycache__" in п.parts:
                continue
            if п.suffix in (".pyc", ".pyo"):
                continue
            try:
                итог[str(п.relative_to(корень))] = цифра(п)
            except OSError:
                continue
    return итог


def происхождение(установлена: pathlib.Path) -> dict:
    п = установлена / "cell-install.json"
    try:
        return json.loads(п.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def сверить(установлена: pathlib.Path, дерево: pathlib.Path) -> dict:
    if not установлена.is_dir():
        return {"измерено": False, "почему": f"нет установленной копии {установлена}"}
    if not дерево.is_dir():
        return {"измерено": False, "почему": f"нет дерева источника {дерево}"}
    у = собрать(установлена)
    д = собрать(дерево)
    if not у:
        return {"измерено": False,
                "почему": f"в установленной копии нет файлов {ПОДДЕРЕВЬЯ}"}
    общие = sorted(set(у) & set(д))
    различия = [к for к in общие if у[к] != д[к]]
    только_установлено = sorted(set(у) - set(д))
    только_в_дереве = sorted(set(д) - set(у))
    пр = происхождение(установлена)
    return {
        "измерено": True,
        "установлена_из": пр.get("code_source") or "не записано",
        "установлена_когда": пр.get("installed_at") or "не записано",
        "пакет": пр.get("package_commit") or "без пакета (прямая установка)",
        "файлов_установлено": len(у),
        "файлов_в_дереве": len(д),
        "совпадает": len(общие) - len(различия),
        "различается": различия,
        "только_установлено": только_установлено,
        "только_в_дереве": только_в_дереве,
    }


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="код установленного исполнителя против дерева")
    р.add_argument("--installed", default=str(УСТАНОВЛЕННАЯ))
    р.add_argument("--tree", default="", help="по умолчанию — дерево из cell-install.json")
    р.add_argument("--json", action="store_true")
    р.add_argument("--limit", type=int, default=12, help="сколько имён печатать")
    дов = р.parse_args(аргв)

    установлена = pathlib.Path(дов.installed)
    дерево = pathlib.Path(дов.tree) if дов.tree else pathlib.Path(
        происхождение(установлена).get("code_source") or ".")
    и = сверить(установлена, дерево)

    if дов.json:
        print(json.dumps({**и, "дерево": str(дерево)}, ensure_ascii=False, indent=2))
        return 0 if и.get("измерено") and not и["различается"] and not и["только_в_дереве"] else (
            2 if not и.get("измерено") else 1)

    if not и["измерено"]:
        print(f"НЕ ИЗМЕРЕНО: {и['почему']}")
        return 2
    print(f"установленная копия: {установлена}")
    print(f"   поставлена из {и['установлена_из']} в {и['установлена_когда']};"
          f" пакет: {и['пакет']}")
    print(f"   сравнение с деревом {дерево}")
    print(f"   файлов: установлено {и['файлов_установлено']},"
          f" в дереве {и['файлов_в_дереве']}, совпадает {и['совпадает']}")
    for имя, список in (("различается", и["различается"]),
                        ("только у исполнителя", и["только_установлено"]),
                        ("только в дереве", и["только_в_дереве"])):
        print(f"   {имя}: {len(список)}")
        for к in список[:дов.limit]:
            print(f"      {к}")
        if len(список) > дов.limit:
            print(f"      … и ещё {len(список) - дов.limit}")
    расхождений = len(и["различается"]) + len(и["только_в_дереве"])
    print()
    if расхождений:
        print(f"расхождений {расхождений}: операции ячеек идут по ДРУГОМУ коду, "
              "чем в дереве. Обновление — automation/host/install-executor-narrow.sh "
              "(нужен root).")
    else:
        print("расхождений нет: исполнитель исполняет тот же код, что в дереве.")
    return 1 if расхождений else 0


if __name__ == "__main__":
    sys.exit(main())
