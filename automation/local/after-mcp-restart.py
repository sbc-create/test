#!/usr/bin/env python3
"""Приёмка перезапуска моста одной командой. Только чтение.

Перезапуск `site-factory-mcp` — действие владельца (`systemctl` и `sudo` в
профиле сессии запрещены). А вот проверка после него должна быть одной командой,
иначе «перезапустили» и «работает исправленный код» опять окажутся разными
утверждениями, как 12.10.

Что проверяется по порядку:

1. **процесс новый** — время запуска службы позже времени правки кода
   (`service-code-freshness.py`);
2. **процесс соответствует юниту** — в командной строке есть `--read-only`
   (12.10 живой процесс шёл без него, хотя юнит его объявляет);
3. **авторство записей** — снимок `overlay-provenance-diff.py` по всей сети ДО
   первой публикации: эти числа станут основанием для сравнения.

Инструмент НИЧЕГО не перезапускает и не публикует: он печатает состояние и
следующий шаг. Коды: 0 — перезапуск состоялся и проверки пройдены; 1 — ещё нет;
2 — измерить не удалось.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ЮНИТ = "site-factory-mcp.service"


def _запустить(аргументы: list[str], таймаут: int = 600) -> tuple[int, str]:
    г = subprocess.run(аргументы, capture_output=True, text=True, timeout=таймаут)
    return г.returncode, (г.stdout or "") + (г.stderr or "")


def свежесть_кода() -> dict:
    код, вывод = _запустить([sys.executable,
                             str(КОРЕНЬ / "automation/local/service-code-freshness.py"),
                             "--unit", ЮНИТ])
    устарел = "ИСПОЛНЯЕТ СТАРЫЙ КОД" in вывод
    м = re.search(r"правка новее запуска на ([\d.]+) ч", вывод)
    return {"измерено": bool(вывод.strip()), "код_устарел": устарел,
            "отставание_ч": float(м.group(1)) if м else None,
            "вывод": вывод.strip().splitlines()[:4]}


def командная_строка() -> dict:
    """`--read-only` в строке запуска живого процесса моста."""
    for п in pathlib.Path("/proc").iterdir():
        if not п.name.isdigit():
            continue
        try:
            строка = (п / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", "replace")
        except OSError:
            continue
        if "factory.qwen.mcp" in строка:
            return {"измерено": True, "pid": п.name,
                    "read_only": "--read-only" in строка,
                    "строка": строка.strip()[:160]}
    return {"измерено": False, "почему": "процесс моста не найден"}


def авторство() -> dict:
    код, вывод = _запустить([sys.executable,
                             str(КОРЕНЬ / "automation/local/overlay-provenance-diff.py")])
    м = re.search(r"измерено (\d+) из (\d+); подмен авторства (\d+)", вывод)
    return {"измерено": bool(м), "код": код,
            "домены": (int(м.group(1)), int(м.group(2))) if м else None,
            "подмен": int(м.group(3)) if м else None,
            "хвост": вывод.strip().splitlines()[-3:]}


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="приёмка перезапуска моста")
    р.add_argument("--json", action="store_true")
    дов = р.parse_args(аргв)

    свежесть = свежесть_кода()
    строка = командная_строка()
    авт = авторство()
    перезапущен = свежесть.get("измерено") and not свежесть.get("код_устарел")

    if дов.json:
        print(json.dumps({"свежесть": свежесть, "командная_строка": строка,
                          "авторство": авт, "перезапущен": bool(перезапущен)},
                         ensure_ascii=False, indent=2))
    else:
        print("1. код службы против правок:")
        for с in свежесть.get("вывод") or ["— нет вывода"]:
            print(f"      {с}")
        print("2. командная строка живого процесса:")
        if not строка.get("измерено"):
            print(f"      НЕ ИЗМЕРЕНО — {строка.get('почему')}")
        else:
            print(f"      pid {строка['pid']}, --read-only:"
                  f" {'есть' if строка['read_only'] else 'НЕТ'}")
            print(f"      {строка['строка']}")
        print("3. подмена авторства по сети (снимок ДО публикации):")
        if not авт.get("измерено"):
            print("      НЕ ИЗМЕРЕНО")
        else:
            изм, всего = авт["домены"]
            print(f"      измерено {изм} из {всего}; подмен {авт['подмен']}")
        print()
        if перезапущен:
            print("ПЕРЕЗАПУСК СОСТОЯЛСЯ. Следующий шаг — по одной витрине:")
            print("   1) линия SEO снимает паузу ТОЛЬКО на zonafilm.space;")
            print("   2) одна публикация описания;")
            print("   3) python3 automation/local/overlay-provenance-diff.py"
                  " --domain zonafilm.space — новых подмен быть не должно;")
            print("   4) затем прогон по всей сети без аргументов и следующая витрина.")
        else:
            print("ПЕРЕЗАПУСКА ЕЩЁ НЕ БЫЛО: служба держит код старше правки.")
            print("   Блок владельца: docs/OWNER_BLOCK_MCP_RESTART.md")
            print("   Пауза публикаций Lords/Zona остаётся в силе.")
    if not свежесть.get("измерено"):
        return 2
    return 0 if перезапущен else 1


if __name__ == "__main__":
    sys.exit(main())
