#!/usr/bin/env python3
"""Записать в очередь домена, ГДЕ его работа изолирована: копия и ветка.

Задание требует изолированных рабочих каталогов и веток для задач. Проверить
это можно только измерением: путь репозитория ячейки, его текущая ветка и то,
не делят ли два домена одну ветку. Инструмент измеряет и записывает, а
проверка в `tests/unit/test_domain_isolation.py` следит, чтобы изоляция не
разъехалась.

Что именно различается, и почему это важно:

* **репозиторий ячейки** — исходный код витрины. У восьми витрин K2 он ЕСТЬ
  локально (`var/new-sites/lords-1X`), хотя РАЗЛОЖЕННОГО выпуска локально нет:
  код работает на узле. Путать эти два факта нельзя — именно из-за путаницы
  я раньше написала «у K2 нет ни ветки, ни раскладки»;
* **ветка** — где ведётся работа. `HEAD` означает отсоединённое состояние:
  работа там не привязана ни к одной ветке, и её легко потерять.

    python3 automation/local/record-isolation.py
    python3 automation/local/record-isolation.py --dry-run
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СПИСОК = КОРЕНЬ / "config" / "active-domains.json"
ЯЧЕЙКИ = КОРЕНЬ / "config" / "site-cells.json"
ОЧЕРЕДИ = КОРЕНЬ / "config" / "domain-queues"
#: Копии, в которых разворачивается относительный путь репозитория ячейки.
#: Порядок важен: сначала копия-владелец выпусков семейств, потом своя.
БАЗЫ = (pathlib.Path("/home/claude/wt-portable-site-cell-01"), КОРЕНЬ)

ОТСОЕДИНЁН = "HEAD"


def теперь() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def ветка_копии(путь: pathlib.Path) -> str:
    if not (путь / ".git").exists():
        return ""
    г = subprocess.run(["git", "-C", str(путь), "rev-parse",
                        "--abbrev-ref", "HEAD"],
                       capture_output=True, text=True)
    return г.stdout.strip()


def изоляция(site_id: str, ячейки: dict) -> dict:
    """Где изолирована работа по ячейке. Возвращает измеренное, без догадок."""
    отн = ((ячейки.get(site_id) or {}).get("repo") or {}).get("path") or ""
    if not отн:
        return {"repo": "", "branch": "", "note": "путь репозитория ячейки не объявлен"}
    for база in БАЗЫ:
        п = база / отн
        if п.exists():
            в = ветка_копии(п)
            если_отсоединён = в == ОТСОЕДИНЁН
            return {
                "repo": str(п),
                "branch": в,
                "note": ("ОТСОЕДИНЁННЫЙ HEAD: работа не привязана к ветке и"
                         " может быть потеряна" if если_отсоединён else
                         "своя копия и своя ветка"),
            }
    return {"repo": отн, "branch": "",
            "note": f"каталог {отн} не найден ни в одной копии"}


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args(аргв)

    список = json.loads(СПИСОК.read_text(encoding="utf-8"))
    ячейки = {з["site_id"]: з for з in json.loads(
        ЯЧЕЙКИ.read_text(encoding="utf-8"))["cells"]}

    по_ветке: dict[str, list[str]] = {}
    отсоединённые = []
    for з in список["domains"]:
        и = изоляция(з["site_id"], ячейки)
        ф = ОЧЕРЕДИ / f"{з['domain']}.json"
        о = json.loads(ф.read_text(encoding="utf-8"))
        о["work"] = {**и, "measured_at": теперь()}
        if not а.dry_run:
            ф.write_text(json.dumps(о, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
        if и["branch"]:
            по_ветке.setdefault(и["branch"], []).append(з["domain"])
        if и["branch"] == ОТСОЕДИНЁН:
            отсоединённые.append(з["domain"])
        print(f"{з['domain']:24} {и['branch'] or '—':44} {и['note'][:40]}")

    общие = {в: д for в, д in по_ветке.items()
             if len(д) > 1 and в != ОТСОЕДИНЁН}
    print(f"\nдомéнов {len(список['domains'])};"
          f" со своей веткой {sum(1 for в in по_ветке for _ in по_ветке[в])};"
          f" отсоединённых {len(отсоединённые)}")
    if общие:
        print(f"ВЕТКУ ДЕЛЯТ НЕСКОЛЬКО ДОМÉНОВ: {общие}")
    else:
        print("общих веток нет: работа по домéнам изолирована")
    if отсоединённые:
        print(f"ОТСОЕДИНЁННЫЙ HEAD: {', '.join(отсоединённые)}"
              f" — работа там не привязана к ветке")
    return 1 if (общие or отсоединённые) else 0


if __name__ == "__main__":
    sys.exit(main())
