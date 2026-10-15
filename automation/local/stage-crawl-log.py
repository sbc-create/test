#!/usr/bin/env python3
"""Дописывает журнал обхода в блоки, у которых есть СВОЙ `access_log`.

Объявление в http-контексте (`automation/host/nginx/00-crawl-log.conf`)
наследуют только блоки без собственного `access_log`. Измерено 2026-10-15:
таких 35, а восемь блоков объявляют свой журнал — и обход этих восьми в общий
файл не попал бы вовсе. Неполнота выглядела бы как «роботы не ходят», то есть
хуже отсутствия журнала.

nginx допускает несколько `access_log` в одном блоке: запись идёт в оба файла,
и собственный журнал витрины остаётся как был. Поэтому правка — ровно одна
добавленная строка, а не замена.

Разбор блоков берётся у `stage-https-www-fix.py`: два разных разборщика одной
конфигурации неизбежно разошлись бы.

    python3 automation/local/stage-crawl-log.py --diff
"""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import pathlib
import re
import sys

КОРЕНЬ_РЕПО = pathlib.Path(__file__).resolve().parents[2]
КОРЕНЬ_NGINX = pathlib.Path("/etc/nginx")
ВЫХОД = КОРЕНЬ_РЕПО / "var" / "staged-nginx-crawl"
СТРОКА = "access_log /var/log/nginx/crawl.log crawl if=$is_crawler;"

_сп = importlib.util.spec_from_file_location(
    "stage_https_www_fix", КОРЕНЬ_РЕПО / "automation" / "local"
    / "stage-https-www-fix.py")
_общий = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(_общий)
блоки = _общий.блоки
имена = _общий.имена


def свой_журнал(тело: str) -> list[tuple[int, int, str]]:
    """`access_log` уровня server (не внутри `location`), с его смещениями."""
    без_location = re.sub(r"(?ms)^\s*location[^{]*\{.*?^\s*\}", "", тело)
    найдено = []
    # Отступ берётся как `[ \t]*`, а не `\s*`: в многострочном режиме `^`
    # совпадает и в начале пустой строки, и `\s*` съедал бы предшествующий
    # перевод строки. Поймано своим же diff: в отступ попадал «\n    », и
    # между строками пояснения вставлялись пустые строки.
    for м in re.finditer(r"(?m)^([ \t]*)access_log[ \t]+[^;]+;", без_location):
        # Смещение ищется в ИСХОДНОМ теле: вырезание location сдвигает индексы.
        строка = м.group(0).strip()
        место = тело.find(строка)
        if место >= 0:
            найдено.append((место, место + len(строка), м.group(1)))
    return найдено


def дописать(файл: pathlib.Path) -> tuple[str, list[str]]:
    текст = файл.read_text(encoding="utf-8")
    сделано: list[str] = []
    правки: list[tuple[int, str]] = []
    for начало, _, тело in блоки(текст):
        if СТРОКА in тело:
            continue
        for место, конец, отступ in свой_журнал(тело):
            правки.append((
                начало + конец,
                f"\n{отступ}# Журнал обхода роботов — ВТОРОЙ журнал этого\n"
                f"{отступ}# блока: свой журнал витрины остаётся как был,\n"
                f"{отступ}# nginx пишет в оба. Формат и признак робота\n"
                f"{отступ}# объявлены в conf.d/00-crawl-log.conf.\n"
                f"{отступ}{СТРОКА}"))
            сделано.append(" ".join(имена(тело)) or "(без server_name)")
            break
    for место, вставка in sorted(правки, reverse=True):
        текст = текст[:место] + вставка + текст[место:]
    return текст, сделано


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--diff", action="store_true")
    а = р.parse_args()
    всего = 0
    for каталог in ("lords", "sites-enabled"):
        п = КОРЕНЬ_NGINX / каталог
        if not п.is_dir():
            continue
        for ф in sorted(п.glob("*.conf")):
            if ".bak" in ф.name:
                continue
            try:
                было = ф.read_text(encoding="utf-8")
            except OSError as ош:
                print(f"{ф.name}: не читается ({ош})")
                continue
            новый, сделано = дописать(ф)
            if новый == было:
                continue
            ВЫХОД.mkdir(parents=True, exist_ok=True)
            цель = ВЫХОД / ф.name
            цель.write_text(новый, encoding="utf-8")
            всего += len(сделано)
            print(f"{ф.relative_to(КОРЕНЬ_NGINX)} → "
                  f"{цель.relative_to(КОРЕНЬ_РЕПО)}: {', '.join(сделано)}")
            if а.diff:
                sys.stdout.writelines(difflib.unified_diff(
                    было.splitlines(keepends=True),
                    новый.splitlines(keepends=True),
                    fromfile=str(ф), tofile=str(цель)))
    print(f"\nблоков дополнено: {всего}; в /etc/nginx ничего не изменено. "
          "Порядок установки — docs/OWNER_CRAWL_LOG_20261015.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
