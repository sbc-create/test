#!/usr/bin/env python3
"""Какие службы перезапускать после публикации каталога. Ответ — из реестра.

Зачем отдельный файл
--------------------

Суточный сценарий написан на shell и работает списком имён. Пока список был
захардкожен, он давал два отказа. Первый: после переноса витрины в собственную
ячейку прежний unit закрыт от ручного запуска, и `systemctl restart` возвращал
отказ, спрятанный за `|| true`. Второй тише и потому хуже: в момент перезапуска
новой службы прежняя успевала занять порт и вернуть посетителям прежний код.

Печатает имена служб через пробел — ровно то, что shell подставит в `restart`.
Витрины, перечитывающие снимок сами, в список не попадают: перезапуск им не
нужен, а стоит он минут — читаются 16.7 МБ каталога и 78.3 МБ подробностей.

Пустой вывод — законный ответ «перезапускать нечего», а не ошибка.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

РЕЕСТР = Path(os.environ.get(
    "SITE_CELLS_REGISTRY",
    "/home/claude/wt-portable-site-cell-01/config/site-cells.json"))


def размещения() -> dict[str, dict]:
    if not РЕЕСТР.is_file():
        return {}
    данные = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    return {c["site_id"]: (c.get("runtime") or {})
            for c in (данные.get("cells") or []) if c.get("runtime")}


def main(argv: list[str]) -> int:
    if not argv:
        print("нужны идентификаторы витрин", file=sys.stderr)
        return 2
    карта = размещения()
    службы: list[str] = []
    for site_id in argv:
        блок = карта.get(site_id)
        if not блок:
            # Неизвестная витрина — не повод молча ничего не делать: shell
            # получит пустой список и решит, что перезапуск не нужен.
            print(f"{site_id}: нет в реестре ячеек", file=sys.stderr)
            return 3
        if блок.get("reload") == "mtime":
            continue
        unit = блок.get("unit")
        if not unit:
            print(f"{site_id}: в реестре не назван unit", file=sys.stderr)
            return 3
        if unit == блок.get("previous_unit"):
            print(f"{site_id}: реестр называет один и тот же unit текущим и "
                  "прежним", file=sys.stderr)
            return 3
        if unit not in службы:
            службы.append(unit)
    print(" ".join(службы))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
