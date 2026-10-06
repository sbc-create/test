#!/usr/bin/env python3
"""Подключение перечитывания снимка (lords_snapshot_reload) в main() ядра lords.

Ядро читает каталог и подробности один раз при запуске, поэтому обновление
снимка доходило до посетителя только через перезапуск процесса — с отказами
соединений на время подъёма (замер 2026-10-06, lordserials22.info). Вставка
заводит наблюдение за файлами снимка до создания сервера; новый снимок
строится в фоне и подменяется на месте.

Порядок как у apply-perf-memo-hook-patch.py: точечно, по якорю создания
сервера в main(); якоря нет или он не единственный — отказ; применённая
вставка распознаётся и пропускается; `--check` ничего не пишет. Нет модуля —
витрина работает как раньше и называет причину в журнале.

Замер и причина — docs/PERF_NETWORK_AUDIT_20261005.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path

ЯКОРЬ = "    сервер = ThreadingHTTPServer((args.host, args.port), Обработчик)\n"
ПРИЗНАК = "import lords_snapshot_reload as _перечитывание"
ВСТАВКА = '''    # Перечитывание снимка на месте (lords_snapshot_reload, файл семейства
    # рядом с ядром). Без него новый снимок доходил до посетителя только
    # перезапуском процесса: отказы соединений на время подъёма (замер
    # 2026-10-06). Нет модуля — витрина работает как раньше.
    try:
        import lords_snapshot_reload as _перечитывание
    except ImportError:
        _перечитывание = None
    if _перечитывание is None:
        print("[nova] перечитывание снимка не заведено: модуля lords_snapshot_reload нет", flush=True)
    else:
        print(f"[nova] {_перечитывание.установить(sys.modules[__name__])}", flush=True)
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
