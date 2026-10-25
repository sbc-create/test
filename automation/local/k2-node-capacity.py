#!/usr/bin/env python3
"""Запас ресурсов узла K2: память, нагрузка, диск — ОДНИМ чтением.

Зачем инструментом, а не командой «на месте». Прямой `ssh`/`ansible` из
сессии запрещён правилами фабрики, и правильно: произвольная команда в цель
не проверяется, не повторяется и не читается в истории. Поэтому чтение
состояния узла живёт инструментом — тем же способом, которым это уже делает
`automation/local/k2-freshness.py` (ansible, модуль `shell`, одна читающая
команда, инвентарь сгенерирован из `inventory/ssh-hosts.yaml`).

Что спрашивается у узла: `/proc/meminfo`, `/proc/loadavg`, число ядер и
`df -P` по корню и `/srv`. Ничего не меняется: ни файла, ни службы.

Зачем это нужно. Размещение новых витрин выбирается ИЗМЕРЕНИЕМ, а не
предположением: на управляющем узле 25.10 свободной памяти было 1,1 ГиБ при
потребности одной витрины Lords в 0,9–1,6 ГиБ, то есть пятёрка туда заведомо
не вмещается. Чтобы сказать, вмещается ли она на K2, нужны его числа.

    python3 automation/local/k2-node-capacity.py
    python3 automation/local/k2-node-capacity.py --root /srv/site-factory/k2-delivery
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ЗДЕСЬ = pathlib.Path(__file__).resolve().parents[2]
ХОСТ = "k2-zomro-01"
#: Одна читающая команда. Разделитель между частями — чтобы разбор не угадывал.
КОМАНДА = ("echo '--meminfo--'; cat /proc/meminfo; echo '--loadavg--'; "
           "cat /proc/loadavg; echo '--nproc--'; nproc; echo '--df--'; df -P / /srv; "
           "echo '--procs--'; ps -eo rss=,comm=,args= --sort=-rss | head -25")


def разобрать_память(текст: str) -> dict:
    """МиБ: всего, доступно, подкачка. Чего нет — None, а не ноль."""
    поля = {к: int(v) for к, v in re.findall(r"^(\w+):\s+(\d+) kB", текст, re.M)}
    def миб(имя):
        return поля[имя] // 1024 if имя in поля else None
    return {"total_mib": миб("MemTotal"), "available_mib": миб("MemAvailable"),
            "free_mib": миб("MemFree"), "swap_total_mib": миб("SwapTotal"),
            "swap_free_mib": миб("SwapFree")}


def разобрать_нагрузку(текст: str, ядер: int | None) -> dict:
    ч = текст.split()
    if len(ч) < 3:
        return {"load1": None, "per_core": None, "cores": ядер}
    один = float(ч[0])
    return {"load1": один, "load5": float(ч[1]), "load15": float(ч[2]),
            "cores": ядер,
            "per_core": round(один / ядер, 2) if ядер else None}


def разобрать_диск(текст: str) -> list[dict]:
    итог = []
    for строка in текст.splitlines()[1:]:
        ч = строка.split()
        if len(ч) < 6:
            continue
        итог.append({"mount": ч[5], "total_gib": round(int(ч[1]) / 2**20, 1),
                     "free_gib": round(int(ч[3]) / 2**20, 1), "used_pct": ч[4]})
    return итог


def разобрать_процессы(текст: str) -> list[dict]:
    """Процессы узла с RSS. Нужны затем, что «свободно» не отвечает на вопрос
    «сколько стоит ОДНА витрина»: без этого числа размещение выбиралось бы на
    глаз."""
    итог = []
    for строка in текст.splitlines():
        ч = строка.split(None, 2)
        if len(ч) < 3 or not ч[0].isdigit():
            continue
        итог.append({"rss_mib": int(ч[0]) // 1024, "comm": ч[1], "args": ч[2][:120]})
    return итог


def разобрать(вывод: str, ) -> dict:
    части = {}
    текущая = None
    for строка in вывод.splitlines():
        м = re.match(r"^--(\w+)--$", строка.strip())
        if м:
            текущая = м.group(1)
            части[текущая] = []
            continue
        if текущая:
            части[текущая].append(строка)
    собрать = {к: "\n".join(v) for к, v in части.items()}
    ядер = None
    if собрать.get("nproc", "").strip().isdigit():
        ядер = int(собрать["nproc"].strip())
    процессы = разобрать_процессы(собрать.get("procs", ""))
    # Витрина узнаётся по пути ВЫПУСКА, а не по имени run.py: на K2 службы
    # запускают сам рантайм (`src/lords-frontend.py`), и фильтр по run.py дал
    # «витрин запущено: 0» при восьми работающих. Ошибка измерения такого рода
    # опаснее его отсутствия: она выглядит как ответ.
    витрины = [п for п in процессы
               if "/srv/" in п["args"]
               and ("frontend.py" in п["args"] or "run.py" in п["args"])]
    return {"memory": разобрать_память(собрать.get("meminfo", "")),
            "load": разобрать_нагрузку(собрать.get("loadavg", ""), ядер),
            "disk": разобрать_диск(собрать.get("df", "")),
            "processes": процессы[:15],
            "showcases": {"count": len(витрины),
                          "rss_mib_total": sum(п["rss_mib"] for п in витрины),
                          "rss_mib_max": max((п["rss_mib"] for п in витрины), default=None),
                          "rss_mib_each": [п["rss_mib"] for п in витрины]}}


def спросить_узел(инвентарь: pathlib.Path, корень: pathlib.Path) -> tuple[str, str]:
    """(вывод, причина). Пустой вывод и названная причина — честное «не измерено»."""
    if not инвентарь.is_file():
        return "", f"инвентаря нет: {инвентарь}"
    try:
        п = subprocess.run(
            ["ansible", "-i", str(инвентарь), ХОСТ, "-m", "shell", "-a", КОМАНДА],
            capture_output=True, text=True, cwd=str(корень), timeout=180)
    except (OSError, subprocess.SubprocessError) as ош:
        return "", f"запуск не удался: {type(ош).__name__}: {ош}"
    if п.returncode != 0:
        return "", f"узел не ответил (код {п.returncode}): {(п.stderr or '').strip()[-200:]}"
    return п.stdout, ""


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--root", default="/srv/site-factory/k2-delivery",
                   help="рабочий каталог доставки, где лежит инвентарь")
    р.add_argument("--json", type=pathlib.Path)
    а = р.parse_args(аргв)
    корень = pathlib.Path(а.root)
    инвентарь = корень / "var" / "ansible" / "hosts.yml"
    вывод, причина = спросить_узел(инвентарь, корень)
    if причина:
        print(f"НЕ ИЗМЕРЕНО: {ХОСТ} — {причина}")
        print("Это не «ресурсов нет»: о запасе узла здесь не сказано ничего.")
        return 2
    св = разобрать(вывод)
    п = св["memory"]
    print(f"узел {ХОСТ}")
    print(f"   память: всего {п['total_mib']} МиБ, доступно {п['available_mib']} МиБ,"
          f" подкачка {п['swap_total_mib']} МиБ (свободно {п['swap_free_mib']})")
    н = св["load"]
    print(f"   нагрузка: {н['load1']} / {н.get('load5')} / {н.get('load15')}"
          f" на {н['cores']} ядер → {н['per_core']} на ядро")
    в = св["showcases"]
    print(f"   витрин запущено: {в['count']}, их RSS суммарно {в['rss_mib_total']} МиБ,"
          f" крупнейшая {в['rss_mib_max']} МиБ; по витринам: {в['rss_mib_each']}")
    for д in св["disk"]:
        print(f"   диск {д['mount']:6}: всего {д['total_gib']} ГиБ,"
              f" свободно {д['free_gib']} ГиБ (занято {д['used_pct']})")
    if а.json:
        а.json.parent.mkdir(parents=True, exist_ok=True)
        а.json.write_text(json.dumps({"host": ХОСТ, **св}, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"свод записан: {а.json}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
