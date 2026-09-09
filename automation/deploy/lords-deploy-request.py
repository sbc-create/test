#!/usr/bin/env python3
"""Построитель заявки на выкладку. Выполняется от claude, ничего не выкладывает.

Зачем отдельный инструмент
--------------------------

Помощник `lords-deployctl` действует от root и глагола «подать заявку» не имеет
намеренно: подача — это не привилегированное действие, а запись файла в
очередь. Но писать этот файл руками нельзя. Рукописный JSON — это ревизия,
набранная по памяти, отпечаток, скопированный не оттуда, и путь к артефакту,
которого нет; каждая из трёх ошибок уже случалась в этом проекте.

Поэтому здесь ни одно поле не вводится: ревизия берётся из git, артефакт
собирается из этой же ревизии, отпечаток считается по собранному файлу, а
готовая заявка проверяется **схемой самого брокера** — тем же кодом, который
будет её принимать. Заявка, не прошедшая эту проверку, не попадает в очередь.

Запуск:
    python3 automation/deploy/lords-deploy-request.py --sites lords-02
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

КАНОНИЧЕСКОЕ_ДЕРЕВО = Path("/home/claude/wt-integration-28")
ОЧЕРЕДЬ = Path("/var/lib/lords-deploy/requests")
РЕЗУЛЬТАТЫ = Path("/var/lib/lords-deploy/results")
БРОКЕР = Path("/usr/local/libexec/site-factory/lords-deploy-broker")


def отпечаток(путь: Path) -> str:
    h = hashlib.sha256()
    with путь.open("rb") as ф:
        for кусок in iter(lambda: ф.read(1 << 20), b""):
            h.update(кусок)
    return h.hexdigest()


def _git(*args: str) -> str:
    готово = subprocess.run(["git", "-C", str(КАНОНИЧЕСКОЕ_ДЕРЕВО), *args],
                            capture_output=True, text=True, check=True)
    return готово.stdout.strip()


def схема_брокера():
    """Схема берётся у установленного брокера, а не переписывается здесь.

    Две копии одной схемы расходятся молча, и заявка, прошедшая мою проверку,
    отваливалась бы у него — с потерей цикла на выяснение, чья правда.
    """
    спец = importlib.util.spec_from_loader(
        "broker", importlib.machinery.SourceFileLoader("broker", str(БРОКЕР)))
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


def собрать_артефакт(ревизия: str) -> Path:
    """Архив ревизии. Собирается владельцем дерева — git от root в чужом
    каталоге это дефект LORDS-RELEASE-ADOPT-GIT-PRIVILEGED-33."""
    куда = КАНОНИЧЕСКОЕ_ДЕРЕВО / "var" / "artifacts"
    куда.mkdir(parents=True, exist_ok=True)
    архив = куда / f"{ревизия[:12]}.tar.gz"
    if архив.is_file() and архив.stat().st_size > 0:
        return архив
    временный = архив.with_suffix(".tar.gz.building")
    with временный.open("wb") as ф:
        subprocess.run(["git", "-C", str(КАНОНИЧЕСКОЕ_ДЕРЕВО), "archive",
                        "--format=tar.gz", ревизия],
                       stdout=ф, stderr=subprocess.PIPE, check=True, timeout=1800)
    os.chmod(временный, 0o644)
    временный.replace(архив)
    return архив


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--sites", nargs="+", required=True,
                   help="витрины по порядку выкладки")
    р.add_argument("--soak", type=int, default=300)
    р.add_argument("--marker", default=".theme-switch",
                   help="строка, которая обязана появиться в /assets/site.css")
    р.add_argument("--note", default="")
    args = р.parse_args()

    if _git("status", "--porcelain"):
        print("дерево кандидата не чистое: заявка не подаётся", file=sys.stderr)
        return 1
    ревизия = _git("rev-parse", "HEAD")
    ветка = _git("rev-parse", "--abbrev-ref", "HEAD")
    архив = собрать_артефакт(ревизия)
    сумма = отпечаток(архив)

    ид = f"lords-{'-'.join(s.split('-')[1] for s in args.sites)}-{ревизия[:8]}"
    заявка = {
        "deployment_id": ид,
        "sites": list(args.sites),
        "revision": ревизия,
        "artifact_sha256": сумма,
        "artifact_source": str(архив),
        "soak_seconds": args.soak,
        "expect_marker": args.marker,
        "note": args.note or f"{ветка}@{ревизия[:12]}",
    }

    брокер = схема_брокера()
    try:
        принято = брокер.проверить_заявку(dict(заявка))
    except Exception as отказ:  # noqa: BLE001 — схема брокера, а не наша
        print(f"заявка не прошла схему брокера: {отказ}", file=sys.stderr)
        return 1

    уже = РЕЗУЛЬТАТЫ / f"{ид}.json"
    if уже.is_file():
        print(f"заявка {ид} уже обрабатывалась: {уже}", file=sys.stderr)
        print("измените ревизию — повтор того же артефакта после той же ошибки запрещён",
              file=sys.stderr)
        return 2

    путь = ОЧЕРЕДЬ / f"{ид}.json"
    временный = путь.with_suffix(".json.building")
    временный.write_text(json.dumps(принято, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    os.chmod(временный, 0o664)
    временный.replace(путь)
    print(json.dumps({"request": str(путь), "deployment_id": ид,
                      "revision": ревизия, "artifact": str(архив),
                      "artifact_sha256": сумма, "sites": args.sites},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
