#!/usr/bin/env python3
"""Гашение осиротевших стендов перед подъёмом нового.

    python3 automation/host/_orphan_stands.py [--tree <путь>] [--list]

Зачем это надёжнее `finally`
----------------------------

Повод измеренный, 28.10. Мой стенд `src/serve.py --port 18342` прожил 409
минут с ppid 1 и держал 598 МиБ; из-за него шлюз фонового редактора трижды не
запустился (`MemAvailable` 996 МиБ при пороге 2048). Все мои прогоны гасят
стенд в `finally`, и это не помогло: когда родитель умирает раньше (timeout,
kill, конец хода), `finally` не исполняется ВООБЩЕ, а стенд остаётся с ppid 1.
Сирота переживает `finally` по определению, поэтому уборка делается ПЕРЕД
подъёмом, а не после.

Что считается своим сиротой
---------------------------

Процесс той же учётной записи, у которого ppid равен 1, в команде есть
`serve.py`, `run.py` или `lords-frontend`, а рабочий каталог лежит внутри
указанного дерева. Чужие процессы (из рабочих каталогов других сессий) НЕ
трогаются: гасить чужое — не наше решение, их имена только печатаются.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import signal
import sys
import time

ПРИЗНАКИ = ("serve.py", "run.py", "lords-frontend")


def _сведения(п: pathlib.Path) -> dict | None:
    try:
        команда = (п / "cmdline").read_bytes().decode("utf-8", "replace")
        команда = команда.replace("\0", " ").strip()
        if not команда or not any(с in команда for с in ПРИЗНАКИ):
            return None
        if (п / "cmdline").stat().st_uid != os.getuid():
            return None
        ppid, rss = 0, 0
        for строка in (п / "status").read_text().splitlines():
            if строка.startswith("PPid:"):
                ppid = int(строка.split()[1])
            elif строка.startswith("VmRSS:"):
                rss = int(строка.split()[1]) // 1024
        cwd = os.readlink(п / "cwd") if (п / "cwd").exists() else ""
    except (OSError, ValueError, IndexError):
        return None
    return {"pid": int(п.name), "ppid": ppid, "rss": rss, "cwd": cwd,
            "команда": команда}


def найти(дерево: pathlib.Path) -> tuple[list[dict], list[dict]]:
    """Свои сироты и чужие сироты по отдельности."""
    свои, чужие = [], []
    for п in pathlib.Path("/proc").iterdir():
        if not п.name.isdigit():
            continue
        св = _сведения(п)
        if св is None or св["ppid"] != 1:
            continue
        (свои if str(дерево) in св["cwd"] else чужие).append(св)
    return свои, чужие


def погасить(дерево: pathlib.Path, печатать: bool = True) -> int:
    свои, чужие = найти(дерево)
    снято = 0
    for св in свои:
        if печатать:
            print(f"    | гашу осиротевший стенд pid {св['pid']} "
                  f"({св['rss']} МиБ): {св['команда'][:80]}")
        try:
            os.kill(св["pid"], signal.SIGTERM)
        except OSError:
            continue
        for _ in range(20):
            if not pathlib.Path(f"/proc/{св['pid']}").exists():
                break
            time.sleep(0.5)
        if pathlib.Path(f"/proc/{св['pid']}").exists():
            try:
                os.kill(св["pid"], signal.SIGKILL)
            except OSError:
                pass
        снято += 1
    if печатать and чужие:
        print(f"    | чужих осиротевших стендов {len(чужие)} — не трогаю: "
              + ", ".join(f"pid {с['pid']} ({с['rss']} МиБ)" for с in чужие[:3]))
    return снято


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--tree", default="/home/claude/wt-nova-publish-memory-02")
    р.add_argument("--list", action="store_true")
    а = р.parse_args()
    дерево = pathlib.Path(а.tree).resolve()
    if а.list:
        свои, чужие = найти(дерево)
        print(f"свои сироты: {len(свои)}, чужие: {len(чужие)}")
        for с in свои + чужие:
            свой = "свой " if str(дерево) in с["cwd"] else "чужой"
            print(f"  {свой} pid {с['pid']} RSS {с['rss']} МиБ: {с['команда'][:90]}")
        return 0
    print(f"погашено своих сирот: {погасить(дерево)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
