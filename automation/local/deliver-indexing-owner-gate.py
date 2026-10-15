#!/usr/bin/env python3
"""Доставить третий гейт индексации в читатель витрины — одну вставку.

Что доставляется и почему. Читатель режима индексации обещал заголовком три
независимых источника решения, а проверял два: разрешение выпуска и файл
состояния. Разрешение ВЛАДЕЛЬЦА (`owner_authorized_open` в том же файле) не
проверялось — его проверяет только операция, которая файл пишет. Любой другой
писатель, положивший `desired_state: OPEN` с `owner_authorized_open: false`,
открыл бы витрину. Нашла линия витрины `animedia.icu` 2026-10-15; исправлено в
шаблоне (`automation/host/indexing_mode.py`), проверки —
`tests/unit/test_indexing_owner_gate.py`.

Почему нужен отдельный инструмент, а не «выпуск шаблона». Измерено по всем 22
рабочим копиям: у КАЖДОЙ витрины свой закреплённый экземпляр
`src/indexing_mode.py`, и они разошлись (152, 163 и 175 строк у разных
семейств). Ни одна не тянет файл из шаблона при выпуске: копия пришла при
создании, и её сумма стоит в `pins.lock.json` витрины. Значит правка шаблона
сама не доезжает никуда — её нужно внести в каждую копию.

Вставка берётся ИЗ ШАБЛОНА, а не переписывается здесь: второй копии того же
условия существовать не должно.

Направление отказа — закрытие: витрина без разрешения владельца становится
закрытой, а не открытой. Безопасность измерена на узле: все 12 файлов
состояния несут `owner_authorized_open: true`, у витрин партии K2 файла нет
вовсе (они закрыты и остаются закрытыми).

Ничего не выкладывает: правит рабочую копию. Выпуск — за линией витрины.

    python3 automation/local/deliver-indexing-owner-gate.py --dry-run lords-10
    python3 automation/local/deliver-indexing-owner-gate.py --repo <путь>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ШАБЛОН = КОРЕНЬ / "automation" / "host" / "indexing_mode.py"
ФАЙЛ = "indexing_mode.py"

ЯКОРЬ = ('    состояние = str(сырое.get("desired_state") or "").strip().upper()\n'
         "    if состояние == ОТКРЫТ:\n"
         '        return ОТКРЫТ, ""')

ПРИМЕЧАНИЕ = (
    "Третий гейт индексации: читатель проверяет owner_authorized_open, а не "
    "только разрешение выпуска и файл состояния. Прежде разрешение владельца "
    "проверяла лишь операция, которая файл пишет, и файл с OPEN без "
    "разрешения открыл бы витрину. Направление отказа — закрытие."
)


def вставка_из_шаблона() -> str:
    """Ветка открытия шаблона целиком — вместе с третьим условием."""
    t = ШАБЛОН.read_text(encoding="utf-8")
    начало = t.index('    состояние = str(сырое.get("desired_state")')
    конец = t.index('        return ОТКРЫТ, ""', начало) + len('        return ОТКРЫТ, ""')
    кусок = t[начало:конец]
    if "owner_authorized_open" not in кусок:
        raise SystemExit("в шаблоне нет третьего гейта — нечего доставлять")
    return кусок


def закрепить(проект: Path, файл: Path) -> str:
    замок = проект / "pins.lock.json"
    if not замок.is_file():
        return "замка нет: пересчитывать нечего"
    д = json.loads(замок.read_text(encoding="utf-8"))
    запись = (д.get("files") or {}).get(ФАЙЛ)
    if запись is None:
        return f"в замке нет записи о {ФАЙЛ}"
    запись["sha256"] = hashlib.sha256(файл.read_bytes()).hexdigest()
    запись["bytes"] = файл.stat().st_size
    запись["verified_against"] = "правка ячейки поверх git"
    прежнее = (запись.get("note") or "").strip()
    if ПРИМЕЧАНИЕ not in прежнее:
        запись["note"] = (прежнее + " " if прежнее else "") + ПРИМЕЧАНИЕ
    замок.write_text(json.dumps(д, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    return "замок обновлён"


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("sites", nargs="*", help="site_id витрин в var/new-sites")
    р.add_argument("--repo", action="append", default=[], type=Path,
                   help="путь к рабочей копии витрины: линия витрины "
                        "запускает инструмент на СВОЕЙ копии сама")
    р.add_argument("--dry-run", action="store_true")
    опции = р.parse_args(аргв)
    if not опции.sites and not опции.repo:
        р.error("нужен хотя бы один site_id или --repo")

    вставка = вставка_из_шаблона()
    цели = [(s, КОРЕНЬ / "var" / "new-sites" / s) for s in опции.sites]
    цели += [(п.name, п) for п in опции.repo]

    плохо = 0
    for имя, проект in цели:
        файл = проект / "src" / ФАЙЛ
        if not файл.is_file():
            print(f"[x] {имя}: нет {файл}")
            плохо += 1
            continue
        было = файл.read_text(encoding="utf-8")
        if "owner_authorized_open" in было:
            print(f"{имя}: уже есть — третий гейт доставлен")
            continue
        if было.count(ЯКОРЬ) != 1:
            print(f"[x] {имя}: ветки открытия не найдено (или она не одна) — "
                  "копия разошлась с шаблоном, правку надо вносить руками")
            плохо += 1
            continue
        стало = было.replace(ЯКОРЬ, вставка, 1)
        if опции.dry_run:
            print(f"{имя}: третий гейт лёг бы ({len(было)} -> {len(стало)} "
                  "знаков), сухой прогон")
            continue
        файл.write_text(стало, encoding="utf-8")
        г = subprocess.run(
            [sys.executable, "-c",
             "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf-8').read())",
             str(файл)], capture_output=True, text=True)
        if г.returncode != 0:
            файл.write_text(было, encoding="utf-8")
            print(f"[x] {имя}: после правки файл не разбирается, возвращён")
            плохо += 1
            continue
        print(f"{имя}: третий гейт доставлен; {закрепить(проект, файл)}")
    return 1 if плохо else 0


if __name__ == "__main__":
    raise SystemExit(главное())
