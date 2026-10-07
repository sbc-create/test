#!/usr/bin/env python3
"""Сколько стоит ХОЛОДНАЯ отрисовка страницы. Только чтение.

    python3 automation/local/cold-render-probe.py --repo var/site-repos/<проект> \\
        --data /srv/<аккаунт>/data [--paths "/,/collections/,/new/"]

Зачем. Посетитель и обход получают 504 не тогда, когда страница «медленная», а
тогда, когда ПЕРВЫЙ запрос после сброса памятки не успевает в таймаут шлюза.
Измерено 2026-10-06 на zonafilm.cc: `/collections/` дважды ответила 504 в
последовательных проверках, а в двадцати прямых замерах — 200 за 0.08–0.5 с.
Разница между этими двумя состояниями и есть то, что здесь измеряется: первый
запрос к свежеподнятой витрине против второго и третьего к ней же.

Витрина поднимается на КОПИИ снимка площадки и слушает локальный порт. Живой
домен при этом не трогается ни одним запросом.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]


def свободный_порт() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def запрос(база: str, путь: str, домен: str, таймаут: float):
    начало = time.monotonic()
    req = urllib.request.Request(база + путь)
    req.add_header("Host", домен)
    try:
        with urllib.request.urlopen(req, timeout=таймаут) as о:
            тело = о.read()
            return о.status, len(тело), time.monotonic() - начало
    except urllib.error.HTTPError as ош:
        return ош.code, len(ош.read()), time.monotonic() - начало
    except Exception as ош:  # noqa: BLE001 — причина называется
        return 0, 0, time.monotonic() - начало


def главная(argv: list[str]) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--repo", required=True)
    р.add_argument("--data", required=True)
    р.add_argument("--paths", default="/,/collections/,/new/,/catalog/")
    р.add_argument("--timeout", type=float, default=180.0)
    о = р.parse_args(argv[1:])

    репо = pathlib.Path(о.repo)
    if not репо.is_absolute():
        репо = КОРЕНЬ / репо
    живые = pathlib.Path(о.data)
    cfg = json.loads((репо / "config" / "site.json").read_text(encoding="utf-8"))
    домен = cfg["domain"]
    пути = [п.strip() for п in о.paths.split(",") if п.strip()]

    врем = pathlib.Path(tempfile.mkdtemp(prefix="cold-render-"))
    try:
        данные = врем / "data"
        данные.mkdir()
        пропущено = []
        for ф in sorted(живые.iterdir()):
            try:
                if ф.is_file():
                    shutil.copy2(ф, данные / ф.name)
                elif ф.is_dir() and ф.name != "sitemap":
                    shutil.copytree(ф, данные / ф.name, dirs_exist_ok=True)
            except (PermissionError, OSError) as ош:
                пропущено.append(f"{ф.name} ({type(ош).__name__})")
                if ф.is_dir():
                    (данные / ф.name).mkdir(exist_ok=True)
        if пропущено:
            print("пропущено на чтение: " + ", ".join(пропущено))
        режим = врем / "indexing"
        режим.mkdir()
        (режим / f"{домен}.json").write_text(
            json.dumps({"state": "OPEN", "reason": "замер холодной отрисовки"}),
            encoding="utf-8")
        порт = свободный_порт()
        база = f"http://127.0.0.1:{порт}"
        среда = dict(os.environ)
        среда.update({"LORDS_INDEXING_ROOT": str(режим),
                      "ANIMEDIA_INDEXING_ROOT": str(режим),
                      "LORDS_INDEXING_TTL": "0",
                      "ANIMEDIA_INDEXING_TTL": "0",
                      "LORDS_SITE_HOST": домен,
                      "PYTHONDONTWRITEBYTECODE": "1"})
        пр = subprocess.Popen(
            [sys.executable, str(репо / "run.py"), "--port", str(порт),
             "--data-dir", str(данные)],
            cwd=str(репо), env=среда,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            край = time.time() + о.timeout
            поднялась = False
            while time.time() < край:
                код, _, _ = запрос(база, "/healthz", домен, 5)
                if код == 200:
                    поднялась = True
                    break
                time.sleep(0.5)
            if not поднялась:
                вывод = (пр.stdout.read() if пр.stdout else "")[-500:]
                print(f"витрина не поднялась: {вывод.strip()}")
                return 1
            print(f"{домен}: витрина поднялась на {порт}\n")
            print(f"{'путь':16} {'1-й запрос':>22} {'2-й':>14} {'3-й':>14}")
            for путь in пути:
                замеры = [запрос(база, путь, домен, о.timeout) for _ in range(3)]
                первый = замеры[0]
                print(f"{путь:16} {первый[0]:>4} {первый[2]:>8.2f}s "
                      f"{первый[1]:>7} Б "
                      f"{замеры[1][0]:>4} {замеры[1][2]:>6.2f}s "
                      f"{замеры[2][0]:>4} {замеры[2][2]:>6.2f}s")
        finally:
            пр.terminate()
            try:
                пр.wait(timeout=20)
            except subprocess.TimeoutExpired:
                пр.kill()
    finally:
        shutil.rmtree(врем, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
