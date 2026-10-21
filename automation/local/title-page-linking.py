#!/usr/bin/env python3
"""Сколько ходов даёт страница произведения: ссылки на другие работы и серии.

Зачем это мерить отдельно от карты сайта. Карта говорит обходчику, ЧТО есть;
внутренние ссылки говорят, КУДА идти с конкретной страницы, и они же держат
глубину просмотра у посетителя. MOD-89 измерил у Yummy четыре ссылки на другие
произведения со страницы произведения и вдвое меньшую глубину просмотра, чем у
наших фронтендов, — но сравнить семейства между собой одной мерой до сих пор
было нечем.

По каждой витрине берутся первые работы с главной, и на их страницах
считается:

* **на другие работы** — различные ссылки на чужие карточки (не на себя);
* **на свои серии и сезоны** — ходы внутрь произведения;
* **хлебные крошки** — есть ли путь наверх, в раздел;
* **фасеты** — ссылки на жанр, год, страну: это ходы в каталог, а не в соседнюю
  работу, и считать их вместе с «другими работами» значило бы завысить связность.

Числа печатаются по каждой странице, а не средним: среднее по трём страницам
скрыло бы страницу-одиночку, а именно такие и выпадают из обхода.

    python3 automation/local/title-page-linking.py --all --pages 3
    python3 automation/local/title-page-linking.py --domain yummyani.biz
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

СЕМЕЙСТВА = {
    "lords": "lordserial33.biz",
    "zona": "zonafilm.space",
    "animedia": "animedia.space",
    "animego": "animeg0.site",
    "yummy": "yummyani.biz",
}


def достать(адрес: str, таймаут: int = 40) -> str | None:
    try:
        г = subprocess.run(["curl", "-sSL", "-w", "\n@@КОД@@%{http_code}",
                            "--max-time", str(таймаут), адрес],
                           capture_output=True, text=True, timeout=таймаут + 20)
    except subprocess.TimeoutExpired:
        return None
    тело, _, код = г.stdout.rpartition("@@КОД@@")
    return тело if код.strip() == "200" else None


def карточки(тело: str) -> list[str]:
    return sorted(set(re.findall(r'href="(/(?:title|anime)/[^"#?]+)"', тело)))


def разобрать(тело: str, свой: str) -> dict:
    все = карточки(тело)
    корень = свой.rstrip("/")
    другие = {а for а in все if not а.rstrip("/").startswith(корень)}
    серии = set(re.findall(
        re.escape(корень) + r"/(?:season-\d+/episode-\d+|season/\d+/episode/\d+)",
        тело))
    сезоны = set(re.findall(
        re.escape(корень) + r"/(?:season-\d+|season/\d+)(?![\w/])", тело))
    фасеты = set(re.findall(r'href="(/catalog/\?[^"]+|/genre/[^"]+|/year/[^"]+)"',
                            тело))
    крошки = bool(re.search(r'BreadcrumbList|class="[^"]*breadcrumb', тело))
    return {"на_другие_работы": len(другие), "на_свои_серии": len(серии),
            "на_свои_сезоны": len(сезоны), "на_фасеты": len(фасеты),
            "хлебные_крошки": крошки}


def проверить(домен: str, сколько: int) -> dict:
    итог: dict = {"домен": домен, "страницы": [], "замечания": []}
    главная = достать(f"https://{домен}/")
    if главная is None:
        итог["замечания"].append("главная не прочитана — НЕ ИЗМЕРЕНО")
        return итог
    пути = карточки(главная)[:сколько]
    if not пути:
        итог["замечания"].append("на главной нет карточек — мерить нечего")
        return итог
    for путь in пути:
        тело = достать(f"https://{домен}{путь}")
        if тело is None:
            итог["страницы"].append({"путь": путь, "итог": "не прочитана"})
            continue
        строка = разобрать(тело, путь)
        строка["путь"] = путь
        итог["страницы"].append(строка)
    измеренные = [с for с in итог["страницы"] if "на_другие_работы" in с]
    if измеренные:
        минимум = min(с["на_другие_работы"] for с in измеренные)
        итог["минимум_на_другие"] = минимум
        if минимум == 0:
            итог["замечания"].append(
                "есть страница без ни одной ссылки на другую работу:"
                " с неё обходчику и посетителю идти некуда")
        if not any(с["хлебные_крошки"] for с in измеренные):
            итог["замечания"].append("хлебных крошек нет ни на одной странице")
    return итог


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", action="append", default=[])
    р.add_argument("--all", action="store_true")
    р.add_argument("--pages", type=int, default=3)
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    домены = а.domain or (list(СЕМЕЙСТВА.values()) if а.all else [])
    if not домены:
        print("не названо ни одной витрины: --domain или --all")
        return 2
    итоги = [проверить(д, а.pages) for д in домены]
    if а.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=1))
        return 0
    print(f"{'витрина':20} {'страница':34} {'другие':>7} {'серии':>6}"
          f" {'сезоны':>7} {'фасеты':>7} крошки")
    for и in итоги:
        for с in и["страницы"]:
            if "на_другие_работы" not in с:
                print(f"{и['домен']:20} {с['путь'][:34]:<34} {с['итог']}")
                continue
            print(f"{и['домен']:20} {с['путь'][:34]:<34}"
                  f" {с['на_другие_работы']:>7} {с['на_свои_серии']:>6}"
                  f" {с['на_свои_сезоны']:>7} {с['на_фасеты']:>7}"
                  f" {'есть' if с['хлебные_крошки'] else 'НЕТ'}")
        for з in и["замечания"]:
            print(f"{'':20} → {з}")
    return 1 if any(и["замечания"] for и in итоги) else 0


if __name__ == "__main__":
    sys.exit(main())
