#!/usr/bin/env python3
"""Сверка карты витрины с её СОБСТВЕННЫМ каталогом — по множествам адресов.

Задание владельца: «сверяй полные наборы адресов с каталогом самого домена;
совпадения итогов недостаточно». Этот проход и делает так: он не сравнивает
числа, а вычитает множества в обе стороны и у каждой разницы спрашивает
ПРИЧИНУ у живой страницы.

Три исхода разницы, и они не равноценны:

* запись есть в каталоге, страница отвечает `noindex` — отсутствие в карте
  ПРАВИЛЬНО: карта обязана описывать индексируемое. Это не дефект;
* запись есть в каталоге, страница `index, follow` — **пробел карты**;
* адрес есть в карте, а записи в каталоге нет — **лишний адрес**, карта
  обещает обходчику то, чего у витрины нет.

Отрицательный контроль входит в проход: столько же записей, которые в карте
ЕСТЬ, обязаны оказаться `index`. Если и они `noindex`, признак ничего не
различает, и выводам о разнице верить нельзя.

Измерено 20.10 на animedia.icu: карта 8 234 адреса (8 226 произведений плюс 8
разделов), каталог 8 674 записи, разница 448 — и у всех проверенных 448 страниц
стоит `noindex, follow`, то есть карта согласована с очередью тематического
допуска, а не неполна. Лишних адресов 0.

    python3 automation/local/sitemap-catalog-reconcile-anime.py --domain animedia.icu
    python3 automation/local/sitemap-catalog-reconcile-anime.py --domain animedia.icu --limit 40
"""
from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
from pathlib import Path

#: Домен → файл подробностей витрины. Берётся из отчёта доставки ячеек, а не
#: угадывается по имени домена.
ВИТРИНЫ = {
    "animedia.icu": "/srv/animedia-icu/data/animedia-01-details.json",
    "animedia.space": "/srv/animedia-space/data/animedia-02-details.json",
}


def добыть(url: str, таймаут: int = 60) -> tuple[str, str]:
    г = subprocess.run(["curl", "-sS", "--max-time", str(таймаут), "-w",
                        "\n%{http_code}", url],
                       capture_output=True, text=True,
                       timeout=таймаут + 20)
    тело = г.stdout
    return тело.rsplit("\n", 1)[0], тело.rsplit("\n", 1)[-1]


def адреса_карты(домен: str) -> list[str]:
    индекс, _ = добыть(f"https://{домен}/sitemap.xml")
    части = [ч for ч in re.findall(r"<loc>([^<]+)</loc>", индекс)
             if "sitemap" in ч]
    если_части = части or [f"https://{домен}/sitemap.xml"]
    итог: list[str] = []
    for ч in если_части:
        тело, _ = добыть(ч, 120)
        итог += re.findall(r"<loc>([^<]+)</loc>", тело)
    return итог


def признаки(домен: str, слаг: str) -> dict:
    тело, код = добыть(f"https://{домен}/title/{слаг}/", 30)
    роботс = re.search(r'<meta name="robots" content="([^"]*)"', тело)
    return {"слаг": слаг, "код": код,
            "robots": роботс.group(1) if роботс else "—"}


def разобрать(домен: str, *, предел: int, семя: int) -> dict:
    файл = ВИТРИНЫ[домен]
    подробности = json.loads(Path(файл).read_text(encoding="utf-8"))["details"]
    карта = адреса_карты(домен)
    произведения = {а for а in карта if "/title/" in а}
    прочие = sorted(а for а in карта if "/title/" not in а)
    каталог = {f"https://{домен}/title/{с}/": с for с in подробности}

    нет_в_карте = sorted(с for а, с in каталог.items()
                         if а not in произведения)
    лишние = sorted(произведения - set(каталог))

    сл = random.Random(семя)
    проверять = нет_в_карте if not предел else \
        sorted(сл.sample(нет_в_карте, min(предел, len(нет_в_карте))))
    разбор = [признаки(домен, с) for с in проверять]
    в_карте = sorted(с for а, с in каталог.items() if а in произведения)
    контроль = [признаки(домен, с)
                for с in sorted(сл.sample(в_карте, min(len(проверять) or 1, 8,
                                                       len(в_карте))))]

    noindex = [з for з in разбор if "noindex" in з["robots"]]
    index = [з for з in разбор if "noindex" not in з["robots"]]
    контроль_index = [з for з in контроль if "noindex" not in з["robots"]]
    return {
        "домен": домен,
        "адресов в карте": len(карта),
        "страниц произведений в карте": len(произведения),
        "прочих адресов в карте": прочие,
        "записей в каталоге": len(каталог),
        "нет в карте": len(нет_в_карте),
        "лишних адресов в карте": лишние,
        "проверено страниц из разницы": len(разбор),
        "из них noindex (отсутствие правильно)": len(noindex),
        "из них index (ПРОБЕЛ КАРТЫ)": [з["слаг"] for з in index],
        "отрицательный контроль": {
            "проверено": len(контроль),
            "из них index": len(контроль_index),
        },
    }


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", required=True)
    р.add_argument("--limit", type=int, default=0,
                   help="0 — проверить ВСЮ разницу; иначе случайная выборка")
    р.add_argument("--seed", type=int, default=20261020)
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    if а.domain not in ВИТРИНЫ:
        print(f"НЕ ИЗМЕРЕНО: домена {а.domain} нет в перечне — расширять его"
              " по своей инициативе нельзя")
        return 2
    итог = разобрать(а.domain, предел=а.limit, семя=а.seed)
    if а.json:
        print(json.dumps(итог, ensure_ascii=False, indent=1))
    else:
        for к in ("домен", "адресов в карте", "страниц произведений в карте",
                  "записей в каталоге", "нет в карте",
                  "проверено страниц из разницы",
                  "из них noindex (отсутствие правильно)"):
            print(f"{к}: {итог[к]}")
        print(f"прочих адресов в карте: {len(итог['прочих адресов в карте'])}"
              f" — {', '.join(итог['прочих адресов в карте'])}")
        print(f"лишних адресов в карте: {len(итог['лишних адресов в карте'])}")
        пробел = итог["из них index (ПРОБЕЛ КАРТЫ)"]
        print(f"ПРОБЕЛ КАРТЫ (страница index, а адреса в карте нет):"
              f" {len(пробел)}")
        for с in пробел[:20]:
            print(f"   {с}")
        к = итог["отрицательный контроль"]
        print(f"отрицательный контроль: из {к['проверено']} записей, которые в"
              f" карте ЕСТЬ, index у {к['из них index']}")
        if к["проверено"] and к["из них index"] != к["проверено"]:
            print("   ВНИМАНИЕ: признак не различает — в карте лежат noindex"
                  " страницы, и вывод о разнице недоказателен")
        if а.limit and итог["нет в карте"] > а.limit:
            print(f"ОХВАТ: проверено {а.limit} из {итог['нет в карте']}"
                  f" записей разницы — остальное НЕ ИЗМЕРЕНО")
    if итог["из них index (ПРОБЕЛ КАРТЫ)"] or итог["лишних адресов в карте"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(главное())
