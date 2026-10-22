#!/usr/bin/env python3
"""Какие опыты сети ДЕЙСТВУЮТ сейчас и чего из-за них нельзя. Только чтение.

ЗАЧЕМ. Задача, выросшая из исследования, может повторять гипотезу уже
идущего опыта — и тогда её исполнение нарушает правило канарейки: до
заслуженного вердикта гипотеза на другие домены не переносится. Измерено на
себе 22.10: я завела две такие задачи (серии в карте Animedia и страница
онгоингов), потому что реестр опытов В МОЕЙ копии содержит только
демонстрационный прогон, а действующие опыты живут в копии владельца
регулярного цикла. Это тот же корень, что у MOD-137: расхождение копий.

Поэтому инструмент читает реестр ТОЙ копии, которая объявлена владельцем в
`config/active-domains.json`, и печатает действующие опыты с канарейкой и
сроком вердикта. Своего реестра он не правит и ничего не публикует.

    python3 automation/local/running-experiments.py
    python3 automation/local/running-experiments.py --json

Коды: 0 — реестр прочитан; 2 — не прочитан (тогда задачу по гипотезе,
похожей на опыт, НЕ создавать: проверить нечем).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СПИСОК = КОРЕНЬ / "config" / "active-domains.json"
КОПИИ = pathlib.Path("/home/claude")
#: Фазы, при которых опыт ещё НЕ завершён и правило канарейки действует.
ДЕЙСТВУЮТ = ("planned", "canary", "observing", "running", "widening")


def владелец_опытов() -> str:
    """Чья копия ведёт реестр опытов. Берётся из объявления, не из догадки."""
    д = json.loads(СПИСОК.read_text(encoding="utf-8"))
    общие = д.get("shared_components") or {}
    запись = общие.get("experiments") or общие.get("regular_cycle") or {}
    return str(запись.get("owner") or "")


def реестры() -> list[pathlib.Path]:
    """Свой реестр и реестр копии-владельца. Порядок: владелец важнее."""
    пути = []
    хозяин = владелец_опытов()
    if хозяин:
        пути.append(КОПИИ / хозяин / "config" / "experiments.json")
    пути.append(КОРЕНЬ / "config" / "experiments.json")
    return [п for п in пути if п.is_file()]


def прочитать(путь: pathlib.Path) -> list[dict]:
    д = json.loads(путь.read_text(encoding="utf-8"))
    записи = д.get("experiments") if isinstance(д, dict) else д
    return list(записи or [])


def действующие(записи: list[dict]) -> list[dict]:
    """Опыты, по которым вердикта ещё нет. Чистая функция."""
    итог = []
    for з in записи:
        if з.get("synthetic"):
            continue
        фаза = str(з.get("phase") or z_ст(з) or "")
        если_вердикт = з.get("verdict")
        if если_вердикт in (None, "", "pending") or фаза in ДЕЙСТВУЮТ:
            итог.append(з)
    return итог


def z_ст(з: dict) -> str:
    return str(з.get("status") or "")


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    пути = реестры()
    if not пути:
        print("реестр опытов не прочитан ни в одной копии:"
              " задачу по гипотезе, похожей на опыт, НЕ создавать —"
              " проверить нечем", file=sys.stderr)
        return 2

    итог = []
    for п in пути:
        try:
            записи = прочитать(п)
        except ValueError as e:
            print(f"{п}: не разобран ({e})", file=sys.stderr)
            continue
        дей = действующие(записи)
        итог.append({"реестр": str(п), "всего": len(записи),
                     "действующих": len(дей), "опыты": дей})

    if а.json:
        print(json.dumps(итог, ensure_ascii=False, indent=1))
        return 0

    print(f"владелец реестра опытов по объявлению: {владелец_опытов() or '—'}")
    for и in итог:
        своя = и["реестр"].startswith(str(КОРЕНЬ))
        print(f"\n{'СВОЯ копия' if своя else 'копия ВЛАДЕЛЬЦА'}:"
              f" {и['реестр']}")
        print(f"   записей {и['всего']}, действующих {и['действующих']}")
        for з in и["опыты"]:
            срок = (з.get("verdict_due") or з.get("decision_due")
                    or з.get("observation_until") or "срок не назван")
            канарейка = (з.get("canary") or з.get("site_id")
                         or "канарейка не названа")
            print(f"      {з.get('experiment_id') or з.get('id') or '?'}"
                  f" | канарейка {канарейка} | вердикт {срок}")
            гип = str(з.get("hypothesis") or "")
            if гип:
                print(f"         гипотеза: {гип[:110]}")
    print("\nПРАВИЛО: до заслуженного вердикта гипотеза действующего опыта на"
          " другие домены НЕ переносится. Задача из исследования, повторяющая"
          " такую гипотезу, ставится как «заблокировано до вердикта».")
    return 0


if __name__ == "__main__":
    sys.exit(main())
