#!/usr/bin/env python3
"""Несущие пути целы, и ни один работающий контейнер не держится за неучтённый.

Зачем. Проект трёх индексируемых витрин Yummy поднят из файла, который лежит в
рабочей копии агента (8,8 МБ, без движения с 1 октября) — то есть выглядит
самым выбрасываемым из 206 копий, а является несущим. Предупреждение в
документе читает владелец; каталог удаляет тот, кто освобождает место, и
документа он может не читать. Поэтому проверка машинная.

Две стороны, и обе нужны:

  реестр → диск     каждый путь из `config/load-bearing-paths.json` существует;
  контейнеры → реестр  каждый файл из метки `com.docker.compose.project.config_files`
                    работающих контейнеров либо лежит под /srv (путь выпуска),
                    либо назван в реестре. Иначе появился новый несущий путь,
                    о котором учёт не знает.

Вторая сторона важнее первой: первая ловит уже случившуюся потерю, вторая —
появление новой зависимости до потери.

    python3 automation/local/load-bearing-check.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "load-bearing-paths.json"

#: Путь выпуска: файлы отсюда несущими не считаются — они и есть место,
#: куда всё перечисленное должно переехать.
ПУТЬ_ВЫПУСКА = ("/srv/",)


def реестр() -> dict:
    return json.loads(РЕЕСТР.read_text(encoding="utf-8"))


def файлы_контейнеров() -> dict[str, list[str]]:
    """Имя контейнера → файлы, которыми он поднят. Пусто, если нет docker."""
    try:
        г = subprocess.run(
            ["docker", "ps", "--format",
             '{{.Names}}\t{{.Label "com.docker.compose.project.config_files"}}'],
            capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    итог: dict[str, list[str]] = {}
    for строка in (г.stdout or "").splitlines():
        имя, _, файлы = строка.partition("\t")
        if not файлы.strip():
            continue
        итог[имя.strip()] = [ф.strip() for ф in файлы.split(",") if ф.strip()]
    return итог


def _разрешить(путь: str) -> Path:
    """Путь до цели ссылок. Несуществующий путь остаётся как есть."""
    п = Path(путь)
    try:
        return п.resolve()
    except OSError:
        return п


def _покрыт(файл: str, учтённые: list[Path]) -> bool:
    """Файл назван в учёте сам либо лежит под учтённым каталогом."""
    ф = _разрешить(файл)
    for у in учтённые:
        if ф == у:
            return True
        if у.is_dir() and у in ф.parents:
            return True
    return False


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--no-docker", action="store_true",
                   help="только сторона «реестр → диск»")
    опции = р.parse_args(аргв)

    д = реестр()
    записи = д["paths"]
    зависимости = д.get("label_dependencies") or []
    print(f"несущих путей в учёте: {len(записи)}; "
          f"зависимостей метки: {len(зависимости)}\n")

    беды: list[str] = []
    for з in записи:
        п = Path(з["path"])
        цел = п.exists()
        print(f"{'ЕСТЬ ' if цел else 'НЕТ  '} {з['path']}")
        print(f"        {з['why'][:150]}")
        if not цел:
            беды.append(f"несущий путь исчез: {з['path']} "
                        f"(дефект {з.get('defect')}, выпуск "
                        f"{'блокируется' if з.get('release_blocking') else 'не блокируется'})")
    for з in зависимости:
        цел = Path(з["path"]).exists()
        print(f"{'ЕСТЬ ' if цел else 'нет  '} {з['path']}  (зависимость метки)")
        if not цел:
            # Не находка: содержимое есть в другом месте. Но операции compose
            # над этими контейнерами будут ругаться до пересоздания.
            print("        путь исчез — метка указывает в пустоту; "
                  "содержимое есть в другом месте, нужно пересоздание")

    if not опции.no_docker:
        # Сравниваются РАЗРЕШЁННЫЕ пути, и запись-каталог покрывает файлы под
        # собой. Первый прогон этого не делал и назвал неучтёнными четыре
        # файла, которые как раз учтены: путь в метке шёл через символическую
        # ссылку, а запись в учёте была каталогом.
        учтённые = [_разрешить(з["path"])
                    for з in (*записи, *зависимости)]
        print()
        неучтённые: dict[str, list[str]] = {}
        for контейнер, файлы in файлы_контейнеров().items():
            для_него = [ф for ф in файлы
                        if not ф.startswith(ПУТЬ_ВЫПУСКА)
                        and not _покрыт(ф, учтённые)]
            if для_него:
                неучтённые[контейнер] = для_него
        if неучтённые:
            print("контейнеры держатся за НЕУЧТЁННЫЕ пути:")
            for контейнер, файлы in sorted(неучтённые.items()):
                print(f"   {контейнер}")
                for ф in файлы:
                    print(f"      {ф}")
                беды.append(f"{контейнер}: файл выпуска вне /srv и вне учёта "
                            f"({файлы[0]})")
        else:
            print("контейнеров, держащихся за неучтённые пути вне /srv, нет")

    print(f"\nнаходок: {len(беды)}")
    for б in беды:
        print(f"   {б}")
    return 1 if беды else 0


if __name__ == "__main__":
    raise SystemExit(главное())
