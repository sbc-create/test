#!/usr/bin/env python3
"""Перенос исправленного сторожа плеера в рантайм витрины семейства zona.

Дефект (замер 2026-10-05, docs/PERF_NETWORK_AUDIT_20261005.md): в
`СКРИПТ_ПЛЕЕРА_КЛИЕНТ` таймеры «нет воспроизведения» (25 с) и «показать
отказ» (35 с) взводились при монтировании плеера, то есть от загрузки
страницы. Во время преролла плеер пересоздавался на 25-й секунде, а без
нажатия через 110 с исправный фильм показывал «Видео временно недоступно».

У zonafilm.cc правка стоит оверлеем сайта (src/player_watchdog.py), у витрин,
где ядро исполняется напрямую, — переносится этим инструментом, как перенос
контракта доступности серий (apply-episode-availability-patch.py): точечно,
по якорям, ВНУТРИ константы скрипта. Нет якоря — отказ, а не тихий пропуск.
Идемпотентен: применённая правка распознаётся (`armPlayTimers`) и
пропускается. `--check` ничего не пишет и отвечает ненулевым кодом, если файл
ещё не приведён.

Замены — те же, что у оверлея: automation/host/zona_player_watchdog.py
(копия src/player_watchdog.py витрины zonafilm.cc).
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ЗДЕСЬ = Path(__file__).resolve().parent
_спец = importlib.util.spec_from_file_location("zona_player_watchdog", ЗДЕСЬ / "zona_player_watchdog.py")
СТОРОЖ = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(СТОРОЖ)

НАЧАЛО = 'СКРИПТ_ПЛЕЕРА_КЛИЕНТ = """'


def применить(текст: str) -> tuple[str, str]:
    """Вернуть (новый текст, исход): applied | already | отказ с причиной."""
    i = текст.find(НАЧАЛО)
    if i < 0 or текст.count(НАЧАЛО) != 1:
        raise SystemExit("нет ровно одной константы СКРИПТ_ПЛЕЕРА_КЛИЕНТ")
    начало = i + len(НАЧАЛО)
    конец = текст.index('"""', начало)
    скрипт = текст[начало:конец]
    if "armPlayTimers" in скрипт:
        return текст, "already"
    return текст[:начало] + СТОРОЖ.исправить(скрипт) + текст[конец:], "applied"


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("файлы", nargs="+")
    р.add_argument("--check", action="store_true", help="только проверить, ничего не писать")
    а = р.parse_args(argv)
    плохо = 0
    for имя in а.файлы:
        путь = Path(имя)
        текст = путь.read_text(encoding="utf-8")
        try:
            новый, исход = применить(текст)
        except (RuntimeError, SystemExit) as ош:
            print(f"{имя}: ОТКАЗ — {ош}")
            плохо = 1
            continue
        if а.check:
            print(f"{имя}: {'приведён' if исход == 'already' else 'НЕ приведён'}")
            плохо |= исход != "already"
            continue
        if исход == "applied":
            compile(новый, имя, "exec")
            путь.write_text(новый, encoding="utf-8")
        print(f"{имя}: {исход}")
    return плохо


if __name__ == "__main__":
    raise SystemExit(main())
