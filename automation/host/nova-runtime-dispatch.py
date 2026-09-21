#!/usr/bin/env python3
"""Загрузчик витрины: исполняет релиз, назначенный ИМЕННО этому домену.

Этот файл устанавливается по общему пути `/srv/lords/.frontend/lords-frontend.py`,
который назван в `ExecStart` шести юнитов. Он ничего не отдаёт по HTTP сам: он
определяет витрину по порту, находит назначенный ей неизменяемый релиз и
передаёт ему управление через `os.execv`.

## Что это чинит

Раньше по этому пути лежал сам рантайм. Одна выкладка перезаписывала его — и
меняла исполняемые байты сразу у шести витрин трёх семейств. Пока соседей не
перезапускали, разницы не было видно; после первого же перезапуска витрина
начинала исполнять чужой код, продолжая объявлять свою прежнюю сборку.

Теперь выкладка не трогает этот файл вовсе. Она кладёт новый каталог в
`releases/` и переставляет символическую ссылку `sites/<витрина>/current` —
только у своей витрины. Байты соседей при этом физически недостижимы для
изменения.

## Почему execv, а не import

`execv` заменяет образ процесса: у релиза остаются те же PID, порт, окружение и
аргументы, а `__file__` становится путём релиза. Значит `/__template_version`
сам сообщает, какой именно релиз исполняется, и это не приходится брать на веру.
Импорт оставил бы `__file__` этого загрузчика, и витрина снова объявляла бы не
то, что исполняет.

## Порядок выбора

1. порт → витрина по `lords-runtime-registry.json`;
2. витрина → `sites/<витрина>/current` (неизменяемый релиз);
3. привязки нет → `releases/legacy/current` — замороженная копия того, что эта
   витрина исполняет сегодня. Это сознательный выбор: витрина вне задания
   получает ровно свой текущий код, а не чужой новый.

Отсутствие и релиза, и запасного пути — отказ с ненулевым кодом. Молча поднять
витрину на неизвестном коде хуже, чем не поднять её вовсе.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

FRONT = pathlib.Path(__file__).resolve().parent
REGISTRY = FRONT / "lords-runtime-registry.json"
LEGACY_LINK = FRONT / "releases" / "legacy" / "current"
RUNTIME_NAME = "lords-frontend.py"

#: Защита от петли: если исполняемый релиз почему-то окажется этим же файлом,
#: execv уйдёт в бесконечный цикл и витрина будет «стартовать» вечно.
LOOP_GUARD = "LORDS_RUNTIME_DISPATCHED"


def порт_из_аргументов(argv: list[str]) -> str:
    for i, arg in enumerate(argv):
        if arg == "--port" and i + 1 < len(argv):
            return argv[i + 1].strip()
        if arg.startswith("--port="):
            return arg.split("=", 1)[1].strip()
    return ""


def витрина_по_порту(порт: str) -> str:
    try:
        реестр = json.loads(REGISTRY.read_text())
    except (OSError, ValueError):
        return ""
    for site_id, запись in (реестр.get("sites") or {}).items():
        if str(запись.get("port")) == порт:
            return site_id
    return ""


def цель(витрина: str) -> pathlib.Path | None:
    кандидаты = []
    if витрина:
        кандидаты.append(FRONT / "sites" / витрина / "current" / RUNTIME_NAME)
    кандидаты.append(LEGACY_LINK / RUNTIME_NAME)
    for кандидат in кандидаты:
        разрешённый = разрешить_кандидата(кандидат)
        if разрешённый is not None:
            return разрешённый
    return None


def разрешить_кандидата(кандидат: pathlib.Path) -> pathlib.Path | None:
    """Разрешённый путь релиза или None.

    Разрешение обязательно: `__file__` должен стать путём неизменяемого
    каталога, а не символической ссылки, иначе доказательство «какой релиз
    исполняется» снова становится косвенным.
    """
    try:
        разрешённый = кандидат.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not разрешённый.is_file():
        return None
    if разрешённый == pathlib.Path(__file__).resolve():
        return None
    return разрешённый


def main() -> int:
    if os.environ.get(LOOP_GUARD):
        print(
            f"{LOOP_GUARD} уже выставлен: загрузчик вызвал сам себя, запуск прекращён",
            file=sys.stderr,
        )
        return 70

    порт = порт_из_аргументов(sys.argv[1:])
    витрина = витрина_по_порту(порт) if порт else ""
    путь = цель(витрина)

    if путь is None:
        print(
            "релиз не найден: "
            f"порт={порт or 'не указан'} витрина={витрина or 'не определена'}; "
            f"ни {FRONT / 'sites' / (витрина or '<витрина>') / 'current'}, "
            f"ни {LEGACY_LINK} не ведут к {RUNTIME_NAME}",
            file=sys.stderr,
        )
        return 71

    os.environ[LOOP_GUARD] = "1"
    os.environ.setdefault("LORDS_RUNTIME_SITE", витрина)
    os.environ["LORDS_RUNTIME_RELEASE_PATH"] = str(путь)
    os.execv(sys.executable, [sys.executable, str(путь), *sys.argv[1:]])
    return 72  # execv не возвращается; строка нужна только статическому анализу


if __name__ == "__main__":
    raise SystemExit(main())
