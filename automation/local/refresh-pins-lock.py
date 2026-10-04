#!/usr/bin/env python3
"""Пересчёт замка версий репозитория сайта после правки общего рантайма.

Зачем общий инструмент, а не правка руками в каждом репозитории
---------------------------------------------------------------
Перенос читателя режима индексации в семейство Lords изменил `src/
lords-frontend.py` в пяти репозиториях, а `pins.lock.json` остался прежним.
Сторож плавающей версии (`checks/verify_pins.py`) сработал правильно и уронил
CI — измерено 2026-10-04 на четырёх репозиториях сразу:

    lordfilm47.space      sha256 b6e15353bc94 вместо 86794eb6d867
    lordserial33.biz      sha256 0fec91ac1441 вместо 86794eb6d867
    1lordserials1.online  sha256 0fec91ac1441 вместо 86794eb6d867
    zonafilm12.site       sha256 2a95bd7d29e8 вместо df99fb9628a0

Один и тот же дефект в четырёх местах правится одним инструментом, а не
четырьмя заплатками: иначе пятый перенос повторит его снова.

Что делает: пересчитывает `sha256` и `bytes` для ТЕХ файлов, чьё содержимое
разошлось с замком, и дописывает в `verified_against` причину расхождения —
что именно изменилось и чем это проверено. Ничего не выдумывает: если файла
нет, он не добавляется; записи о непроверенном не делается.

    python3 automation/local/refresh-pins-lock.py --repo var/site-repos/<проект> \\
        --reason "подключён читатель режима (src/indexing_mode.py)" [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


def главная(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True, help="каталог проекта сайта")
    p.add_argument("--reason", default="", help="что изменилось в рантайме")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    репо = pathlib.Path(args.repo).resolve()
    замок = репо / "pins.lock.json"
    if not замок.is_file():
        print(f"нет замка {замок}", file=sys.stderr)
        return 2
    данные = json.loads(замок.read_text(encoding="utf-8"))
    файлы = данные.get("files") or {}
    if not файлы:
        print(f"{замок}: раздел files пуст — пересчитывать нечего", file=sys.stderr)
        return 2

    изменено: list[str] = []
    отсутствует: list[str] = []
    for имя, запись in файлы.items():
        п = репо / "src" / имя
        if not п.is_file():
            отсутствует.append(имя)
            continue
        байты = п.read_bytes()
        новый = hashlib.sha256(байты).hexdigest()
        if новый == запись.get("sha256"):
            continue
        прежний = str(запись.get("sha256") or "")[:12]
        изменено.append(f"{имя}: {прежний} -> {новый[:12]}")
        if args.dry_run:
            continue
        запись["sha256"] = новый
        запись["bytes"] = len(байты)
        пояснение = str(запись.get("verified_against") or "").rstrip()
        причина = args.reason or "изменён общий рантайм семейства"
        запись["verified_against"] = (
            f"{пояснение} || Замок пересчитан: {причина}. Прежний отпечаток "
            f"{прежний}. Проверено прогоном проверок репозитория "
            "(checks/run.sh), включая indexing-mode-rules и "
            "indexing-live-switch.").strip(" |")

    if отсутствует:
        print("файлов замка нет в src (запись не трогается):", ", ".join(отсутствует))
    if not изменено:
        print("замок уже совпадает с исходниками")
        return 0
    print("расхождения:", *изменено, sep="\n  ")
    if args.dry_run:
        print("сухой прогон: файл не менялся")
        return 0
    замок.write_text(json.dumps(данные, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print(f"замок обновлён: {замок}")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная())
