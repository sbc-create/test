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
import re
import subprocess
import sys
from pathlib import Path

КАНОНИЧЕСКОЕ_ДЕРЕВО = Path("/home/claude/wt-integration-28")
ОЧЕРЕДЬ = Path("/var/lib/lords-deploy/requests")
РЕЗУЛЬТАТЫ = Path("/var/lib/lords-deploy/results")
БРОКЕР = Path("/usr/local/libexec/site-factory/lords-deploy-broker")


def барьер_модуль():
    """Барьер лежит рядом с подателем, в том же каталоге."""
    путь = Path(__file__).resolve().parent / "lords_fence.py"
    спец = importlib.util.spec_from_loader(
        "lords_fence", importlib.machinery.SourceFileLoader("lords_fence", str(путь)))
    модуль = importlib.util.module_from_spec(спец)
    sys.modules.setdefault("lords_fence", модуль)
    спец.loader.exec_module(модуль)
    return модуль


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
    р.add_argument("--revision", default=None,
                   help="полный сороказначный SHA замороженной ревизии семейства; "
                        "без него берётся HEAD")
    р.add_argument("--attempt", type=int, default=1,
                   help="номер попытки: повтор той же ревизии осознанно, "
                        "когда причиной отказа был не артефакт")
    args = р.parse_args()

    if _git("status", "--porcelain"):
        print("дерево кандидата не чистое: заявка не подаётся", file=sys.stderr)
        return 1

    # Ревизия семейства задаётся явно, а не берётся из HEAD.
    #
    # Порядок выкладки — lords-02, затем lords-01, затем lords-03 — тем же
    # замороженным артефактом. Но между витринами HEAD уходит вперёд: пока шла
    # отрисовка канарейки, в это дерево легло несколько коммитов. Со «свежим»
    # HEAD вторая витрина получила бы другой шаблон, чем первая, и «тот же
    # артефакт» стало бы неправдой. Кэш по имени файла не спасает: имя
    # считается от ревизии.
    if args.revision:
        if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
            print(f"ревизия должна быть полным SHA из сорока знаков: {args.revision!r}",
                  file=sys.stderr)
            return 1
        существует = subprocess.run(
            ["git", "-C", str(КАНОНИЧЕСКОЕ_ДЕРЕВО), "cat-file", "-e",
             f"{args.revision}^{{commit}}"], capture_output=True)
        if существует.returncode != 0:
            print(f"ревизии {args.revision} нет в дереве", file=sys.stderr)
            return 1
        ревизия = args.revision
    else:
        ревизия = _git("rev-parse", "HEAD")
    ветка = _git("rev-parse", "--abbrev-ref", "HEAD")
    архив = собрать_артефакт(ревизия)
    сумма = отпечаток(архив)

    # Номер попытки входит в идентификатор. Повтор той же ревизии запрещён
    # «после той же ошибки» — но отказ по гонке за юнит обновления к артефакту
    # отношения не имеет, и пересобирать его было бы обманом самого себя.
    хвост = ревизия[:8] if args.attempt == 1 else f"{ревизия[:8]}-{args.attempt}"
    ид = f"lords-{'-'.join(s.split('-')[1] for s in args.sites)}-{хвост}"
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

    # Объявление барьера. Поколение растёт всегда, даже для той же ревизии:
    # повторная подача — осознанное решение выложить заново, и все заявки
    # прежнего поколения обязаны быть вытеснены им.
    барьер = барьер_модуль()
    поколения = {}
    for сайт in args.sites:
        объявлен = барьер.объявить(сайт, ревизия, сумма,
                                   reason=f"{ид} {ветка}@{ревизия[:12]}")
        поколения[сайт] = объявлен.generation
    единое = set(поколения.values())
    if len(единое) != 1:
        # Витрины идут одной заявкой и обязаны разделять поколение: иначе одно
        # поле `generation` в заявке было бы верным не для всех.
        print(f"поколения витрин разошлись: {поколения}", file=sys.stderr)
        return 1
    заявка["generation"] = единое.pop()

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
