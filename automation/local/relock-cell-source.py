#!/usr/bin/env python3
"""Перезакрепить исходник ячейки, правка которого решена отдельно от фабрики.

Зачем это нужно
---------------

`pins.lock.json` закрепляет каждый заимствованный исходник по sha256 и помнит,
откуда он взят (`repo_path`, `verified_against: git`). Проверка выпуска
`pins-match-sources` сверяет суммы и валит сборку при расхождении — так и
должно быть: иначе закрепление было бы записью о намерении, а не о факте.

Но бывает решённое расхождение. Партия K2 несёт исправления интерфейса,
сделанные В ЯЧЕЙКАХ: решение D212а прямо оставляет семейный рантайм на
отдельный выпуск, потому что тот же файл исполняют 17 действующих витрин.
Измерено 2026-10-14: с 12:10 каждый выпуск восьми витрин падал на
`pins-match-sources` (`lords-frontend.py: sha256 905e2d1938a2 вместо
2e5c3c0d2dc2`), и зелёного прогона CI у партии не было ни одного — то есть
активация была невозможна независимо от входов владельца.

Что делает инструмент
---------------------

Приводит замок к ФАКТУ и сохраняет оба конца расхождения:

* `sha256`, `bytes` — по реальному файлу;
* `base_sha256` — сумма, с которой файл разошёлся (прежнее значение замка);
* `verified_against` — `правка ячейки поверх git` вместо `git`;
* `note` — чьим решением правка живёт в ячейке.

Причина обязательна и в текст не придумывается: без `--reason` инструмент
отказывает. Молча переписать сумму значило бы снять проверку тем же движением,
которым она охраняется.

    python3 automation/local/relock-cell-source.py --site lords-10 \\
        --file lords-frontend.py --reason "D212а: ..."
    python3 automation/local/relock-cell-source.py --site lords-10 --file ... --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПРОИСХОЖДЕНИЕ = "правка ячейки поверх git"


class Отказ(RuntimeError):
    """Операция не выполнена, и причина названа."""


def перезакрепить(site_id: str, имя: str, причина: str, *, apply: bool,
                  основа: Path | None = None) -> dict:
    корень_ячеек = основа or (КОРЕНЬ / "var" / "new-sites")
    ячейка = корень_ячеек / site_id
    замок_путь = ячейка / "pins.lock.json"
    исходник = ячейка / "src" / имя
    if not замок_путь.is_file():
        raise Отказ(f"{site_id}: нет {замок_путь}")
    if not исходник.is_file():
        raise Отказ(f"{site_id}: нет {исходник} — перезакреплять нечего")
    замок = json.loads(замок_путь.read_text(encoding="utf-8"))
    записи = замок.get("files") or {}
    if имя not in записи:
        raise Отказ(f"{site_id}: {имя} в замке не закреплён; добавлять новые "
                    "записи этот инструмент не умеет — это другая операция")

    было = записи[имя]
    факт = hashlib.sha256(исходник.read_bytes()).hexdigest()
    отчёт = {
        "site_id": site_id,
        "файл": имя,
        "замок": str(замок_путь.relative_to(КОРЕНЬ)) if замок_путь.is_relative_to(КОРЕНЬ)
                 else str(замок_путь),
        "было": было.get("sha256", "")[:12],
        "стало": факт[:12],
        "применено": bool(apply),
    }
    if было.get("sha256") == факт:
        отчёт["итог"] = "менять нечего: замок уже совпадает с файлом"
        return отчёт
    if not apply:
        отчёт["итог"] = "сухой прогон: замок будет приведён к факту"
        return отчёт

    запись = dict(было)
    # Прежняя сумма не теряется: без неё расхождение перестаёт быть видимым, и
    # следующий сеанс не отличит решённую правку от случайной.
    запись.setdefault("base_sha256", было.get("sha256", ""))
    запись.update({"sha256": факт, "bytes": исходник.stat().st_size,
                   "verified_against": ПРОИСХОЖДЕНИЕ, "note": причина})
    записи[имя] = запись
    замок["files"] = записи
    замок_путь.write_text(json.dumps(замок, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")

    # Сверка ПОСЛЕ записи: отчёт не вправе утверждать согласие, которого нет.
    снова = (json.loads(замок_путь.read_text(encoding="utf-8")).get("files") or {})
    if снова.get(имя, {}).get("sha256") != факт:
        raise Отказ(f"{site_id}: после записи замок не совпал с файлом")
    отчёт["итог"] = "замок приведён к факту, прежняя сумма сохранена в base_sha256"
    return отчёт


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", action="append", required=True,
                   help="site_id ячейки; можно повторять")
    р.add_argument("--file", required=True, help="имя исходника в src/")
    р.add_argument("--reason", required=True,
                   help="чьим решением правка живёт в ячейке (обязательно)")
    р.add_argument("--apply", action="store_true", help="записать; без флага — сухой прогон")
    а = р.parse_args()
    if len(а.reason.strip()) < 20:
        print("ОТКАЗ: причина должна называть решение, а не быть отметкой",
              file=sys.stderr)
        return 2
    отчёты = []
    for site_id in а.site:
        try:
            отчёты.append(перезакрепить(site_id, а.file, а.reason.strip(), apply=а.apply))
        except Отказ as ош:
            print(str(ош), file=sys.stderr)
            return 3
    print(json.dumps(отчёты, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
