#!/usr/bin/env python3
"""Живы ли страницы, которые УЖЕ приносят поисковые визиты. Только чтение.

ЗАЧЕМ. Визиты получают от 0,05 до 3,75 % объявленных страниц, и эти страницы
— единственный измеренный источник реальных визитов сети. Сломанная страница
из этого набора стоит дороже любой правки каталога: она уже зарабатывала.
Поэтому проверяется не «всё ли работает вообще», а именно заработавший набор.

ЧТО ПРОВЕРЯЕТСЯ по каждому адресу набора:

* код ответа — 200 или нет;
* режим индексации страницы: `noindex` на странице, которая приносит визиты
  из поиска, — противоречие, и его надо видеть;
* наличие плеера: страница произведения без плеера для посетителя из поиска
  бесполезна (признак тот же, что в проверке сценариев);
* совпадение canonical с самим адресом — чтобы страница не отдавала вес
  другой.

ЯКОРЬ. Путь вида `/title/x/#watch` — это та же страница, что `/title/x/`:
якорь браузер на сервер не отправляет. Визиты якорных путей складываются с
визитами страницы, иначе одна страница считается дважды и у «якорного» адреса
canonical оказывается «не свой» по построению.

ОТБОР. Берутся адреса с НАИБОЛЬШИМ числом поисковых визитов за окно выгрузки:
они и есть «что мы можем потерять». Число задаётся ключом `--top`.

    python3 automation/local/earning-pages-health.py --domain animedia.icu
    python3 automation/local/earning-pages-health.py --top 40 --json
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import pathlib
import re
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ВЫГРУЗКА = pathlib.Path("/home/claude/wt-portable-site-cell-01/var/analytics"
                        "/cabinet-latest.json")
АГЕНТ = "factory-earning-health"


def посадочные(я: dict) -> collections.Counter:
    """{путь: визиты} по мере поисковых посадочных страниц."""
    мера = next((м for м in я.get("measurements") or []
                 if м.get("key") == "daily_search_landing_pages"
                 and м.get("measured")), None)
    итог: collections.Counter = collections.Counter()
    for с in (мера or {}).get("value") or []:
        путь = ""
        for и in с.get("dimensions") or []:
            текст = str((и or {}).get("name") or "")
            if текст.startswith("/") or "://" in текст:
                # Якорь на сервер не отправляется: `/title/x/#watch` — это
                # та же страница, что `/title/x/`. Визиты складываются.
                путь = текст.split("?", 1)[0].split("#", 1)[0]
                break
        if "://" in путь:
            путь = "/" + путь.split("/", 3)[-1] if путь.count("/") > 2 else "/"
        if not путь.startswith("/"):
            continue
        мет = с.get("metrics") or [0]
        итог[путь] += float(мет[-1] if len(мет) > 1 else мет[0])
    return итог


def проверить(домен: str, путь: str) -> dict:
    адрес = f"https://{домен}{путь}"
    р = subprocess.run(
        ["curl", "-sSL", "--compressed", "--max-time", "25", "-A", АГЕНТ,
         "-w", "\n%{http_code}", адрес],
        capture_output=True, text=True, timeout=50)
    текст = р.stdout
    код = текст.rsplit("\n", 1)[-1].strip() if "\n" in текст else "000"
    тело = текст.rsplit("\n", 1)[0] if "\n" in текст else ""
    мета = re.findall(r'<meta[^>]*name="robots"[^>]*content="([^"]*)"',
                      тело, re.I)
    канон = re.findall(r'<link[^>]*rel="canonical"[^>]*href="([^"]*)"',
                       тело, re.I)
    плеер = ("data-player" in тело or "playerjs" in тело.lower()
             or "<iframe" in тело.lower())
    свой_канон = bool(канон) and путь.rstrip("/") in канон[0].rstrip("/")
    return {
        "путь": путь, "код": код, "байт": len(тело),
        "robots": (мета[0] if мета else "нет"),
        "noindex": bool(мета) and "noindex" in мета[0].lower(),
        "плеер": плеер, "canonical_свой": свой_канон,
        "canonical": (канон[0][-60:] if канон else "нет"),
    }


def main(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", action="append", default=[])
    р.add_argument("--top", type=int, default=25)
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    if not ВЫГРУЗКА.is_file():
        print(f"НЕ ИЗМЕРЕНО: выгрузки нет: {ВЫГРУЗКА}", file=sys.stderr)
        return 2
    д = json.loads(ВЫГРУЗКА.read_text("utf-8"))
    из_очередей = {pathlib.Path(п).stem for п in
                   glob.glob(str(КОРЕНЬ / "config/domain-queues/*.json"))}
    домены = а.domain or sorted(из_очередей)
    всё = []
    плохих_всего = 0
    for я in д.get("domains") or []:
        домен = я.get("domain")
        if домен not in домены:
            continue
        верх = посадочные(я).most_common(а.top)
        if not верх:
            print(f"{домен}: посадочных страниц из поиска нет — проверять"
                  " нечего")
            continue
        строки = []
        for путь, визиты in верх:
            запись = проверить(домен, путь)
            запись["визиты"] = визиты
            запись["домен"] = домен
            строки.append(запись)
        плохие = [с for с in строки
                  if с["код"] != "200" or с["noindex"]
                  or not с["canonical_свой"]]
        без_плеера = [с for с in строки
                      if с["плеер"] is False and "/title/" in с["путь"]]
        плохих_всего += len(плохие)
        всё += строки
        потеря = sum(с["визиты"] for с in плохие)
        print(f"{домен}: проверено {len(строки)} верхних посадочных"
              f" (визитов в них {sum(с['визиты'] for с in строки):.0f})")
        print(f"   не 200 / noindex / чужой canonical: {len(плохие)}"
              f"{'' if not плохие else f' — визитов под угрозой {потеря:.0f}'}")
        print(f"   без плеера среди страниц произведений: {len(без_плеера)}")
        for с in (плохие + без_плеера)[:5]:
            print(f"      {с['путь'][:52]:<52} код {с['код']}"
                  f" robots {с['robots'][:14]} плеер"
                  f" {'есть' if с['плеер'] else 'НЕТ'}"
                  f" canonical {'свой' if с['canonical_свой'] else с['canonical']}")
    if а.json:
        print(json.dumps(всё, ensure_ascii=False, indent=1))
    print(f"ЗАВЕРШЕНО: адресов проверено {len(всё)}, с изъяном"
          f" {плохих_всего}", file=sys.stderr)
    return 1 if плохих_всего else 0


if __name__ == "__main__":
    sys.exit(main())
