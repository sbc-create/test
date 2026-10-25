#!/usr/bin/env python3
"""Состав витрин узла по реестру ячеек — одной строкой, через пробел.

Зачем отдельным файлом. Этот перечень нужен и сценариям оболочки (суточная
доставка каталога), и юнитам, и людям, а живёт он в одном месте — в паспортах
(`deploy_target.ref`). Перечисление витрин строкой в юните уже стоило дорого:
суточная доставка объявляла восемь витрин, и пять новых ячеек того же узла не
получали бы обновлений каталога вовсе, причём отсутствие строки выглядит точно
так же, как «доставка настроена» (класс 47 в docs/RECURRING_FAILURES.md).

Выведенные из работы ячейки исключаются по признаку паспорта
(`withdrawal.withdrawn`), а не по отсутствию имени: решение владельца о выводе
не должно требовать правки ещё и здесь.

    python3 automation/local/node-cell-list.py k2-zomro-01
    python3 automation/local/node-cell-list.py k2-zomro-01 --json
"""
from __future__ import annotations

import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"


def витрины_узла(ref: str, реестр: pathlib.Path | None = None) -> list[str]:
    данные = json.loads((реестр or РЕЕСТР).read_text(encoding="utf-8"))
    return sorted(
        c["site_id"] for c in данные.get("cells") or []
        if (c.get("deploy_target") or {}).get("ref") == ref
        and not (c.get("withdrawal") or {}).get("withdrawn"))


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    ref = argv[0]
    имена = витрины_узла(ref)
    if not имена:
        print(f"в реестре нет витрин узла {ref}", file=sys.stderr)
        return 1
    if "--json" in argv[1:]:
        print(json.dumps({"node": ref, "cells": имена}, ensure_ascii=False))
    else:
        print(" ".join(имена))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
