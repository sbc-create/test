#!/usr/bin/env python3
"""Замер памяти витрин: RSS, высшая отметка, снимок, возраст процесса.

Один и тот же вывод служит замером «до» и «после» по временному порядку
обслуживания (`docs/MEMORY_MAINTENANCE_ORDER.md`). Ничего не меняет: читает
только `/proc` и размеры файлов данных, root не нужен.

Базовая линия считается по витринам с ОДИНАКОВЫМ размером снимка: превышение
над минимумом своей группы и есть дрейф, который снимает перезапуск. Сравнивать
витрины с разными снимками нельзя — у них разный законный объём данных.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ПРОЦЕССЫ = Path("/proc")
КОРНИ = Path("/srv")
МиБ = 1024 * 1024
ПОРОГ_РЕДАКТОРА = 2048  # МиБ, seo_operator/editor_run.py; снижать нельзя
ТАКТ = 100.0  # SC_CLK_TCK


def _кб(текст: str, поле: str) -> int:
    м = re.search(rf"^{поле}:\s+(\d+) kB$", текст, re.M)
    return int(м.group(1)) if м else 0


def _витрина(командная: str) -> str | None:
    """Имя витрины из пути запуска: /srv/<витрина>/current/… .

    Считается только сам сервер витрины: он запускается с `--port`. Иначе в
    замер попадают обновлятель данных (`animedia-data-update.py`, живёт минуту
    и держит свои 150 МиБ) и даже оболочка, которая этот замер выполняет, — RSS
    витрины оказывается завышен, а её возраст обнулён.
    """
    if "--port" not in командная:
        return None
    м = re.search(r"/srv/([^/\x00]+)/(?:current|releases)/", командная)
    return м.group(1) if м else None


def _снимок(витрина: str) -> float:
    данные = КОРНИ / витрина / "data"
    всего = 0
    for хвост in ("catalog.json", "details.json"):
        for файл in данные.glob(f"*{хвост}"):
            try:
                всего += файл.stat().st_size
            except OSError:
                pass
    return round(всего / МиБ, 1)


def собрать() -> list[dict]:
    сейчас = time.time()
    загрузка = float((ПРОЦЕССЫ / "uptime").read_text().split()[0])
    найдено: dict[str, dict] = {}
    for запись in ПРОЦЕССЫ.iterdir():
        if not запись.name.isdigit():
            continue
        try:
            командная = (запись / "cmdline").read_bytes().decode("utf-8", "replace")
            витрина = _витрина(командная)
            if not витрина:
                continue
            состояние = (запись / "status").read_text()
            старт = float((запись / "stat").read_text().rsplit(") ", 1)[1].split()[19])
        except (OSError, IndexError, ValueError):
            continue  # процесс успел завершиться — он уже не занимает память
        мера = найдено.setdefault(витрина, {
            "showcase": витрина, "rss_mib": 0, "hwm_mib": 0, "processes": 0,
            "age_s": None, "snapshot_mib": _снимок(витрина)})
        мера["rss_mib"] += _кб(состояние, "VmRSS") // 1024
        мера["hwm_mib"] = max(мера["hwm_mib"], _кб(состояние, "VmHWM") // 1024)
        мера["processes"] += 1
        возраст = int(загрузка - старт / ТАКТ)
        прежний = мера["age_s"]
        мера["age_s"] = возраст if прежний is None else min(прежний, возраст)
    return sorted(найдено.values(), key=lambda м: -м["rss_mib"])


def хост() -> dict:
    память = (ПРОЦЕССЫ / "meminfo").read_text()
    доступно = _кб(память, "MemAvailable") // 1024
    убийств = None
    try:
        м = re.search(r"^oom_kill (\d+)$", (ПРОЦЕССЫ / "vmstat").read_text(), re.M)
        убийств = int(м.group(1)) if м else None
    except OSError:
        pass
    return {"mem_available_mib": доступно,
            "mem_total_mib": _кб(память, "MemTotal") // 1024,
            "oom_kill_total": убийств,
            "editor_threshold_mib": ПОРОГ_РЕДАКТОРА,
            "editor_can_start": доступно >= ПОРОГ_РЕДАКТОРА}


ДОПУСК = 0.2  # снимки считаются сравнимыми, если различаются не более чем на 20%


def группы(витрины: list[dict]) -> list[list[dict]]:
    """Витрины сравнимы, когда их снимки одного порядка.

    Точное равенство размера не годится: снимки одного семейства расходятся на
    единицы МиБ, и каждая витрина оказалась бы в группе из себя одной — дрейф
    тогда всегда нулевой. Абсолютный шаг корзины тоже не годится: он свёл бы в
    одну группу витрину на 3 МиБ снимка и служебный процесс без данных.
    """
    по_размеру = sorted((м for м in витрины if м["snapshot_mib"] > 0),
                        key=lambda м: м["snapshot_mib"])
    собрано: list[list[dict]] = []
    for м in по_размеру:
        if собрано and м["snapshot_mib"] <= собрано[-1][0]["snapshot_mib"] * (1 + ДОПУСК):
            собрано[-1].append(м)
        else:
            собрано.append([м])
    собрано.extend([м] for м in витрины if м["snapshot_mib"] <= 0)
    return собрано


def дрейф(витрины: list[dict]) -> list[dict]:
    for группа in группы(витрины):
        база = min(м["rss_mib"] for м in группа)
        один = len(группа) == 1
        for м in группа:
            м["baseline_mib"] = база
            м["drift_mib"] = м["rss_mib"] - база
            # одиночке сравнивать себя не с чем: это не «дрейфа нет»
            м["comparable"] = not один
    return витрины


def _возраст(секунды: int | None) -> str:
    if секунды is None:
        return "—"
    return f"{секунды // 3600}ч{(секунды % 3600) // 60:02d}м"


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="замер памяти витрин")
    р.add_argument("--json", action="store_true", help="машинный вывод")
    а = р.parse_args(аргв)
    витрины, х = дрейф(собрать()), хост()
    if а.json:
        print(json.dumps({"host": х, "showcases": витрины},
                         ensure_ascii=False, indent=2))
        return 0
    print(f"{'витрина':26} {'RSS':>6} {'HWM':>6} {'снимок':>7} {'база':>6} "
          f"{'дрейф':>6} {'проц':>5} {'возраст':>8}")
    print("RSS — сумма по процессам витрины, HWM — наибольшая отметка одного из них")
    for м in витрины:
        дрейф_ = f"{м['drift_mib']}" if м["comparable"] else "—"
        print(f"{м['showcase'][:26]:26} {м['rss_mib']:6} {м['hwm_mib']:6} "
              f"{м['snapshot_mib']:7} {м['baseline_mib']:6} {дрейф_:>6} "
              f"{м['processes']:5} {_возраст(м['age_s']):>8}")
    print(f"\nMemAvailable {х['mem_available_mib']} из {х['mem_total_mib']} МиБ; "
          f"порог редактора {х['editor_threshold_mib']} МиБ — "
          f"{'хватает' if х['editor_can_start'] else 'НЕ хватает'}; "
          f"oom_kill за загрузку: {х['oom_kill_total']}")
    кандидаты = [м for м in витрины if м["comparable"] and м["drift_mib"] > 0]
    if кандидаты:
        п = max(кандидаты, key=lambda м: м["drift_mib"])
        print(f"наибольший дрейф: {п['showcase']} (+{п['drift_mib']} МиБ к базе "
              f"{п['baseline_mib']} при снимке {п['snapshot_mib']} МиБ)")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
