#!/usr/bin/env python3
"""Есть ли в карте сайта страницы, на которые поиск уже приводит людей.

Зачем именно так. Карта «есть» и карта «называет нужные страницы» — разные
вещи. На yummyani.site карта серий отдаёт 1 663 адреса и `lastmod` индекса
2026-08-21, а пять страниц серий ДжоДжо, которые дают **66 % поисковых входов
витрины**, в ней отсутствуют; на соседней yummyani.org те же пять страниц есть,
и адресов там 50 000. Поэтому проверка идёт не по размеру карты, а по спросу:
берутся страницы входа из выгрузки кабинета и ищутся в картах.

Что печатается: свежесть индекса карты, размер каждой дочерней карты, и по
каждой верхней странице входа — числится ли она в картах.

Третий исход обязателен: карта не отдалась или в выгрузке нет страниц входа —
«не измерено» с причиной, а не «покрытие полное».

    python3 automation/local/sitemap-demand-coverage.py --domain yummyani.site
    python3 automation/local/sitemap-demand-coverage.py --domain yummyani.site --top 10 --json

Коды: 0 — все проверенные страницы спроса в карте; 1 — есть отсутствующие;
2 — не измерено.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse

ВЫГРУЗКА = pathlib.Path(
    "/home/claude/wt-portable-site-cell-01/var/analytics/cabinet-latest.json")


def _достать(адрес: str, предел: int = 60) -> tuple[str, str]:
    г = subprocess.run(["curl", "-sS", "-w", "\n%{http_code}", "--max-time", str(предел),
                        адрес], capture_output=True, text=True)
    if г.returncode != 0:
        return "", f"curl код {г.returncode}"
    т = г.stdout
    тело, код = т.rsplit("\n", 1)[0], т.rsplit("\n", 1)[-1].strip()
    if код != "200":
        return "", f"код ответа {код}"
    return тело, ""


def карты(домен: str) -> tuple[dict, str]:
    """{имя карты: (адресов, текст)} плюс lastmod индекса."""
    индекс, беда = _достать(f"https://{домен}/sitemap.xml")
    if беда:
        return {}, f"индекс карты: {беда}"
    записи = re.findall(r"<loc>(.*?)</loc>\s*(?:<lastmod>(.*?)</lastmod>)?", индекс)
    если_пусто = not записи
    if если_пусто:
        return {}, "в индексе карты нет записей"
    итог: dict[str, dict] = {"_индекс": {
        "карт": len(записи),
        "lastmod": sorted({lm[:10] for _, lm in записи if lm}),
    }}
    for адрес, _ in записи:
        тело, беда = _достать(адрес)
        имя = адрес.rsplit("/", 1)[-1]
        итог[имя] = {"адресов": len(re.findall(r"<loc>", тело)) if тело else 0,
                     "текст": тело, "почему": беда}
    return итог, ""


def страницы_спроса(выгрузка: pathlib.Path, домен: str, верх: int) -> tuple[list, str]:
    try:
        д = json.loads(выгрузка.read_text(encoding="utf-8"))
    except (OSError, ValueError) as сбой:
        return [], f"выгрузка не прочитана: {сбой}"
    цели = [x for x in д.get("domains") or [] if x.get("domain") == домен]
    if not цели:
        return [], f"домена {домен} в выгрузке нет"
    мера = next((м for м in цели[0].get("measurements") or []
                 if м.get("key") == "search_landing_pages"), None)
    if мера is None or not мера.get("measured"):
        причина = (мера or {}).get("state") or "показателя нет"
        return [], f"страницы входа: {причина}"
    строки = []
    for стр in мера.get("value") or []:
        изм = стр.get("dimensions") or []
        мет = стр.get("metrics") or []
        if len(изм) < 2 or not мет:
            continue
        if str((изм[0] or {}).get("id") or "") != "organic":
            continue
        путь = str((изм[1] or {}).get("name") or "")
        if путь in ("/", "") or not путь.startswith("/"):
            continue  # главная в карте есть всегда и спроса на проверку не создаёт
        строки.append((float(мет[0] or 0), путь))
    строки.sort(reverse=True)
    return строки[:верх], ""


def в_карте(путь: str, карты_: dict) -> list[str]:
    """Имена карт, где адрес найден. Сравнение по ГРАНИЦЕ адреса.

    Подстрочный поиск здесь обманывает: `/anime/x` входит в
    `/anime/x/season/1/episode/2`, и страница тайтла выглядела бы покрытой
    картой серий, которой в ней нет. Поэтому путь обязан заканчиваться вместе
    с адресом: `</loc>` или `"` сразу после него, с необязательным слешем.
    """
    без_слеша = путь.rstrip("/")
    варианты = {без_слеша, urllib.parse.quote(без_слеша, safe="/:?=&")}
    шаблоны = [re.compile(re.escape(в) + r'/?(?=</loc>|["\s<])') for в in варианты if в]
    найдено = []
    for имя, сведения in карты_.items():
        if имя.startswith("_"):
            continue
        текст = сведения.get("текст") or ""
        if any(ш.search(текст) for ш in шаблоны):
            найдено.append(имя)
    return найдено


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="покрытие картой страниц со спросом")
    р.add_argument("--domain", required=True)
    р.add_argument("--top", type=int, default=8)
    р.add_argument("--file", default=str(ВЫГРУЗКА))
    р.add_argument("--json", action="store_true")
    дов = р.parse_args(аргв)

    спрос, беда_с = страницы_спроса(pathlib.Path(дов.file), дов.domain, дов.top)
    карты_, беда_к = карты(дов.domain)
    if беда_к:
        print(f"НЕ ИЗМЕРЕНО: {беда_к}")
        return 2
    if беда_с:
        print(f"НЕ ИЗМЕРЕНО: {беда_с}")
        return 2
    if not спрос:
        print("НЕ ИЗМЕРЕНО: страниц входа из поиска в выгрузке нет")
        return 2

    итоги = []
    for визиты, путь in спрос:
        где = в_карте(путь, карты_)
        итоги.append({"путь": путь, "визиты": визиты, "в_картах": где})

    индекс = карты_["_индекс"]
    if дов.json:
        print(json.dumps({"домен": дов.domain, "индекс": индекс,
                          "карты": {к: v["адресов"] for к, v in карты_.items()
                                    if not к.startswith("_")},
                          "страницы": итоги}, ensure_ascii=False, indent=2))
    else:
        print(f"{дов.domain}: карт в индексе {индекс['карт']},"
              f" lastmod индекса {', '.join(индекс['lastmod']) or 'нет'}")
        for имя, св in карты_.items():
            if имя.startswith("_"):
                continue
            хвост = f" ({св['почему']})" if св.get("почему") else ""
            print(f"   {имя:20} адресов {св['адресов']}{хвост}")
        print("   страницы со спросом:")
        for и in итоги:
            метка = ", ".join(и["в_картах"]) if и["в_картах"] else "НЕТ НИ В ОДНОЙ КАРТЕ"
            print(f"      {и['визиты']:7.0f}  {метка:28} {и['путь'][:60]}")
    нет = [и for и in итоги if not и["в_картах"]]
    визиты_без = sum(и["визиты"] for и in нет)
    всего = sum(и["визиты"] for и in итоги)
    print()
    print(f"страниц проверено {len(итоги)}; вне карт {len(нет)};"
          f" визитов за ними {визиты_без:.0f} из {всего:.0f}"
          f" ({100 * визиты_без / всего if всего else 0:.0f} %)")
    return 1 if нет else 0


if __name__ == "__main__":
    sys.exit(main())
