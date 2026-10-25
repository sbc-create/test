#!/usr/bin/env python3
"""Какой publisher_id фактически отдаёт плеер каждой витрины K2.

Назначение владельца для партии K2 — 10454, и оно обязано пережить любой
выпуск: сценарий выпуска переносит `config/player.json` из прежнего выпуска, а
не берёт его из git (в git его нет намеренно). Проверка смотрит на ПУБЛИЧНУЮ
страницу произведения: там номер попадает в разметку плеера, и это
единственное место, где видно то же, что и посетителю.

Номер не секрет (он назван в решении владельца и в журнале выпусков), но и не
подставляется: если его на странице нет, печатается «не найден», а не
ожидаемое значение.

    python3 automation/local/k2-publisher-id-check.py [ожидаемый]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

АГЕНТ = "factory-k2-publisher-id-check"

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
def _витрины_узла(ref: str = "k2-zomro-01") -> list[str]:
    """Состав узла из реестра — одним модулем на всю фабрику (класс 47)."""
    import importlib.util

    путь = КОРЕНЬ / "automation" / "local" / "node-cell-list.py"
    сп = importlib.util.spec_from_file_location("node_cell_list", путь)
    м = importlib.util.module_from_spec(сп)
    сп.loader.exec_module(м)
    return list(м.витрины_узла(ref))


#: Витрины узла. Ячейка без назначенного номера обязана попадать в проверку:
#: именно её отсутствие в перечне и прятало бы незаполненный вход владельца.
K2 = _витрины_узла()
ОБРАЗЦЫ = (re.compile(r'data-publisher(?:-id)?="(\d{3,6})"'),
           re.compile(r'[?&]publisher_id=(\d{3,6})'),
           re.compile(r'"publisher_id"\s*:\s*"?(\d{3,6})'),
           re.compile(r'/(\d{4,6})/iframe'))


def домены() -> dict[str, str]:
    j = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    ячейки = j.get("cells") or []
    записи = ячейки.values() if isinstance(ячейки, dict) else ячейки
    return {з["site_id"]: з["domain"] for з in записи
            if isinstance(з, dict) and з.get("site_id") and з.get("domain")}


def первый_тайтл(домен: str) -> str:
    html = subprocess.run(["curl", "-A", АГЕНТ, "-sS", "--max-time", "60",
                           f"https://{домен}/"],
                          capture_output=True, text=True).stdout or ""
    м = re.search(r'href="(/title/[^"]+)"', html)
    return м.group(1) if м else ""


def по_витрине(пара: tuple[str, str]) -> dict:
    site_id, домен = пара
    путь = первый_тайтл(домен)
    if not путь:
        return {"site_id": site_id, "домен": домен, "id": None,
                "почему": "на главной нет ссылок на произведения"}
    html = subprocess.run(["curl", "-A", АГЕНТ, "-sS", "--max-time", "60",
                           f"https://{домен}{путь}"],
                          capture_output=True, text=True).stdout or ""
    for образец in ОБРАЗЦЫ:
        м = образец.search(html)
        if м:
            return {"site_id": site_id, "домен": домен, "id": м.group(1),
                    "страница": путь}
    return {"site_id": site_id, "домен": домен, "id": None,
            "почему": "номер в разметке страницы не найден", "страница": путь}


def главная(аргв: list[str]) -> int:
    ожидаемый = аргв[0] if аргв else "10454"
    все = домены()
    пары = [(с, все[с]) for с in K2 if с in все]
    with ThreadPoolExecutor(max_workers=4) as пул:
        итоги = list(пул.map(по_витрине, пары))
    плохо = 0
    for и in итоги:
        если = и["id"]
        метка = " " if если == ожидаемый else "✗"
        плохо += если != ожидаемый
        print(f"{метка} {и['site_id']:9} {и['домен']:20} "
              f"{если or и.get('почему')}")
    print(f"\nожидался {ожидаемый}; расхождений: {плохо} из {len(итоги)}")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(главная(sys.argv[1:]))
