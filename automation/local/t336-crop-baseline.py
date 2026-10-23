#!/usr/bin/env python3
"""Снимок «до» для приёмки T336: размеры, вес и суммы обложек набора.

ЗАЧЕМ ДО, А НЕ ПОСЛЕ. T336 меняет КАДРИРОВАНИЕ: отношение больше 0,94
обрезается по центру до 0,85 при неизменной высоте. Проверить это можно только
сравнением с тем, что было, а «что было» существует до выпуска. Снимок,
сделанный после, уже ничего не доказывает.

ЧТО СНИМАЕТСЯ по каждому адресу набора:

* байты, SHA-256 и размеры в пикселях — на канарейке и на контроле;
* отношение ширины к высоте: именно по нему T336 решает, обрезать или нет
  (порог 0,94), и файлы до 0,94 включительно не должны измениться ни на байт;
* сама картинка сохраняется рядом, чтобы приёмка сравнивала содержимое, а не
  только числа.

Набор задаётся ключом `--uuid` (можно несколько) и дополняется вариантами
ширины `--width`, потому что обрезка обязана применяться ко ВСЕМ вариантам
одинаково.

    python3 automation/local/t336-crop-baseline.py --out var/t336-before \\
        --uuid 01a155cc-... --uuid 019fc2ae-...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

КАНАРЕЙКА = "animedia.icu"
КОНТРОЛЬ = "animedia.space"
АГЕНТ = "factory-crop-baseline"


def скачать(адрес: str) -> bytes | None:
    р = subprocess.run(
        ["curl", "-sSL", "--max-time", "30", "-A", АГЕНТ, адрес],
        capture_output=True, timeout=60)
    return р.stdout or None


def размеры(байты: bytes) -> tuple[int | None, int | None, str]:
    try:
        from PIL import Image
    except ImportError as сбой:
        return None, None, f"PIL недоступен: {сбой}"
    import io
    try:
        с = Image.open(io.BytesIO(байты))
        return с.width, с.height, с.format or ""
    except Exception as сбой:  # noqa: BLE001
        return None, None, f"не разобрано: {type(сбой).__name__}"


def main(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--uuid", action="append", default=[], required=True)
    р.add_argument("--width", action="append", default=["", "160", "240",
                                                        "320", "720"],
                   help="варианты ширины; пустая строка — адрес без параметра")
    р.add_argument("--out", default="var/t336-before")
    а = р.parse_args(аргв)
    каталог = pathlib.Path(а.out)
    каталог.mkdir(parents=True, exist_ok=True)
    итог = []
    for уид in а.uuid:
        for ширина in а.width:
            хвост = f"?w={ширина}" if ширина else ""
            for домен, роль in ((КАНАРЕЙКА, "канарейка"),
                                (КОНТРОЛЬ, "контроль")):
                адрес = f"https://{домен}/poster/{уид}.webp{хвост}"
                байты = скачать(адрес)
                запись = {"домен": домен, "роль": роль, "uuid": уид,
                          "вариант": ширина or "без", "адрес": адрес}
                if not байты:
                    запись["исход"] = "НЕ ПОЛУЧЕНО"
                    итог.append(запись)
                    continue
                ш, в, формат = размеры(байты)
                запись.update({
                    "байт": len(байты),
                    "sha256": hashlib.sha256(байты).hexdigest(),
                    "ширина": ш, "высота": в, "формат": формат,
                    "отношение": (round(ш / в, 4) if ш and в else None),
                })
                имя = f"{роль}-{уид[:8]}-{ширина or 'plain'}.webp"
                (каталог / имя).write_bytes(байты)
                запись["файл"] = str(каталог / имя)
                итог.append(запись)
    (каталог / "baseline.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(f"{'роль':<10} {'uuid':<10} {'вариант':<8} {'пиксели':<12}"
          f" {'отн':<7} {'байт':>8}  обрезка по T336")
    for з in итог:
        if з.get("исход"):
            print(f"{з['роль']:<10} {з['uuid'][:8]:<10}"
                  f" {з['вариант']:<8} {з['исход']}")
            continue
        отн = з["отношение"]
        будет = ("обрежется до 0,85" if отн and отн > 0.94
                 else "не меняется")
        print(f"{з['роль']:<10} {з['uuid'][:8]:<10} {з['вариант']:<8}"
              f" {str(з['ширина']) + 'x' + str(з['высота']):<12}"
              f" {отн if отн is not None else '—':<7} {з['байт']:>8}"
              f"  {будет}")
    print(f"снимок сохранён в {каталог}/baseline.json и рядом файлами")
    получено = sum(1 for з in итог if not з.get("исход"))
    print(f"ЗАВЕРШЕНО: записей {len(итог)}, получено {получено}",
          file=sys.stderr)
    return 0 if получено else 1


if __name__ == "__main__":
    sys.exit(main())
