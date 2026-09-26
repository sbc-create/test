#!/usr/bin/env python3
"""Совпадает ли установленное с ЗАФИКСИРОВАННЫМ ПАКЕТОМ. Без root, одной командой.

    python3 automation/host/check-installed.py [--package <каталог>]

Сравнение идёт с описью пакета, а не с рабочей веткой. Рабочая ветка меняется
каждый коммит, и сверка с ней объявляла бы «расхождением» любую работу,
начатую после установки, — то есть шумела бы всегда и ничего не доказывала.

Исходы разделены на четыре, потому что они требуют разных действий:

    совпадает              ничего делать не надо
    отличается             содержимое другое -> переустановка обоснована
    отсутствует            файла в установленной копии нет -> то же
    не удалось проверить   нет прав на чтение УСТАНОВЛЕННОГО файла

Последнее — не различие. `config/site-cells.json` в корневой копии принадлежит
root в режиме 0600 сознательно, и его нечитаемость означала бы «переустановите»
при любом состоянии. В прошлом отчёте он попал в общий список расхождений; это
было неверно, и разделение исходов ровно про это.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent.parent
if not (КОРЕНЬ / "factory" / "cell" / "executor.py").is_file():
    raise SystemExit(f"не похоже на репозиторий фабрики: {КОРЕНЬ}")
УСТАНОВЛЕНО = Path("/usr/local/lib/site-factory-cell")
ХРАНИЛИЩЕ = КОРЕНЬ / "var" / "install-packages"
#: Что именно попадает в корневую копию (install-cell-executor.sh копирует три
#: каталога). automation/host в пакете есть, но в /usr/local/lib не ставится,
#: поэтому в сверку не входит.
СТАВИТСЯ = ("factory/", "schemas/", "config/")


def цифра(п: Path) -> str:
    х = hashlib.sha256()
    with п.open("rb") as ф:
        for кусок in iter(lambda: ф.read(1 << 20), b""):
            х.update(кусок)
    return х.hexdigest()


def найти_пакет(явный: str | None, свидетельство: dict) -> tuple[Path | None, str]:
    if явный:
        return Path(явный).resolve(), "указан аргументом"
    иден = свидетельство.get("package_id")
    if иден and (ХРАНИЛИЩЕ / иден / "manifest.json").is_file():
        return ХРАНИЛИЩЕ / иден, "назван установкой"
    кандидаты = [п for п in ХРАНИЛИЩЕ.glob("pkg-*") if (п / "manifest.json").is_file()]
    if not кандидаты:
        return None, "зафиксированных пакетов нет"
    кандидаты.sort(key=lambda п: json.loads((п / "manifest.json").read_text(encoding="utf-8"))["frozen_at"])
    return кандидаты[-1], "последний зафиксированный (установка пакет не назвала)"


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--package")
    а = р.parse_args()

    if not УСТАНОВЛЕНО.is_dir():
        print(f"установленной копии нет: {УСТАНОВЛЕНО}")
        return 2

    свидетельство: dict = {}
    маркер = УСТАНОВЛЕНО / "cell-install.json"
    if маркер.is_file():
        try:
            свидетельство = json.loads(маркер.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            print("cell-install.json не читается")
    print(f"установлено:      {свидетельство.get('installed_at') or 'время не записано'}")
    print(f"пакет установки:  {свидетельство.get('package_id') or 'НЕ НАЗВАН (установка старого образца)'}")
    print(f"коммит пакета:    {(свидетельство.get('package_commit') or 'не записан')[:12]}")
    print(f"корень репозиториев: {свидетельство.get('site_repos_root') or 'не записан'}")

    пакет, откуда = найти_пакет(а.package, свидетельство)
    if пакет is None:
        print(f"\nсверять не с чем: {откуда}")
        print("зафиксируйте пакет: python3 automation/host/freeze-package.py")
        return 2
    опись = json.loads((пакет / "manifest.json").read_text(encoding="utf-8"))
    print(f"сверяю с пакетом: {опись['package_id']} ({откуда}), коммит {опись['commit'][:12]}")
    if свидетельство.get("package_digest") and свидетельство["package_digest"] != опись["digest"]:
        print("   [!] установка выполнена ДРУГИМ пакетом, чем тот, с которым я сверяю")

    совпало: list[str] = []
    отличается: list[str] = []
    отсутствует: list[str] = []
    без_прав: list[str] = []

    for отн, ожидаемая in sorted(опись["files"].items()):
        if not отн.startswith(СТАВИТСЯ):
            continue
        там = УСТАНОВЛЕНО / отн
        if not там.is_file():
            отсутствует.append(отн)
            continue
        try:
            (совпало if цифра(там) == ожидаемая else отличается).append(отн)
        except PermissionError:
            без_прав.append(отн)
        except OSError as ош:
            без_прав.append(f"{отн} ({ош.strerror})")

    print()
    print(f"совпадает:            {len(совпало)}")
    print(f"отличается:           {len(отличается)}")
    print(f"отсутствует:          {len(отсутствует)}")
    print(f"не удалось проверить: {len(без_прав)} (нет прав на чтение установленного файла)")
    for имя, набор in (("отличается", отличается), ("отсутствует", отсутствует),
                       ("не удалось проверить", без_прав)):
        if набор:
            print(f"\n{имя}:")
            for и in набор[:20]:
                print("   ", и)
            if len(набор) > 20:
                print(f"    … и ещё {len(набор) - 20}")

    print()
    if отличается or отсутствует:
        print("ИТОГ: установленное отстаёт от пакета. Это основание переустановить:")
        print(f"  sudo bash {пакет}/tree/automation/host/unblock-transfer.sh")
        return 1
    if без_прав:
        print("ИТОГ: всё проверенное совпадает с пакетом. Часть файлов проверить нельзя")
        print("из-за прав, и это не различие — под root та же команда сверит и их.")
        return 0
    print("ИТОГ: установленное полностью совпадает с зафиксированным пакетом.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
