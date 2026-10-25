#!/usr/bin/env python3
"""Кто держит память узла — и какая витрина за этим стоит.

Зачем. Шлюз фонового редактора требует 2 048 МиБ свободной памяти
(`config/editor-run.json`, `resources.mem_available_min_mib`) и 25.10 отказывал
в запуске каждые пять минут: доступно 1 691–1 905 МиБ. Отказ сам по себе
правильный — он не тратит квоту на модель, — но редактор с 03:51Z не
опубликовал ничего, и это ОСТАНОВКА, а не экономия. Решение о памяти
принимает владелец, и ему нужен не «мало памяти», а перечень: сколько держит
каждая витрина и разрешается ли её домен.

Что делает. Читает `/proc/*/status` и `/proc/*/cmdline` (без внешних команд),
узнаёт витрину по пути `/srv/<ячейка>/releases/...`, сверяет домен с реестром
ячеек и проверяет его разрешение в DNS. Ничего не останавливает и не меняет:
остановка процесса — операция узла.

    python3 automation/local/node-memory-holders.py [--min-mib 60] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import socket
import sys

РЕЕСТР = pathlib.Path(__file__).resolve().parents[2] / "config" / "site-cells.json"
ПУТЬ_ВИТРИНЫ = re.compile(r"/srv/([A-Za-z0-9_.-]+)/releases/")


def процессы(порог_миб: int = 60, корень: pathlib.Path = pathlib.Path("/proc")) -> list[dict]:
    """Процессы с RSS не ниже порога: (миб, pid, команда)."""
    итог = []
    for п in корень.iterdir():
        if not п.name.isdigit():
            continue
        try:
            статус = (п / "status").read_text(encoding="utf-8", errors="replace")
            команда = (п / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", "replace").strip()
        except OSError:
            continue
        м = re.search(r"^VmRSS:\s+(\d+) kB", статус, re.M)
        if not м:
            continue
        миб = int(м.group(1)) // 1024
        if миб >= порог_миб:
            итог.append({"миб": миб, "pid": int(п.name), "команда": команда})
    return sorted(итог, key=lambda з: -з["миб"])


def ячейка_процесса(команда: str) -> str:
    """Имя каталога витрины из пути выпуска, иначе пустая строка."""
    м = ПУТЬ_ВИТРИНЫ.search(команда)
    return м.group(1) if м else ""


def домены(реестр: pathlib.Path | None = None) -> dict[str, str]:
    """Каталог витрины → домен. Берётся из реестра ячеек, а не угадывается."""
    try:
        д = json.loads((реестр or РЕЕСТР).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    итог = {}
    for я in д.get("cells") or []:
        домен = я.get("domain") or ""
        if not домен:
            continue
        дефисами = домен.replace(".", "-")
        # Каталоги выпусков названы по-разному: `animedia-icu`, `zonafilm12-site`
        # и `site-1lordserials1-online` — приставку «site-» носит часть витрин.
        итог[дефисами] = домен
        итог[f"site-{дефисами}"] = домен
        путь = ((я.get("repo") or {}).get("path") or "").rstrip("/")
        if путь:
            итог[путь.rsplit("/", 1)[-1]] = домен
        сид = я.get("site_id") or ""
        if сид:
            итог[сид] = домен
    return итог


def разрешается(домен: str, *, резолвер=None) -> bool | None:
    """True/False, либо None — проверить не удалось (не то же, что «нет домена»)."""
    если = резолвер or socket.gethostbyname
    try:
        если(домен)
        return True
    except socket.gaierror as ош:
        if getattr(ош, "errno", None) in (socket.EAI_NONAME, -2, -5):
            return False
        return None
    except OSError:
        return None


def вид(запись: dict) -> str:
    к = запись["команда"]
    if ячейка_процесса(к):
        return "витрина"
    if к.startswith("claude") or " claude " in к[:40]:
        return "сеанс claude"
    return "прочее"


def свод(записи: list[dict], карта: dict[str, str], *, резолвер=None) -> dict:
    по_виду: dict[str, int] = {}
    витрины: list[dict] = []
    for з in записи:
        в = вид(з)
        по_виду[в] = по_виду.get(в, 0) + з["миб"]
        кат = ячейка_процесса(з["команда"])
        if not кат:
            continue
        домен = карта.get(кат, "")
        витрины.append({"миб": з["миб"], "pid": з["pid"], "каталог": кат,
                        "домен": домен,
                        "разрешается": разрешается(домен, резолвер=резолвер) if домен else None})
    мёртвые = [в for в in витрины if в["разрешается"] is False]
    return {"по_виду": по_виду, "витрины": sorted(витрины, key=lambda з: -з["миб"]),
            "не_разрешаются": sorted(мёртвые, key=lambda з: -з["миб"]),
            "освободимо_миб": sum(в["миб"] for в in мёртвые)}


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--min-mib", type=int, default=60)
    р.add_argument("--json", type=pathlib.Path)
    а = р.parse_args(аргв)
    записи = процессы(а.min_mib)
    с = свод(записи, домены())
    доступно = None
    м = re.search(r"^MemAvailable:\s+(\d+) kB",
                  pathlib.Path("/proc/meminfo").read_text(encoding="utf-8"), re.M)
    if м:
        доступно = int(м.group(1)) // 1024
    print(f"процессов от {а.min_mib} МиБ: {len(записи)}; доступно памяти: "
          f"{доступно if доступно is not None else 'НЕ ИЗМЕРЕНО'} МиБ "
          f"(порог шлюза редактора 2048 МиБ)")
    print("держат по виду: " + ", ".join(f"{к} {v} МиБ" for к, v in
                                         sorted(с["по_виду"].items(), key=lambda п: -п[1])))
    print("\nвитрины:")
    for в in с["витрины"]:
        знак = {True: "разрешается", False: "НЕ РАЗРЕШАЕТСЯ",
                None: "не проверено"}[в["разрешается"]]
        print(f"  {в['миб']:5} МиБ  pid {в['pid']:>7}  {в['домен'] or в['каталог']:28} {знак}")
    неизвестных = [в for в in с["витрины"] if в["разрешается"] is None]
    if с["не_разрешаются"]:
        print(f"\nдержат память витрины без DNS: {с['освободимо_миб']} МиБ — "
              + ", ".join(f"{в['домен']} ({в['миб']} МиБ)" for в in с["не_разрешаются"]))
        if доступно is not None:
            print(f"остановка этих процессов дала бы {доступно + с['освободимо_миб']} МиБ "
                  f"при пороге 2048 МиБ. РЕШЕНИЕ ВЛАДЕЛЬЦА: инструмент ничего "
                  "не останавливает")
    elif неизвестных:
        # «Таких нет» и «проверить не удалось» — разные ответы, и путать их
        # нельзя: второй выдал бы отсутствие измерения за отсутствие проблемы.
        print(f"\nНЕ ИЗМЕРЕНО: у {len(неизвестных)} витрин домен или его "
              "разрешение не установлены — вывода об освободимой памяти нет")
    else:
        print("\nвитрин без DNS среди держателей памяти нет")
    if а.json:
        а.json.parent.mkdir(parents=True, exist_ok=True)
        а.json.write_text(json.dumps({"доступно_миб": доступно, **с},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"свод записан: {а.json}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
