#!/usr/bin/env python3
"""Фактическое состояние сети: реестр против установленного против репозитория.

Одна строка — один домен. Только чтение, ни одной мутации.

    python3 automation/local/network-state.py            # все ячейки реестра
    python3 automation/local/network-state.py --json      # то же машинно

Зачем отдельный инструмент. «Остаток работ» раньше собирался из отчётов, а
отчёты describe состояние на момент написания. Здесь каждое поле измеряется
сейчас: что объявляет реестр, что РАЗЛОЖЕНО в `/srv`, что отдаёт домен и где
стоит голова репозитория. Расхождение этих четырёх и есть остаток.

Раскладок две, и обе действующие:

    releases/<build> + симлинк current   большинство ячеек
    app/ без выпусков                    ячейки AnimeGo и Animedia

Первая объявляет выпуск в `current/release-manifest.json: release`, вторая —
в `app/config/template-manifest.json: build_id`. Инструмент, знающий одну,
объявляет расхождением собственную неосведомлённость (так и было 2026-10-06 в
приёмке карты сайта), поэтому здесь читаются обе и вид раскладки печатается.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
РЕПОЗИТОРИИ = КОРЕНЬ / "var" / "site-repos"
УЧЁТКИ = pathlib.Path("/srv")


def ячейки() -> list[dict]:
    return json.loads(РЕЕСТР.read_text(encoding="utf-8"))["cells"]


def установлено(аккаунт: str) -> tuple[str, str]:
    """`(объявленный выпуск, вид раскладки)` установленного дерева."""
    к = УЧЁТКИ / аккаунт
    текущий = к / "current"
    if (к / "releases").is_dir() and текущий.exists():
        try:
            м = json.loads((текущий / "release-manifest.json").read_text(encoding="utf-8"))
            return str(м.get("release") or ""), "releases"
        except (OSError, ValueError):
            return "", "releases"
    if (к / "app").is_dir():
        try:
            м = json.loads((к / "app" / "config" / "template-manifest.json").read_text(
                encoding="utf-8"))
            return str(м.get("build_id") or ""), "app"
        except (OSError, ValueError):
            return "", "app"
    return "", ""


def публичный(домен: str, таймаут: int = 25) -> tuple[str, str]:
    """`(код ответа, build-id из заголовка)`. Пустое — факт, а не ошибка."""
    г = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "-D", "-", "-L",
         "--max-time", str(таймаут), f"https://{домен}/"],
        capture_output=True, text=True)
    код, билд = "", ""
    for с in (г.stdout or "").splitlines():
        if с.lower().startswith("http/"):
            ч = с.split()
            код = ч[1] if len(ч) > 1 else код
        elif с.lower().startswith("x-site-factory-build-id:"):
            билд = с.partition(":")[2].strip()
    return код, билд


def гит(путь: pathlib.Path, *арг: str) -> str:
    г = subprocess.run(["git", "-C", str(путь), *арг], capture_output=True, text=True)
    return (г.stdout or "").strip()


def репозиторий(аккаунт: str) -> dict:
    п = РЕПОЗИТОРИИ / аккаунт
    if not (п / ".git").is_dir():
        return {"есть": False}
    ветка = гит(п, "rev-parse", "--abbrev-ref", "HEAD")
    голова = гит(п, "rev-parse", "--short=12", "HEAD")
    грязно = bool(гит(п, "status", "--porcelain"))
    return {"есть": True, "ветка": ветка, "голова": голова, "грязно": грязно}


def строка(ячейка: dict) -> dict:
    домен = ячейка.get("domain") or ""
    аккаунт = (ячейка.get("runtime") or {}).get("account") or домен.replace(".", "-")
    выпуск, вид = установлено(аккаунт)
    код, билд = публичный(домен) if домен else ("", "")
    р = репозиторий(аккаунт)
    # Заголовок у раскладки `releases` начинается с выпуска, у `app` равен ему.
    совпало = bool(билд) and bool(выпуск) and (
        билд == выпуск if вид == "app" else билд.startswith(выпуск))
    голова_впереди = bool(р.get("есть")) and bool(выпуск) and (
        р["голова"] not in выпуск and выпуск.split("-")[0] not in р["голова"])
    return {
        "домен": домен,
        "site_id": ячейка.get("site_id") or "",
        "аккаунт": аккаунт,
        "раскладка": вид or "—",
        "установлено": выпуск or "—",
        "код": код or "—",
        "публичный_build": билд or "—",
        "совпало": совпало,
        "ветка": р.get("ветка", "—"),
        "голова": р.get("голова", "—"),
        "грязно": р.get("грязно", False),
        "голова_впереди": голова_впереди,
    }


def главная(argv: list[str]) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--json", action="store_true")
    р.add_argument("--domain", action="append", default=[])
    о = р.parse_args(argv[1:])

    строки = [строка(я) for я in ячейки()
              if not о.domain or (я.get("domain") in о.domain)]
    if о.json:
        print(json.dumps(строки, ensure_ascii=False, indent=2))
        return 0
    загл = (f"{'домен':24} {'site_id':14} {'раскл':9} {'установлено':26} "
            f"{'код':4} {'совп':5} {'ветка':44} {'голова':13}")
    print(загл)
    print("-" * len(загл))
    for с in строки:
        print(f"{с['домен']:24} {с['site_id']:14} {с['раскладка']:9} "
              f"{с['установлено']:26} {с['код']:4} "
              f"{'да' if с['совпало'] else 'НЕТ':5} {с['ветка'][:44]:44} "
              f"{с['голова']:13}{' грязно' if с['грязно'] else ''}")
    плохих = [с for с in строки if not с["совпало"]]
    print(f"\nячеек {len(строки)}, публичный build совпал с установленным "
          f"у {len(строки) - len(плохих)}")
    for с in плохих:
        print(f"   не совпало: {с['домен']} — код {с['код']}, "
              f"заголовок {с['публичный_build']}, установлено {с['установлено']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
