#!/usr/bin/env python3
"""Каждый путь `ReadWritePaths=` юнита обязан существовать на диске.

Повод измерен и стоил суточного обновления СЕМИ витрин. В `ReadWritePaths`
обработчиков стоял `/srv/animedia-icu/data`, которого на диске ещё не было
(витрина тогда не переехала), и рядом три таких же пути Yummy. systemd
отказывает на подготовке namespace кодом **226/NAMESPACE** — целиком, а не
«пропустив лишний путь», — поэтому обновление не запускалось вовсе. Снаружи
это выглядело как «таймер есть, значит обновляется».

Проверка статическая и только читающая: разбирает файлы юнитов и спрашивает
диск. Три исхода различаются, потому что их склейка и прячет такие случаи:

* путь есть — хорошо;
* пути нет, и префикса `-` у него нет — **беда**: юнит упадёт на запуске;
* пути нет, но стоит `-` — systemd пропускает его намеренно, беды нет;
* посмотреть не дали права — **предел измерения**, не «нет»: родитель закрыт
  рабочей учётной записи, а systemd работает от root и путь увидит.

Шаблоны с `%i`/`$VAR` статически не разрешаются и пропускаются явно.

Код возврата 1 — есть пути, которых нет; 0 — таких нет.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

СТРОКА = re.compile(r"^ReadWritePaths\s*=\s*(.+)$", re.M)
ПО_УМОЛЧАНИЮ = "/etc/systemd/system"


def пути_юнита(текст: str) -> list[str]:
    """Все значения `ReadWritePaths=` файла, развёрнутые по пробелам."""
    return [п for значение in СТРОКА.findall(текст) for п in значение.split()]


def разобрать(каталог: pathlib.Path) -> tuple[list[str], list[str], int, int]:
    """(беды, недоступные, юнитов с путями, путей всего)."""
    беды: list[str] = []
    недоступные: list[str] = []
    юнитов = путей = 0
    for юнит in sorted(каталог.glob("*.service")):
        try:
            текст = юнит.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        пути = пути_юнита(текст)
        if not пути:
            continue
        юнитов += 1
        for путь in пути:
            путей += 1
            чистый = путь.lstrip("-")
            if "%" in чистый or "$" in чистый:
                continue
            try:
                есть = pathlib.Path(чистый).exists()
            except PermissionError:
                недоступные.append(f"{юнит.name}: {чистый}")
                continue
            if есть or путь.startswith("-"):
                continue
            беды.append(f"{юнит.name}: {чистый}")
    return беды, недоступные, юнитов, путей


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--units", default=ПО_УМОЛЧАНИЮ,
                   help=f"каталог юнитов (по умолчанию {ПО_УМОЛЧАНИЮ})")
    а = р.parse_args()
    каталог = pathlib.Path(а.units)
    if not каталог.is_dir():
        print(f"ОТКАЗ: нет каталога юнитов {каталог}", file=sys.stderr)
        return 2
    беды, недоступные, юнитов, путей = разобрать(каталог)
    print(f"юнитов с ReadWritePaths: {юнитов}; путей: {путей}")
    if беды:
        print(f"ПУТЕЙ НЕТ НА ДИСКЕ: {len(беды)} — такой юнит падает 226/NAMESPACE "
              f"целиком, а не пропускает путь")
        for б in беды:
            print(f"   {б}")
    else:
        print("все обязательные пути существуют")
    if недоступные:
        print(f"проверить не дали права: {len(недоступные)} — это предел "
              f"измерения, а не «нет»")
        for н in недоступные:
            print(f"   {н}")
    return 1 if беды else 0


if __name__ == "__main__":
    raise SystemExit(main())
