#!/usr/bin/env python3
"""Разделы, которые существуют, но с главной на них не попасть.

Страница без входящих внутренних ссылок для обхода почти не существует: её
находят только по карте, и вес ей ниоткуда не приходит. Проверка берёт
известные разделы семейства, спрашивает каждый у домена и сравнивает с тем,
на что ссылается главная.

Что считается ссылкой: `href` в разметке главной — меню, подвал, полки.
Что НЕ считается: упоминание в карте сайта (это не ссылка) и ссылки со
страниц, на которые с главной не попасть.

    python3 automation/local/orphan-sections-probe.py
    python3 automation/local/orphan-sections-probe.py animeg0.site
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"

#: Разделы, которые семейства вообще умеют отдавать. Список закрытый: гадать,
#: какие адреса «должны быть», нельзя — проверяется только то, что домен
#: действительно отдаёт.
КАНДИДАТЫ = ("/catalog/", "/new/", "/collections/", "/movies/", "/series/",
             "/anime/", "/dorama/", "/animation/", "/schedule/", "/search/")
ЗАМОРОЖЕННЫЕ = {"lordserials22.site", "lordserials22.space",
                "lordserial101.site", "lordfilm077.site"}


def домены() -> list[str]:
    j = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    список = j.get("cells") or []
    записи = список.values() if isinstance(список, dict) else список
    итог = []
    for з in записи:
        д = (з or {}).get("domain")
        if д and not д.endswith(".localhost") and not д.endswith(".localhost.test") \
                and д not in ЗАМОРОЖЕННЫЕ:
            итог.append(д)
    return sorted(set(итог))


def код(url: str) -> str:
    п = subprocess.run(["curl", "-sS", "--max-time", "30", "-o", "/dev/null",
                        "-w", "%{http_code}", url], capture_output=True, text=True)
    return (п.stdout or "0").strip()


def по_домену(домен: str) -> dict:
    html = subprocess.run(["curl", "-sS", "--max-time", "45",
                           f"https://{домен}/"],
                          capture_output=True, text=True).stdout or ""
    не_отвечает = not html
    # Вход в раздел — это не только <a href>. Поиск открывается ФОРМОЙ
    # (`<form action="/search/">`), и считать его «без входящих ссылок» —
    # ошибка предиката: измерено 2026-10-18, когда /search/ попал в сироты на
    # шестнадцати доменах подряд при живой форме поиска в шапке каждого.
    ссылки = set(re.findall(r'href="(/[a-z0-9_/-]*/?)"', html))
    ссылки |= set(re.findall(r'action="(/[a-z0-9_/-]*/?)"', html))
    # Адрес без завершающего слэша и с ним — один и тот же вход.
    ссылки |= {с + "/" for с in ссылки if not с.endswith("/")}
    живые, мёртвые, осиротевшие = [], [], []
    for путь in КАНДИДАТЫ:
        к = код(f"https://{домен}{путь}")
        if к == "200":
            живые.append(путь)
            if путь not in ссылки:
                осиротевшие.append(путь)
        elif к not in ("404", "301", "302"):
            мёртвые.append((путь, к))
    # Ноль найденных ссылок на живой главной означает, что разметка устроена
    # иначе (например ссылки собирает скрипт), а не что их нет. Выдавать это
    # за сиротство нельзя — измерено на пяти витринах Yummy.
    неизмеримо = (not не_отвечает) and len(ссылки) == 0
    return {"домен": домен, "не_отвечает": не_отвечает, "живые": живые,
            "осиротевшие": [] if неизмеримо else осиротевшие,
            "неизмеримо": неизмеримо, "ошибки": мёртвые,
            "ссылок_с_главной": len(ссылки)}


def главная(аргв: list[str]) -> int:
    цели = аргв or домены()
    with ThreadPoolExecutor(max_workers=4) as пул:
        итоги = list(пул.map(по_домену, цели))
    плохо = 0
    for и in итоги:
        if и["не_отвечает"]:
            print(f"  {и['домен']:22} НЕ ИЗМЕРЕНО: главная не ответила")
            continue
        if и.get("неизмеримо"):
            print(f"  {и['домен']:22} НЕ ИЗМЕРЕНО: на главной не нашлось ни "
                  f"одной ссылки — разметка устроена иначе")
            continue
        плохо += bool(и["осиротевшие"])
        метка = "✗" if и["осиротевшие"] else " "
        print(f"{метка} {и['домен']:22} разделов живых {len(и['живые']):2}, "
              f"ссылок с главной {и['ссылок_с_главной']:3}, "
              f"без входящей ссылки: "
              f"{', '.join(и['осиротевшие']) if и['осиротевшие'] else '—'}")
        for путь, к in и["ошибки"]:
            print(f"      {путь} отвечает {к}")
    print(f"\nдоменов с разделами без входящих ссылок: {плохо} из {len(итоги)}")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(главная(sys.argv[1:]))
