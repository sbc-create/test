#!/usr/bin/env python3
"""Повторяет ли РЕДАКЦИОННЫЙ текст неверный год каталога. Только чтение.

Повод — требование задания по MOD-102: «проверь согласованность источника,
каталога, отображения и редакционных текстов. Ошибочное поле каталога нельзя
использовать для принудительного внесения ошибки в текст».

Если описание называет неверный год СЛОВАМИ, правка поля каталога его не
исправит, и поправка года закроет только часть дефекта. Проверяется это по
каждой поправке отдельно, и ровно на тех поверхностях, где живёт редакционный
текст:

* `meta name="description"` — то, что видит поиск в сниппете;
* `description` в JSON-LD — тот же текст в структурированных данных.

Отдельно печатается `datePublished` из JSON-LD: это ПРОИЗВОДНОЕ от поля
каталога, а не текст. Если там стоит неверный год, его исправит та же поправка —
и это надо знать, потому что структурированные данные поиск читает буквально.

ЧЕГО ЭТА ПРОВЕРКА НЕ ДЕЛАЕТ, и это исправление её же первой редакции. Сначала
год искался во всём видимом тексте страницы — и проверка объявила «оба года в
тексте» у 12 записей из 15. Разбор показал, откуда брались числа: из блока
«Похожее аниме» (годы ДРУГИХ произведений) и из подвала со списком годов
(«Годы 2026 2025 2024 2023 2022»). То есть признак отвечал одно и то же почти
везде и к описанию отношения не имел.

    python3 automation/local/year-text-consistency.py --site animedia-01
"""
from __future__ import annotations

import argparse
import html as _html
import json
import pathlib
import re
import subprocess
import sys

АГЕНТ = "factory-year-text-consistency"

ПОПРАВКИ = pathlib.Path("/home/claude/wt-nova-publish-memory-02/config/"
                        "anime-year-corrections.json")
ДОМЕНЫ = {"animedia-01": "animedia.icu", "animedia-02": "animedia.space"}


def достать(адрес: str, таймаут: int = 40) -> str | None:
    try:
        г = subprocess.run(["curl", "-A", АГЕНТ, "-sSL", "-w", "\n@@КОД@@%{http_code}",
                            "--max-time", str(таймаут), адрес],
                           capture_output=True, text=True, timeout=таймаут + 20)
    except subprocess.TimeoutExpired:
        return None
    тело, _, код = г.stdout.rpartition("@@КОД@@")
    return тело if код.strip() == "200" else None


def редакционный_текст(тело: str) -> str:
    """Только описание: meta description и `description` из JSON-LD."""
    части = []
    м = re.search(r'<meta name="description" content="([^"]*)"', тело)
    if м:
        части.append(_html.unescape(м.group(1)))
    for блок in re.findall(
            r'<script type="application/ld\+json"[^>]*>(.*?)</script>', тело, re.S):
        try:
            d = json.loads(блок)
        except json.JSONDecodeError:
            continue
        for узел in (d if isinstance(d, list) else [d]):
            if isinstance(узел, dict) and isinstance(узел.get("description"), str):
                части.append(узел["description"])
    return " ".join(части)


def дата_разметки(тело: str) -> str:
    for блок in re.findall(
            r'<script type="application/ld\+json"[^>]*>(.*?)</script>', тело, re.S):
        try:
            d = json.loads(блок)
        except json.JSONDecodeError:
            continue
        for узел in (d if isinstance(d, list) else [d]):
            if isinstance(узел, dict) and узел.get("datePublished"):
                return str(узел["datePublished"])
    return ""


def проверить(site_id: str) -> dict:
    домен = ДОМЕНЫ[site_id]
    d = json.loads(ПОПРАВКИ.read_text(encoding="utf-8"))
    итог: dict = {"site_id": site_id, "домен": домен, "записи": []}
    for п in d.get("corrections") or []:
        слаг = п.get("slug_at_measure") or ""
        неверный = str(п.get("year_provider") or "").strip()
        верный = str(п.get("year_source") or "").strip()
        строка = {"слаг": слаг, "год_поставщика": неверный or "—",
                  "год_источника": верный or "—"}
        if not неверный or not верный:
            # Пустой год сравнивать нечем. Первая редакция подставляла пустую
            # строку в регулярное выражение, и `\b\b` совпадал с чем угодно —
            # запись получала вердикт «оба года в тексте» на пустом месте.
            #
            # Чаще всего это поправка ВИДА (`type_provider`/`type_source`), а
            # не года: называть её «не измерено» значило бы записать в пробел
            # то, что просто не про год.
            вид = bool(п.get("type_source") or п.get("type_provider"))
            строка["итог"] = ("поправка ВИДА, а не года — к тексту о годе не"
                              " относится" if вид
                              else "год в поправке не назван — НЕ ИЗМЕРЕНО")
            итог["записи"].append(строка)
            continue
        тело = достать(f"https://{домен}/title/{слаг}/")
        if тело is None:
            строка["итог"] = "страница не прочитана"
            итог["записи"].append(строка)
            continue
        текст = редакционный_текст(тело)
        строка["символов_текста"] = len(текст)
        строка["datePublished"] = дата_разметки(тело) or "—"
        есть_неверный = bool(re.search(rf"\b{re.escape(неверный)}\b", текст))
        есть_верный = bool(re.search(rf"\b{re.escape(верный)}\b", текст))
        if not текст:
            строка["итог"] = "редакционного текста на странице нет"
        elif есть_неверный and есть_верный:
            строка["итог"] = "в тексте оба года — разбирать глазами"
        elif есть_неверный:
            строка["итог"] = "ТЕКСТ НЕСЁТ НЕВЕРНЫЙ ГОД"
        elif есть_верный:
            строка["итог"] = "текст несёт верный год"
        else:
            строка["итог"] = "текст года не называет"
        итог["записи"].append(строка)
    return итог


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", default="animedia-01", choices=sorted(ДОМЕНЫ))
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    итог = проверить(а.site)
    if а.json:
        print(json.dumps(итог, ensure_ascii=False, indent=1))
        return 0
    счёт: dict = {}
    в_разметке = 0
    for з in итог["записи"]:
        счёт[з["итог"]] = счёт.get(з["итог"], 0) + 1
        дата = з.get("datePublished", "—")
        # Пустой год поставщика нельзя считать совпадением: `startswith("")`
        # верно для любой строки, и первая редакция печатала «(неверный)» даже
        # там, где сравнивать было нечего.
        если_неверная = (з["год_поставщика"] != "—"
                         and дата.startswith(з["год_поставщика"]))
        в_разметке += 1 if если_неверная else 0
        print(f"   {з['слаг'][:42]:<42} поставщик {з['год_поставщика']:>4}"
              f" источник {з['год_источника']:>4}"
              f" | datePublished {дата:>10}"
              f"{' (неверный)' if если_неверная else ''} | {з['итог']}")
    print(f"\n{итог['домен']}: записей {len(итог['записи'])}")
    for имя, сколько in sorted(счёт.items(), key=lambda x: -x[1]):
        print(f"   {сколько:3} {имя}")
    print(f"   {в_разметке:3} записей несут неверный год в JSON-LD"
          f" (`datePublished`) — это производное от поля каталога,"
          f" и его исправит та же поправка")
    return 1 if счёт.get("ТЕКСТ НЕСЁТ НЕВЕРНЫЙ ГОД") else 0


if __name__ == "__main__":
    sys.exit(main())
