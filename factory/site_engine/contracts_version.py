"""Какой набор контрактов считается текущим.

Одно место на весь код. Прежде версия стояла строкой прямо в обработчике, и
когда она отстала от разложенной на диске, служба отдавала план на три версии
младше реализации — расхождение обнаруживалось только попыткой вызвать то,
чего в плане нет.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

#: Версия, которую объявляет ЭТОТ выпуск кода.
ТЕКУЩИЙ = "1.4.0"

#: Куда выкладываются наборы. Путь переопределяется ради проверок.
КАТАЛОГ = Path(os.environ.get(
    "CONTROL_PLANE_CONTRACTS", "/srv/site-factory/control-plane-contracts"))

_ВЕРСИЯ = re.compile(r"^\d+\.\d+\.\d+$")


def _ключ(имя: str) -> tuple[int, ...]:
    return tuple(int(ч) for ч in имя.split("."))


def разложенные(каталог: Path | None = None) -> list[str]:
    к = каталог or КАТАЛОГ
    if not к.is_dir():
        return []
    return sorted((п.name for п in к.iterdir()
                   if п.is_dir() and _ВЕРСИЯ.match(п.name)), key=_ключ)


def обслуживаемый(каталог: Path | None = None) -> dict[str, object]:
    """Какой набор служба отдаёт на самом деле.

    Текущий — если он разложен. Иначе самый свежий из разложенных, и это
    прямо объявляется: отдавать устаревший план молча хуже, чем отдавать его
    с пометкой, потому что молчащий выглядит истинным.
    """
    к = каталог or КАТАЛОГ
    есть = разложенные(к)
    if ТЕКУЩИЙ in есть:
        return {"version": ТЕКУЩИЙ, "path": str(к / ТЕКУЩИЙ),
                "declared": ТЕКУЩИЙ, "matches_code": True}
    if not есть:
        return {"version": None, "path": None, "declared": ТЕКУЩИЙ,
                "matches_code": False,
                "note": f"ни один набор не разложен в {к}"}
    свежий = есть[-1]
    return {"version": свежий, "path": str(к / свежий), "declared": ТЕКУЩИЙ,
            "matches_code": False,
            "note": f"код объявляет {ТЕКУЩИЙ}, разложен {свежий}: "
                    f"набор {ТЕКУЩИЙ} ещё не выложен"}
