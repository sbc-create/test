"""Выпуски и происшествия — из каноническогo состояния программы, а не из копии.

Раздел читает `/srv/site-factory/coordination/v1` (каталог задаётся через
`SITE_ENGINE_COORDINATION_DIR`) и ничего туда не пишет. Копировать записи в
репозиторий было бы удобнее для чтения и хуже по существу: копия расходится с
оригиналом молча, и расхождение обнаруживается ровно тогда, когда по ней
принимают решение об откате.

Правило ответа одно на оба раздела: **пустой список и недоступный источник —
разные ответы**. Ноль строк на месте нечитаемого каталога выглядит как «ничего
не было». Именно так каталог тридцатипятичасовой давности месяцами считался
работающим.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

#: Сколько записей отдаётся за раз. Не «все»: журнал выпусков растёт, а экран
#: читает человек.
ПРЕДЕЛ = 100

_СТАТУС = re.compile(r"(?im)^[-*]?\s*статус\s*[:—-]\s*([A-ZА-Я_]+)")
_ВЛИЯНИЕ = re.compile(r"(?im)^[-*]?\s*влияние\s*[:—-]\s*(.+)$")
_ОБНАРУЖЕНО = re.compile(r"(?im)^[-*]?\s*обнаружено\s*[:—-]\s*(.+)$")
_ЗАГОЛОВОК = re.compile(r"(?m)^#\s+(.+)$")

ОТКРЫТЫЕ = {"OPEN", "ОТКРЫТО", "IN_PROGRESS", "ОТКРЫТ"}


def каталог(root: Path, env: dict[str, str] | None = None) -> Path | None:
    """Где лежит каноническое состояние программы.

    Явная переменная среды важнее удобного умолчания: служба может работать из
    рабочей копии, из выложенного выпуска и из проверочного стенда, и во всех
    трёх случаях «рядом с корнем» указывает в разные места.
    """
    env = env or {}
    указано = str(env.get("SITE_ENGINE_COORDINATION_DIR") or "").strip()
    if указано:
        путь = Path(указано)
        return путь if путь.is_absolute() else (root / путь)
    свой = root / "coordination" / "v1"
    return свой if свой.exists() else None


def _недоступно(причина: str) -> dict[str, Any]:
    return {"available": False, "reason": причина, "items": [], "unreadable": []}


def releases(root: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Записи выпусков: что выложено, откуда и куда откатываться."""
    основа = каталог(root, env)
    if основа is None:
        return _недоступно("каталог состояния программы не указан и не найден рядом с корнем")
    папка = основа / "releases"
    if not папка.is_dir():
        return _недоступно(f"каталог выпусков не читается: {папка}")

    записи: list[dict[str, Any]] = []
    нечитаемые: list[str] = []
    for файл in sorted(папка.glob("*.json")):
        try:
            данные = json.loads(файл.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Одна битая запись не должна прятать остальные — но и молчать о
            # себе не должна: её имя попадает в ответ отдельным списком.
            нечитаемые.append(файл.stem)
            continue
        выложено = данные.get("deployed") or {}
        записи.append(
            {
                "releaseId": файл.stem,
                "iteration": данные.get("iteration", ""),
                "branch": данные.get("branch", ""),
                "headSha": данные.get("headSha", ""),
                "commitCount": данные.get("commitCount"),
                "generatedAt": данные.get("generatedAt", ""),
                "component": выложено.get("component", ""),
                "deployedSha": выложено.get("sha", ""),
                "deployedAt": выложено.get("deployedAt", ""),
                "rollbackTo": выложено.get("previousSha", ""),
                "digest": выложено.get("digest", ""),
                "rollbackAvailable": bool(выложено.get("previousSha")),
            }
        )
    записи.sort(key=lambda з: (з["deployedAt"] or з["generatedAt"] or "", з["releaseId"]), reverse=True)
    return {
        "available": True,
        "source": str(папка),
        "items": записи[:ПРЕДЕЛ],
        "total": len(записи),
        "unreadable": нечитаемые,
    }


def incidents(root: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Происшествия: заголовок, состояние, влияние и дата обнаружения."""
    основа = каталог(root, env)
    if основа is None:
        return _недоступно("каталог состояния программы не указан и не найден рядом с корнем")
    папка = основа / "incidents"
    if not папка.is_dir():
        return _недоступно(f"каталог происшествий не читается: {папка}")

    записи: list[dict[str, Any]] = []
    нечитаемые: list[str] = []
    for файл in sorted(папка.glob("*.md")):
        try:
            текст = файл.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            нечитаемые.append(файл.stem)
            continue
        заголовок = _ЗАГОЛОВОК.search(текст)
        статус = _СТАТУС.search(текст)
        состояние = (статус.group(1).upper() if статус else "UNKNOWN").strip()
        влияние = _ВЛИЯНИЕ.search(текст)
        обнаружено = _ОБНАРУЖЕНО.search(текст)
        записи.append(
            {
                "incidentId": файл.stem,
                "title": (заголовок.group(1).strip() if заголовок else файл.stem),
                # Состояние берётся из текста. Отсутствие строки статуса — это
                # UNKNOWN, а не CLOSED: молчаливое закрытие происшествия хуже,
                # чем честно неизвестное состояние.
                "state": состояние,
                "open": состояние in ОТКРЫТЫЕ or состояние == "UNKNOWN",
                "impact": (влияние.group(1).strip() if влияние else ""),
                "detectedAt": (обнаружено.group(1).strip() if обнаружено else ""),
            }
        )
    записи.sort(key=lambda з: з["incidentId"], reverse=True)
    return {
        "available": True,
        "source": str(папка),
        "items": записи[:ПРЕДЕЛ],
        "total": len(записи),
        "open": sum(1 for з in записи if з["open"]),
        "unreadable": нечитаемые,
    }
