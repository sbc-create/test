#!/usr/bin/env python3
"""Все имена одной ячейки рядом: угадывать одно по другому нельзя.

Зачем это существует. У ячейки пять имён: `site_id`, домен, каталог рабочей
копии, системная учётная запись и unit службы. У 20 ячеек из 21 каталог и
учётная запись совпадают — и ровно поэтому одна остаётся ловушкой:

    lords-03   каталог var/site-repos/1lordserials1-online
               учётная запись  site-1lordserials1-online
               unit            nova-1lordserials1-online.service

То есть префикс `site-` есть у учётной записи и каталога `/srv`, но нет ни у
каталога рабочей копии, ни у unit. Измерено 13.10: вывод, где видно имя учётной
записи, заставил искать рабочую копию в `site-1lordserials1-online` — такого
каталога нет, и из этого вышло ложное утверждение «цифру ядра подтвердить не
могу». Соглашение, верное в 20 случаях из 21, опаснее отсутствия соглашения:
исключение не выглядит исключением.

Инструмент только читает: паспорт ячеек и файловую систему. Он называет
расхождение, а НЕ приводит имена к одному виду: переименование учётной записи и
unit — необратимая операция на живой витрине, и решает её владелец.

    python3 automation/local/cell-name-map.py
    python3 automation/local/cell-name-map.py --site lords-03
    python3 automation/local/cell-name-map.py --check   # код 1 на расхождении
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ПАСПОРТ = Path("/home/claude/wt-portable-site-cell-01/config/site-cells.json")
КОПИИ = Path("/home/claude/wt-portable-site-cell-01")
ЮНИТЫ = Path("/etc/systemd/system")
УЧЁТКИ = Path("/srv")


def имена(я: dict) -> dict[str, str]:
    р = (я.get("repo") or {}).get("path") or ""
    рт = я.get("runtime") or {}
    unit = str(рт.get("unit") or "")
    return {
        "site_id": str(я.get("site_id") or ""),
        "домен": str(я.get("domain") or ""),
        "копия": р.rsplit("/", 1)[-1] if р else "",
        "учётка": str(рт.get("account") or ""),
        "unit": unit,
        # Суффикс unit — то, чем unit отличается от соглашения `nova-<имя>.service`.
        "суффикс_unit": unit[len("nova-"):-len(".service")]
        if unit.startswith("nova-") and unit.endswith(".service") else "",
        "каталог_приложения": str(рт.get("app_dir") or ""),
    }


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--site", default=None)
    р.add_argument("--check", action="store_true",
                   help="код 1, если имена ячейки расходятся между собой")
    # Путь паспорта нужен флагом, а не вшитым: иначе `--check` нечем проверить,
    # а проверка, которая не может провалиться, доверия не несёт (D205).
    р.add_argument("--registry", type=Path, default=ПАСПОРТ,
                   help="путь к паспорту ячеек")
    а = р.parse_args()

    if not а.registry.is_file():
        print(f"паспорта ячеек нет: {а.registry} — НЕ ИЗМЕРЕНО")
        return 2
    ячейки = json.loads(а.registry.read_text(encoding="utf-8")).get("cells") or []

    расхождения: list[tuple[str, str]] = []
    print(f"{'site_id':12} {'домен':24} {'копия':26} {'учётка':28} unit-суффикс")
    for я in ячейки:
        н = имена(я)
        if а.site and н["site_id"] != а.site:
            continue
        if not н["копия"] and not н["учётка"]:
            continue
        разные = {з for з in (н["копия"], н["учётка"], н["суффикс_unit"]) if з}
        метка = "" if len(разные) <= 1 else "   <-- ИМЕНА РАЗНЫЕ"
        if метка:
            расхождения.append((н["site_id"], ", ".join(sorted(разные))))
        print(f"{н['site_id']:12} {н['домен']:24} {н['копия']:26} "
              f"{н['учётка']:28} {н['суффикс_unit']}{метка}")

    # Соглашение проверяется не по себе, а по диску: имя, которого на диске нет,
    # соглашением не оправдывается.
    print()
    for я in ячейки:
        н = имена(я)
        if а.site and н["site_id"] != а.site:
            continue
        if not н["копия"]:
            continue
        копия = КОПИИ / "var" / "site-repos" / н["копия"]
        прил = Path(н["каталог_приложения"]) if н["каталог_приложения"] else None
        unit = ЮНИТЫ / н["unit"] if н["unit"] else None
        нет = []
        if not копия.is_dir():
            нет.append(f"рабочей копии {копия} нет")
        if прил is not None and not прил.is_dir():
            нет.append(f"каталога приложения {прил} нет")
        if unit is not None and not unit.is_file():
            нет.append(f"unit-файла {unit} нет")
        if нет:
            print(f"{н['site_id']:12} " + "; ".join(нет))

    if расхождения:
        print(f"\nячеек с разными именами: {len(расхождения)}")
        for site_id, какие in расхождения:
            print(f"  {site_id}: {какие}")
        print("Имена НЕ приводятся к одному виду этим инструментом: "
              "переименование учётной записи и unit — необратимая операция на "
              "живой витрине, и это вход владельца.")
    else:
        print("\nимена ячеек согласованы между собой")
    return 1 if (а.check and расхождения) else 0


if __name__ == "__main__":
    sys.exit(main())
