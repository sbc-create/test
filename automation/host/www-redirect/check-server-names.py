#!/usr/bin/env python3
"""Проверка правки `server_name` перед перезагрузкой nginx и после неё.

Правка www-зеркал состоит из двух частей, и вторая без первой бесполезна:
надо дописать блок для www И убрать `www.` из `server_name` блока 443. Если
убрать забыли, nginx скажет `conflicting server name`, победит первый блок,
перенаправления не будет — а выглядеть будет сделанным.

Ловушка, из-за которой проверка нужна отдельно. У `zona-02.conf` ДВА блока:
порт 80 и порт 443. Из блока 80 имя `www.` убирать НЕЛЬЗЯ — именно он
перенаправляет `http://www` на https. Глобальная замена по файлу сломала бы
это молча. Поэтому проверка смотрит на блоки по отдельности: в 443 имени www
быть не должно, в 80 — должно.

Проверка умеет упасть на неисправленном состоянии (D203): до правки она
называет все четыре файла.

Ничего не меняет: только читает. Root не нужен.

    python3 automation/host/www-redirect/check-server-names.py
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

КАТАЛОГ = Path("/etc/nginx/lords")

#: Файл → домен. Перечень не угадывается: он равен набору готовых вставок
#: рядом с этим сценарием.
ЦЕЛИ: tuple[tuple[str, str], ...] = (
    ("animego-04-tls.conf", "an1meg0.site"),
    ("lords-05-tls.conf", "lordserials22.info"),
    ("zona-03-tls.conf", "zonafilm12.site"),
    ("zona-02.conf", "zonafilm.cc"),
)


def блоки(текст: str) -> list[tuple[str, str]]:
    """Блоки server как пары (порт, тело). Порт — то, что слушает блок."""
    итог: list[tuple[str, str]] = []
    for кусок in re.split(r"^server\s*\{", текст, flags=re.M)[1:]:
        тело = кусок.split("\n}")[0]
        порты = re.findall(r"^\s*listen\s+(?:\[::\]:)?(\d+)", тело, re.M)
        итог.append((порты[0] if порты else "?", тело))
    return итог


def имена(тело: str) -> list[str]:
    м = re.search(r"^\s*server_name\s+([^;]+);", тело, re.M)
    return м.group(1).split() if м else []


def разобрать(текст: str, домен: str) -> list[str]:
    """Замечания по файлу. Пустой список — правка на месте."""
    плохо: list[str] = []
    видели_443 = False
    видели_80 = False
    for порт, тело in блоки(текст):
        перечень = имена(тело)
        if not перечень:
            continue
        www = f"www.{домен}"
        if порт == "443":
            видели_443 = True
            # Блок, который только перенаправляет, называть лишним нельзя:
            # у него server_name РОВНО www, и это и есть цель правки.
            if перечень == [www]:
                continue
            if www in перечень:
                плохо.append(
                    f"блок 443 всё ещё слушает {www} вместе с основным именем "
                    f"({' '.join(перечень)}) — nginx скажет conflicting "
                    "server name, и перенаправления не будет")
        elif порт == "80":
            видели_80 = True
            if www not in перечень:
                плохо.append(
                    f"из блока 80 убрано {www} — именно он перенаправляет "
                    "http://www на https, и без имени зеркало по http "
                    "перестанет отвечать")
    if not видели_443:
        плохо.append("блока 443 с server_name в файле не нашлось — "
                     "предел измерения, а не исправность")
    # Блок 80 есть не у всех файлов: у трёх витрин он в отдельном файле.
    # Отсутствие блока 80 здесь — не замечание.
    del видели_80
    return плохо


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--dir", type=Path, default=КАТАЛОГ)
    опции = р.parse_args(аргв)

    всего = 0
    замечаний = 0
    непрочитанных = 0
    for файл, домен in ЦЕЛИ:
        путь = опции.dir / файл
        if not путь.is_file():
            print(f"   [? ] {файл:24s} файла нет: {путь}")
            непрочитанных += 1
            continue
        try:
            текст = путь.read_text(encoding="utf-8")
        except OSError as сбой:
            print(f"   [? ] {файл:24s} не прочитан: {type(сбой).__name__}")
            непрочитанных += 1
            continue
        всего += 1
        плохо = разобрать(текст, домен)
        if плохо:
            замечаний += len(плохо)
            print(f"   [x ] {файл:24s} {домен}")
            for строка in плохо:
                print(f"        {строка}")
        else:
            print(f"   [ок] {файл:24s} {домен}: блок 443 не слушает www")

    print(f"\nфайлов проверено: {всего}; замечаний: {замечаний}")
    if непрочитанных:
        print(f"не прочитано: {непрочитанных} — предел измерения, "
              "а не исправность", file=sys.stderr)
        return 2
    return 1 if замечаний else 0


if __name__ == "__main__":
    raise SystemExit(главное())
