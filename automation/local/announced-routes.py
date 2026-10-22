#!/usr/bin/env python3
"""Какие поверхности витрина ОБЪЯВЛЯЕТ о себе, и живы ли они. Только чтение.

Зачем именно так, а не подбором адресов. За одну смену 22.10 я пять раз
записала «поверхности нет», проверив адреса, которые придумала сама:

| что записала | чем оказалось |
| --- | --- |
| «разделов стран нет» (Zona) | `/catalog/?country=turciya` — 200, `index, follow` |
| то же (Lords) | и фасет, и чистый `/country/…`, canonical сведён |
| «маршрута анонсов нет вовсе» (Yummy) | `/catalog/announcement` и `/catalog/schedule` — обе 200 |
| «маршрут один, `/schedule`» (Yummy) | плюс `/catalog/top` со 100 карточками, `/catalog/anime-updates`, раздел `/posts` |
| «нет расписания и жанров» (Animedia) | `/schedule/` — 200 и 73 карточки, `/genres/` — 200 |

Общая причина у всех пяти одна: перечень адресов брался из головы, а не из
карты сайта витрины. Придуманный адрес отвечает 404, и из этого выводится
«поверхности нет» — вывод о МОЁМ незнании, выданный за вывод о витрине.

Поэтому инструмент берёт перечень ТОЛЬКО из карты и проверяет каждый адрес:
код, `robots`, canonical и число карточек. Он ничего не придумывает и ничего не
меняет.

    python3 automation/local/announced-routes.py yummyani.site
    python3 automation/local/announced-routes.py animedia.icu --json

Коды: 0 — все объявленные поверхности отвечают 200; 1 — есть мёртвые
(объявлено в карте, а страницы нет); 2 — карта не прочитана, то есть НЕ
ИЗМЕРЕНО, а не «поверхностей нет».
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

АГЕНТ = "factory-announced-routes"
#: Адреса произведений из перечня исключаются: их десятки тысяч, и вопрос не
#: про них. Шаблоны взяты из измеренных семейств: Yummy — `/anime/<slug>`,
#: остальные — `/title/<slug>/`.
КАРТОЧКА = re.compile(r"^/(?:anime|title)/[^/]+/?$")
#: Сколько поверхностей проверять. Предел называется в выводе: обрезанный
#: перечень, выглядящий полным, — та же ложь, что «проверено» без запуска.
СКОЛЬКО = 40


def достать(url: str, таймаут: int = 60) -> tuple[str, str]:
    try:
        р = subprocess.run(
            ["curl", "-sSL", "--max-time", str(таймаут),
             "-w", "\n@@%{http_code}", "-H", f"User-Agent: {АГЕНТ}", url],
            capture_output=True, text=True, timeout=таймаут + 30)
    except subprocess.TimeoutExpired:
        return "таймаут", ""
    т = р.stdout
    if "@@" not in т:
        return "—", т
    тело, код = т.rsplit("@@", 1)
    return код.strip(), тело


def части_карты(тело: str) -> list[str]:
    """Адреса частей из индекса карты. Пусто — карта не индексная."""
    return re.findall(r"<loc>([^<]*sitemap[^<]*)</loc>", тело)


def поверхности(тело: str, домен: str) -> list[str]:
    """Пути из карты, КРОМЕ адресов произведений. Чистая функция.

    Карточки исключаются по шаблону, а не по числу: «первые сто адресов» дали
    бы разный ответ на разных витринах.
    """
    пути = []
    for м in re.finditer(r"<loc>https?://[^/]+([^<]*)</loc>", тело):
        путь = м.group(1) or "/"
        if КАРТОЧКА.match(путь):
            continue
        if "sitemap" in путь:
            continue
        пути.append(путь)
    # порядок сохраняется, повторы убираются
    видели: set[str] = set()
    итог = []
    for п in пути:
        if п not in видели:
            видели.add(п)
            итог.append(п)
    return итог


def разобрать(тело: str) -> dict:
    роб = re.search(r'<meta name="robots" content="([^"]*)"', тело)
    кан = re.search(r'<link rel="canonical" href="([^"]*)"', тело)
    заг = re.search(r"<title>(.*?)</title>", тело, re.S)
    карточек = len({м.group(0) for м in
                    re.finditer(r'href="/(?:anime|title)/[a-z0-9-]+/?"',
                                тело)})
    return {
        "robots": роб.group(1) if роб else "—",
        "canonical": кан.group(1) if кан else "—",
        "title": (re.sub(r"\s+", " ", заг.group(1)).strip() if заг else ""),
        "карточек": карточек,
    }


def проверить(домен: str, предел: int = СКОЛЬКО) -> dict:
    код, тело = достать(f"https://{домен}/sitemap.xml")
    if код != "200":
        return {"домен": домен, "исход": "НЕ ИЗМЕРЕНО",
                "почему": f"карта отдала {код}", "поверхности": []}
    части = части_карты(тело)
    собрано = тело
    for часть in части[:3]:
        к, т = достать(часть)
        if к == "200":
            собрано += т
    пути = поверхности(собрано, домен)
    итог = []
    for путь in пути[:предел]:
        к, т = достать(f"https://{домен}{путь}", 30)
        запись = {"путь": путь, "код": к}
        if к == "200":
            запись.update(разобрать(т))
        итог.append(запись)
    return {"домен": домен, "исход": "измерено", "почему": "",
            "поверхности": итог, "всего_объявлено": len(пути)}


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("домены", nargs="+")
    р.add_argument("--json", action="store_true")
    р.add_argument("--limit", type=int, default=СКОЛЬКО)
    а = р.parse_args(аргв)

    итоги = [проверить(д, а.limit) for д in а.домены]
    if а.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=1))
    else:
        for и in итоги:
            if и["исход"] == "НЕ ИЗМЕРЕНО":
                print(f"{и['домен']}: НЕ ИЗМЕРЕНО — {и['почему']}."
                      f" Это предел измерения, а НЕ «поверхностей нет»")
                continue
            показано = len(и["поверхности"])
            всего = и["всего_объявлено"]
            print(f"=== {и['домен']}: объявлено поверхностей {всего},"
                  f" проверено {показано}"
                  + ("" if показано >= всего else
                     f" (перечень обрезан пределом {а.limit})"))
            for з in и["поверхности"]:
                if з["код"] != "200":
                    print(f"   {з['код']:>4} МЁРТВАЯ (объявлена в карте)"
                          f"  {з['путь']}")
                    continue
                print(f"   {з['код']:>4} robots {з['robots']:16}"
                      f" карточек {з['карточек']:4}  {з['путь']}")
                if з["title"]:
                    print(f"        «{з['title'][:64]}»")
    мёртвых = sum(1 for и in итоги for з in и["поверхности"]
                  if з["код"] != "200")
    if all(и["исход"] == "НЕ ИЗМЕРЕНО" for и in итоги):
        return 2
    return 1 if мёртвых else 0


if __name__ == "__main__":
    sys.exit(main())
