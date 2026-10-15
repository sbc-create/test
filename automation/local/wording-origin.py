#!/usr/bin/env python3
"""Откуда витрина печатает оставшуюся формулировку: файл и строка.

Зачем отдельно от сверки публичных страниц. Та отвечает «на домене осталось N
формулировок», и этого мало: правка идёт в файл, а файлов у витрины десятки, и
один и тот же текст в семействе живёт в разных слоях.

Урок, оплаченный дважды. Сессия витрины `1lordserials1.online` показала: после
замены текста в `src/` формулировки остались на живой главной, потому что
печатает их НАЛОЖЕНИЕ — оно переопределяет `главная()` целиком. Её же уточнение
важнее первого вывода: смотреть надо не на наличие каталога `overlay/`, а на
то, переопределён ли КОНКРЕТНЫЙ метод. У той витрины правка ядра до главной не
доехала, а до подвала доехала — `_подвал` наложение не трогает.

Поэтому инструмент ищет не каталог, а файл и строку, и делает это по
СКЛЕЕННОМУ исходнику: фраза бывает свёрстана переносом строковых литералов — на
странице печатается целиком, поиском подстрокой не находится. Именно на этом
молчала доставляемая проверка `checks/public_wording.py`.

Формулировки берутся из измерения публичных страниц
(`automation/local/editorial-public-state.py`), а не придумываются.

Ничего не меняет: только читает файлы выложенного выпуска.

    python3 automation/local/wording-origin.py --release /srv/lordserial33-biz/current \\
        --domain lordserial33.biz
    python3 automation/local/wording-origin.py --release <путь> --phrase "текст"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИЗМЕРЕНИЕ = КОРЕНЬ / "docs/verification/editorial-public-state-20261015.json"

_СКЛЕЙКА = re.compile(r"""(?:"\s*\+?\s*")|(?:'\s*\+?\s*')""")


def склеенный(текст: str) -> str:
    """Исходник в виде, в котором фраза видна так же, как на странице."""
    return re.sub(r"\s+", " ", _СКЛЕЙКА.sub("", текст))


def ближайшая_функция(строки: list[str], номер: int) -> str:
    """Имя ближайшего `def` выше строки — ПОДСКАЗКА, а не истина.

    У таблиц уровня модуля ближайший `def` оказывается сверху случайно, и
    выдавать его за место печати нельзя. Поэтому ответ помечается словом
    «рядом», а решение принимает читатель по файлу и строке.
    """
    for i in range(номер, -1, -1):
        м = re.match(r"\s*(?:async\s+)?def\s+([^\s(]+)", строки[i])
        if м:
            отступ = len(строки[i]) - len(строки[i].lstrip())
            return f"{м.group(1)}{' (метод)' if отступ else ''}"
    return "(вне функции)"


def фразы_домена(домен: str) -> list[str]:
    if not ИЗМЕРЕНИЕ.is_file():
        print(f"нет измерения {ИЗМЕРЕНИЕ}: сначала прогоните "
              "automation/local/editorial-public-state.py", file=sys.stderr)
        return []
    д = json.loads(ИЗМЕРЕНИЕ.read_text(encoding="utf-8"))
    return list((д.get("с_остатками") or {}).get(домен) or [])


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--release", type=Path, required=True,
                   help="каталог выложенного выпуска витрины")
    р.add_argument("--domain", default="",
                   help="домен: формулировки берутся из измерения страниц")
    р.add_argument("--phrase", action="append", default=[],
                   help="формулировка явно (можно несколько раз)")
    опции = р.parse_args(аргв)

    фразы = list(опции.phrase) or фразы_домена(опции.domain)
    if not фразы:
        print("нечего искать: ни --phrase, ни остатков по домену в измерении",
              file=sys.stderr)
        return 2
    if not опции.release.is_dir():
        print(f"нет каталога выпуска {опции.release}", file=sys.stderr)
        return 2

    файлы = sorted(p for каталог in ("src", "overlay", "template")
                   for p in (опции.release / каталог).rglob("*.py")
                   if (опции.release / каталог).is_dir()
                   and "__pycache__" not in str(p))
    print(f"выпуск: {опции.release}")
    print(f"файлов: {len(файлы)}; каталоги: "
          f"{sorted({p.parent.name for p in файлы})}")

    не_найдено = 0
    for фраза in фразы:
        найдено: list[tuple[str, int, str]] = []
        for ф in файлы:
            исходник = ф.read_text(encoding="utf-8", errors="replace")
            строки = исходник.splitlines()
            попал = False
            for n, с in enumerate(строки):
                if фраза in с:
                    найдено.append((str(ф.relative_to(опции.release)), n + 1,
                                    ближайшая_функция(строки, n)))
                    попал = True
            if not попал and фраза in склеенный(исходник):
                найдено.append((str(ф.relative_to(опции.release)), 0,
                                "свёрстана переносом литералов"))
        print(f"\n«{фраза[:70]}»")
        if not найдено:
            не_найдено += 1
            print("   в файлах выпуска НЕ найдена: приходит из закреплённого "
                  "артефакта либо собирается из частей — правка идёт "
                  "переходником")
        for имя, строка, функция in найдено:
            где = f"строка {строка}" if строка else "перенос литералов"
            print(f"   {имя}: {где}, рядом {функция}")

    print(f"\nформулировок: {len(фразы)}; без найденного места: {не_найдено}")
    return 1 if не_найдено else 0


if __name__ == "__main__":
    raise SystemExit(главное())
