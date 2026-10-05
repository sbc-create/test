#!/usr/bin/env python3
"""Подключение памяти на снимок (lords_perf_memo) в main() ядра семейства lords.

У витрин, где ядро исполняется напрямую и своей точки входа или оверлея нет
(lordserials22.info), ставить память больше неоткуда: run.py исполняет ядро
через execv. По AGENTS.md п. 3 такого сайта ядро меняется из шаблона и
приезжает отдельным коммитом, поднимающим замок. Ядро сайта при этом несёт
местные правки (verified_against: patch), поэтому подъём пина целиком снёс бы
их — перенос идёт ТОЧЕЧНО, по якорю, как у apply-episode-availability-patch.py.

Вставка — двенадцать строк перед созданием сервера: импорт lords_perf_memo
(файл семейства рядом с ядром) и вызов установки. Нет модуля — витрина
поднимается как раньше и называет причину в журнале. Якоря нет или он не
единственный — отказ. Применённая вставка распознаётся и пропускается.
`--check` ничего не пишет.

Замер и причина — docs/PERF_NETWORK_AUDIT_20261005.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path

ЯКОРЬ = "    сервер = ThreadingHTTPServer((args.host, args.port), Обработчик)\n"
ПРИЗНАК = "import lords_perf_memo as _память"
ВСТАВКА = '''    # Память на снимок (lords_perf_memo, файл семейства рядом с ядром).
    # Главная, подборки, отбор и похожие обходили весь каталог на каждом
    # запросе (замер 2026-10-05). Ставится до первого запроса; сбрасывается при
    # смене снимка и при записи согласования серий. Нет модуля — витрина
    # работает как раньше, причина называется в журнале.
    try:
        import lords_perf_memo as _память
    except ImportError:
        _память = None
    if _память is None:
        print("[nova] память на снимок не поставлена: модуля lords_perf_memo нет", flush=True)
    else:
        print(f"[nova] {_память.установить(sys.modules[__name__])}", flush=True)
'''


def применить(текст: str) -> tuple[str, str]:
    if ПРИЗНАК in текст:
        return текст, "already"
    n = текст.count(ЯКОРЬ)
    if n != 1:
        raise SystemExit(f"якорь создания сервера найден {n} раз(а), ожидался 1")
    i = текст.index("def main(")
    j = текст.index(ЯКОРЬ)
    if j < i:
        raise SystemExit("якорь стоит не в main()")
    return текст.replace(ЯКОРЬ, ВСТАВКА + ЯКОРЬ, 1), "applied"


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("файлы", nargs="+")
    р.add_argument("--check", action="store_true")
    а = р.parse_args(argv)
    плохо = 0
    for имя in а.файлы:
        путь = Path(имя)
        новый, исход = применить(путь.read_text(encoding="utf-8"))
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
