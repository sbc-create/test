#!/usr/bin/env python3
"""Непо́днятая песочница: ограничение окружения — пропуск, отказ — отказ.

    python3 automation/local/wire-sandbox-skip.py --repo var/site-repos/<проект> [--dry-run]
    python3 automation/local/wire-sandbox-skip.py --all-animego [--dry-run]

Зачем. Проверки песочницы поднимают настоящую витрину на копии снимка. Витрина
fail-closed: без читаемого `config/player.json` она не запускается вовсе — и это
правильно. Файл живёт вне git (на раннере его нет) и на самой машине принадлежит
root в режиме 0600 — так его положил установщик владельца.

Измерено 2026-10-07 на an1mego.site и animeg0.site: пять проверок песочницы
(`content_update`, `data_chain`, `sections_update`, `community_storage`,
`moderation`) печатали «стенд песочницы не поднялся» и возвращали 1. То есть
прогон краснел от ограничения ОКРУЖЕНИЯ ПРОВЕРКИ, а не от дефекта витрины — и
краснел молча, не называя причины. У третьей ячейки (an1meg0.site) тех же
проверок не касалось только потому, что её `player.json` принадлежит обычному
пользователю.

Правильное поведение в этом же репозитории уже есть: `checks/sitemap_wired.py`
при той же беде печатает «ПРОПУСК живой ярус: витрину не поднять правами —
PermissionError…» и пройденной проверкой это не считает. Инструмент переносит то
же решение в проверки песочницы.

Что меняется: вместо «не поднялся → 1» проверка ЧИТАЕТ вывод витрины и

* при ограничении окружения (нет прав на `config/player.json`, нет самого файла,
  не задан `LORDS_PLAYER_CONFIG`) — объявляет ПРОПУСК вслух и возвращает 0;
* при любой другой причине — печатает последние строки вывода витрины и
  возвращает 1, то есть отказ остаётся отказом и перестаёт быть молчаливым.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕПОЗИТОРИИ = КОРЕНЬ / "var" / "site-repos"
ЯЧЕЙКИ_ANIMEGO = ("an1mego-site", "an1meg0-site", "animeg0-site")

#: Вспомогательная функция, одна на файл. Имя уникальное, чтобы не столкнуться
#: с существующими.
ПОМОЩНИК = '''

#: Признаки того, что витрина не поднялась по ОГРАНИЧЕНИЮ ОКРУЖЕНИЯ проверки, а
#: не из-за дефекта. `config/player.json` живёт вне git и на самой машине
#: принадлежит root в режиме 0600; витрина без publisher_id не работает
#: намеренно — это её fail-closed свойство, проверяемое отдельно.
ОГРАНИЧЕНИЯ_ОКРУЖЕНИЯ = (
    "Permission denied", "PermissionError",
    "плеер без publisher_id не заработает", "LORDS_PLAYER_CONFIG",
)


def _почему_не_поднялась(процесс) -> tuple[bool, str]:
    """`(это ограничение окружения, последние строки вывода витрины)`."""
    вывод = ""
    try:
        if процесс.stdout is not None:
            вывод = процесс.stdout.read() or ""
    except Exception:  # noqa: BLE001 — причина важнее способа её прочитать
        вывод = ""
    хвост = вывод.strip()[-600:]
    return any(п in вывод for п in ОГРАНИЧЕНИЯ_ОКРУЖЕНИЯ), хвост
'''

ТИХОЕ = '''            print("стенд песочницы не поднялся", file=sys.stderr)
            return 1'''

ГРОМКОЕ = '''            окружение, хвост = _почему_не_поднялась(процесс)
            if окружение:
                # Пропуск объявляется вслух и пройденной проверкой не считается.
                print("ПРОПУЩЕНО  стенд песочницы не поднялся по ограничению "
                      f"окружения проверки: {хвост[-200:]}")
                return 0
            print("стенд песочницы не поднялся; вывод витрины:", file=sys.stderr)
            print(хвост, file=sys.stderr)
            return 1'''

ТИХОЕ_ИСКЛ = '''    raise SystemExit("стенд песочницы не поднялся")'''

ГРОМКОЕ_ИСКЛ = '''    окружение, хвост = _почему_не_поднялась(процесс)
    if окружение:
        print("ПРОПУЩЕНО  стенд песочницы не поднялся по ограничению окружения "
              f"проверки: {хвост[-200:]}")
        raise SystemExit(0)
    raise SystemExit("стенд песочницы не поднялся; вывод витрины: " + хвост)'''


def имя_процесса(текст: str, место: int) -> str:
    """Как в этом файле называется объект процесса витрины."""
    окно = текст[max(0, место - 2000): место]
    for имя in ("процесс", "пр", "сервер", "стенд"):
        if f"{имя} = subprocess.Popen" in окно:
            return имя
    return ""


def править(файл: pathlib.Path, сухо: bool) -> str:
    т = файл.read_text(encoding="utf-8")
    if "_почему_не_поднялась" in т:
        return "уже перенесено"
    место = т.find("стенд песочницы не поднялся")
    if место < 0:
        return "места подъёма стенда нет"
    имя = имя_процесса(т, место)
    if not имя:
        return "ОТКАЗ: имя объекта процесса не определено"

    было = т
    if ТИХОЕ in т:
        т = т.replace(ТИХОЕ, ГРОМКОЕ.replace("процесс", имя))
    elif ТИХОЕ_ИСКЛ in т:
        т = т.replace(ТИХОЕ_ИСКЛ, ГРОМКОЕ_ИСКЛ.replace("процесс", имя))
    else:
        return "ОТКАЗ: форма отказа не распознана"

    # Помощник ставится после последнего импорта верхнего уровня.
    строки = т.split("\n")
    последний_импорт = max(
        (н for н, с in enumerate(строки)
         if с.startswith(("import ", "from ")) and "noqa" not in с),
        default=0)
    строки.insert(последний_импорт + 1, ПОМОЩНИК.replace("процесс", имя))
    т = "\n".join(строки)
    if т != было and not сухо:
        файл.write_text(т, encoding="utf-8")
    return "перенесено"


def главная(argv: list[str]) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--repo", action="append", default=[])
    р.add_argument("--all-animego", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    о = р.parse_args(argv[1:])

    цели: list[pathlib.Path] = []
    if о.all_animego:
        цели += [РЕПОЗИТОРИИ / и for и in ЯЧЕЙКИ_ANIMEGO]
    for р_ in о.repo:
        п_ = pathlib.Path(р_)
        цели.append(п_ if п_.is_absolute() else КОРЕНЬ / п_)
    if not цели:
        print(__doc__)
        return 2

    отказов = 0
    for цель in цели:
        проверки = цель / "checks"
        if not проверки.is_dir():
            print(f"{цель.name}: checks/ нет")
            continue
        файлы = [ф for ф in sorted(проверки.glob("*.py"))
                 if "стенд песочницы не поднялся" in ф.read_text(
                     encoding="utf-8", errors="replace")]
        print(f"=== {цель.name}: проверок с песочницей {len(файлы)}")
        for ф in файлы:
            итог = править(ф, о.dry_run)
            отказов += int(итог.startswith("ОТКАЗ"))
            print(f"   {ф.name:24} {итог}")
    return 1 if отказов else 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
