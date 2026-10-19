#!/usr/bin/env python3
"""Каждый ли проверенный текст дошёл до своей витрины. Только чтение.

Повод (19.10): в реестре оператора содержания 640 записей `READY_VERIFIED`, и
на yummyani.site шесть из 188 не числятся ни в накладке, ни в черновиках, ни в
журнале витрины — то есть никогда не доставлялись, хотя в реестре помечены
проверенными с пустым `published_at` (MOD-88). Такое состояние неразличимо с
«ждёт очереди», поэтому его надо видеть по всей сети, а не на одном домене.

Ключ сверки — **slug из `canonical_url`**, и только он. У adapter animedia в
`title_id` лежит slug, а у yummyani — UUID; сверка по `title_id` даёт ложные
«172 вне накладки» (эта ошибка уже сделана и исправлена).

Где лежит наш учёт: у приложения (animedia, animego, yummy) — накладка
`title-overlays.json`, у adapter lords — наш учёт `published.json`. Нет ни того,
ни другого — «не измерено» с причиной.

    python3 automation/local/content-registry-vs-live.py
    python3 automation/local/content-registry-vs-live.py --live --limit 6
    python3 automation/local/content-registry-vs-live.py --json

`--live` дополнительно открывает страницы недостающих и проверяет, нет ли текста
на них (на случай, если он доставлен другим путём).

Коды: 0 — все проверенные тексты на месте; 1 — есть недостающие; 2 — не измерено.
"""
from __future__ import annotations

import argparse
import collections
import html as _html
import json
import pathlib
import re
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

from factory.qwen import registry  # noqa: E402

РЕЕСТР = pathlib.Path("/var/lib/seo-content-operator/registry.json")
ГОТОВ = "READY_VERIFIED"


def slug_записи(и: dict) -> str:
    адрес = str(и.get("canonical_url") or "")
    хвост = адрес.rstrip("/").rsplit("/", 1)[-1]
    return хвост or ""


def из_реестра(путь: pathlib.Path) -> tuple[dict[str, list[dict]], str]:
    try:
        д = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError) as сбой:
        return {}, f"реестр не прочитан: {сбой}"
    по_домену: dict[str, list[dict]] = collections.defaultdict(list)
    for и in д.get("items") or []:
        if и.get("status") != ГОТОВ:
            continue
        домен = str(и.get("target_site") or "")
        if домен and slug_записи(и):
            по_домену[домен].append(и)
    if not по_домену:
        return {}, f"в реестре нет записей со статусом {ГОТОВ}"
    return dict(по_домену), ""


def наш_учёт(домен: str, сайты: dict) -> tuple[set[str], str]:
    s = сайты.get(домен)
    if s is None:
        return set(), "домена нет в реестре ячеек"
    живой = pathlib.Path(registry.путь_доставки(s))
    каталог = pathlib.Path(registry.корень_хранилища(s.adapter)) / домен
    источник = живой if живой.name == "title-overlays.json" else каталог / "published.json"
    try:
        д = json.loads(источник.read_text(encoding="utf-8"))
    except (OSError, ValueError) as сбой:
        return set(), f"{источник.name}: {сбой}"
    записи = д.get("items")
    if not isinstance(записи, list):
        return set(), f"{источник.name}: нет списка items"
    return {str(и.get("slug")) for и in записи
            if isinstance(и, dict) and и.get("slug")}, ""


def на_странице(адрес: str, тело: str) -> tuple[bool | None, str]:
    отрезок = re.sub(r"<[^>]+>", "", тело).strip()[:60]
    if not отрезок:
        return None, "тело записи пусто"
    г = subprocess.run(["curl", "-sSL", "-w", "\n%{http_code}", "--max-time", "30", адрес],
                       capture_output=True, text=True)
    if г.returncode != 0:
        return None, f"curl код {г.returncode}"
    страница, код = г.stdout.rsplit("\n", 1)[0], г.stdout.rsplit("\n", 1)[-1].strip()
    if код != "200":
        return None, f"код ответа {код}"
    return отрезок in _html.unescape(страница), ""


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="проверенные тексты против витрин")
    р.add_argument("--file", default=str(РЕЕСТР))
    р.add_argument("--domain", action="append", default=[])
    р.add_argument("--live", action="store_true", help="открыть страницы недостающих")
    р.add_argument("--limit", type=int, default=6, help="сколько недостающих печатать")
    р.add_argument("--json", action="store_true")
    дов = р.parse_args(аргв)

    по_домену, беда = из_реестра(pathlib.Path(дов.file))
    if беда:
        print(f"НЕ ИЗМЕРЕНО: {беда}")
        return 2
    сайты = {s.domain: s for s in registry.собрать(опрашивать_сеть=False)}
    итоги = {}
    for домен, записи in sorted(по_домену.items()):
        if дов.domain and домен not in дов.domain:
            continue
        слаги, беда_у = наш_учёт(домен, сайты)
        if беда_у:
            итоги[домен] = {"измерено": False, "почему": беда_у,
                            "проверенных": len(записи)}
            continue
        нет = [и for и in записи if slug_записи(и) not in слаги]
        итоги[домен] = {
            "измерено": True,
            "проверенных": len(записи),
            "в_учёте": len(записи) - len(нет),
            "недостающие": [slug_записи(и) for и in нет],
        }
        if дов.live and нет:
            живые = []
            for и in нет[:дов.limit]:
                видно, почему = на_странице(str(и.get("canonical_url") or ""),
                                            str(и.get("body") or ""))
                живые.append({"slug": slug_записи(и), "на_странице": видно,
                              "почему": почему})
            итоги[домен]["живая_проверка"] = живые

    if дов.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=2))
    else:
        for домен in sorted(итоги):
            и = итоги[домен]
            if not и["измерено"]:
                print(f"{домен:22} НЕ ИЗМЕРЕНО — {и['почему']}"
                      f" (проверенных в реестре {и['проверенных']})")
                continue
            метка = "" if not и["недостающие"] else "  ← НЕДОСТАЮЩИЕ"
            print(f"{домен:22} проверенных {и['проверенных']:4},"
                  f" в учёте {и['в_учёте']:4}, недостающих"
                  f" {len(и['недостающие']):3}{метка}")
            for s in и["недостающие"][:дов.limit]:
                print(f"      {s}")
            for ж in и.get("живая_проверка") or []:
                состояние = {True: "текст на странице ЕСТЬ",
                             False: "текста на странице нет",
                             None: f"не измерено: {ж['почему']}"}[ж["на_странице"]]
                print(f"      живая проверка {ж['slug']}: {состояние}")
    измерены = [и for и in итоги.values() if и["измерено"]]
    недостающих = sum(len(и["недостающие"]) for и in измерены)
    проверенных = sum(и["проверенных"] for и in измерены)
    print()
    print(f"домены: измерено {len(измерены)} из {len(итоги)};"
          f" проверенных текстов {проверенных}; недостающих {недостающих}")
    if not измерены:
        return 2
    return 1 if недостающих else 0


if __name__ == "__main__":
    sys.exit(main())
