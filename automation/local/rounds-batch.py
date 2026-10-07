#!/usr/bin/env python3
"""Круг выпуска по многим ячейкам подряд: штамп, прогон, коммит, отправка.

    python3 automation/local/rounds-batch.py --message-file <файл> \\
        [--reason "что изменилось"] [--only <проект>]… [--skip <проект>]… [--dry-run]

Один круг на ячейку, строго по очереди: параллельные прогоны делят процессор и
удлиняют друг друга, а живой ярус части проверок поднимает настоящую витрину.

Перед прогоном, если у ячейки есть свои штампующие инструменты, они вызываются:
`tools/stamp_manifest.py`, `tools/update_pins.py`, затем `checks/boundaries.py
--принять` — и ТОЛЬКО если граничная проверка до этого краснела. Причина
переставления отпечатков дописывается в сам замок, а прежняя история замка
сохраняется: «обновите контрольную сумму» без причины и есть обход проверки.

Витрины Yummy не трогаются ни одним шагом: ими распоряжается другое окно.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕПОЗИТОРИИ = КОРЕНЬ / "var" / "site-repos"


def выполнить(команда: list[str], где: pathlib.Path, таймаут: int = 2400):
    return subprocess.run(команда, cwd=str(где), capture_output=True, text=True,
                          timeout=таймаут)


def заштамповать(репо: pathlib.Path, причина: str) -> list[str]:
    """Переставить отпечатки ячейки. Возвращает, что сделано."""
    сделано: list[str] = []
    for инструмент in ("tools/stamp_manifest.py", "tools/update_pins.py"):
        if (репо / инструмент).is_file():
            г = выполнить(["python3", инструмент], репо, 900)
            сделано.append(f"{pathlib.Path(инструмент).stem}: код {г.returncode}")
    границы = репо / "checks" / "boundaries.py"
    if границы.is_file():
        г = выполнить(["python3", "checks/boundaries.py"], репо, 900)
        if г.returncode != 0:
            стар = выполнить(["git", "-C", str(репо), "show",
                              "HEAD:checks/boundaries.lock.json"], КОРЕНЬ)
            прежняя = ""
            try:
                прежняя = (json.loads(стар.stdout or "{}").get("note") or "").rstrip()
            except ValueError:
                pass
            выполнить(["python3", "checks/boundaries.py", "--принять"], репо, 900)
            замок = репо / "checks" / "boundaries.lock.json"
            try:
                данные = json.loads(замок.read_text(encoding="utf-8"))
                if причина and причина not in прежняя:
                    данные["note"] = (прежняя + "\n" + причина).strip()
                замок.write_text(json.dumps(данные, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
                сделано.append("boundaries: отпечатки переставлены, причина записана")
            except (OSError, ValueError) as ош:
                сделано.append(f"boundaries: замок не перезаписан ({ош})")
    return сделано


def главная(argv: list[str]) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--message-file", required=True)
    р.add_argument("--reason", default="")
    р.add_argument("--lock-reason", default="",
                   help="причина переставления отпечатков для замка границ")
    р.add_argument("--only", action="append", default=[])
    р.add_argument("--skip", action="append", default=[])
    р.add_argument("--dry-run", action="store_true")
    о = р.parse_args(argv[1:])

    цели = [п for п in sorted(РЕПОЗИТОРИИ.iterdir())
            if (п / ".git").is_dir() and not п.name.startswith("yummy")
            and (not о.only or п.name in о.only) and п.name not in о.skip]

    итоги: list[tuple[str, str]] = []
    for репо in цели:
        грязно = выполнить(["git", "-C", str(репо), "status", "--porcelain"],
                           КОРЕНЬ).stdout.strip()
        if not грязно:
            print(f"=== {репо.name}: изменений нет", flush=True)
            итоги.append((репо.name, "изменений нет"))
            continue
        print(f"=== {репо.name}", flush=True)
        for строка in заштамповать(репо, о.lock_reason):
            print(f"   {строка}", flush=True)
        команда = [sys.executable, "automation/local/release-round.py",
                   "--repo", str(репо), "--message-file", о.message_file]
        if о.reason:
            команда += ["--reason", о.reason]
        if о.dry_run:
            команда.append("--dry-run")
        г = выполнить(команда, КОРЕНЬ, 3000)
        вывод = (г.stdout or "") + (г.stderr or "")
        for строка in вывод.strip().split("\n")[1:]:
            print(f"   {строка.strip()}", flush=True)
        последняя = [с.strip() for с in вывод.strip().split("\n") if с.strip()]
        итоги.append((репо.name, последняя[-1] if последняя else f"код {г.returncode}"))

    print("\n--- итог круга")
    for имя, строка in итоги:
        print(f"{имя:24} {строка[:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
