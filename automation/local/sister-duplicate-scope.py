#!/usr/bin/env python3
"""Сколько страниц семейства несут описание соседа ДОСЛОВНО.

Зачем. Измерено 25.10: слой различия по домену в рантайме не даёт ничего —
провайдерское описание приходит на витрины-сёстры одинаковым, и единственное,
что их различает, это размещённый редакционный текст. Значит охват дублей
считается просто: страница, у которой НЕТ редакционного текста ни на одной
витрине семейства, стоит с описанием соседа дословно.

Инструмент считает это со знаменателем и проверяет саму посылку выборкой
живых страниц — потому что «нет текста в хранилище» это не то же самое, что
«описания совпали»: первое читается с диска, второе проверяется у витрины.

Два источника, оба обязательны:

* карта сайта первой витрины — перечень слагов (не придумывается, берётся у
  витрины);
* хранилище размещения каждой витрины (`title-overlays.json`, у него `items`
  бывает и списком, и словарём — читаются обе формы).

Выборка живых страниц обязательна. Без неё «8 435 страниц без текста» было бы
утверждением о диске, а не о том, что видит посетитель.

    python3 automation/local/sister-duplicate-scope.py --family animedia
    python3 automation/local/sister-duplicate-scope.py \
        --domain animeg0.site --domain an1meg0.site --domain an1mego.site
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import re
import subprocess
import sys

АГЕНТ = "factory-sister-duplicate-scope"
НАЛОЖЕНИЯ = pathlib.Path("/srv/sites")
СЕМЕЙСТВА = {
    "animedia": ("animedia.icu", "animedia.space"),
    "animego": ("animeg0.site", "an1meg0.site", "an1mego.site"),
    "yummy": ("yummyani.site", "yummyani.org", "yummyani.biz",
              "yummyani7.site", "yummyani7.info"),
}


def слаги_наложения(домен: str) -> set[str]:
    """Слаги с размещённым редакционным текстом. Обе формы `items`."""
    из: set[str] = set()
    for путь in sorted(НАЛОЖЕНИЯ.glob(
            f"*/runtime/overlays/{домен}/title-overlays.json")):
        try:
            д = json.loads(pathlib.Path(путь).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        зп = д.get("items")
        зп = list(зп.values()) if isinstance(зп, dict) else (зп or [])
        для = {з.get("slug") for з in зп
               if isinstance(з, dict) and з.get("slug") and (з.get("body") or "").strip()}
        из |= для
    return из


def достать(url: str, таймаут: int = 60) -> tuple[str, str]:
    г = subprocess.run(["curl", "-sSL", "-A", АГЕНТ, "--max-time", str(таймаут),
                        "-w", "\n@@КОД:%{http_code}", url],
                       capture_output=True, text=True)
    части = (г.stdout or "").rsplit("@@КОД:", 1)
    return (части[0], части[1].strip()) if len(части) == 2 else ("", "0")


def слаги_карты(домен: str, таймаут: int = 90) -> tuple[list[str], str]:
    """Слаги произведений из карты витрины. Индекс карты раскрывается."""
    тело, код = достать(f"https://{домен}/sitemap.xml", таймаут)
    if код != "200":
        return [], f"карта не отдалась: код {код}"
    части = re.findall(r"<loc>([^<]+)</loc>", тело)
    слаги: set[str] = set()
    for часть in части:
        if часть.rstrip("/").endswith(("sitemap.xml",)):
            continue
        т2, к2 = достать(часть, таймаут)
        if к2 != "200":
            continue
        слаги |= set(re.findall(r"/(?:title|anime)/([^/<?\"]+)", т2))
    if not слаги:
        слаги = set(re.findall(r"/(?:title|anime)/([^/<?\"]+)", тело))
    return sorted(слаги), ""


def описание(домен: str, слаг: str, таймаут: int = 35) -> tuple[str, str]:
    for вид in ("title", "anime"):
        тело, код = достать(f"https://{домен}/{вид}/{слаг}/", таймаут)
        if код == "200":
            м = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', тело)
            return (м.group(1).strip() if м else ""), код
    return "", код


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--family", choices=sorted(СЕМЕЙСТВА))
    р.add_argument("--domain", action="append", default=[])
    р.add_argument("--sample", type=int, default=6)
    р.add_argument("--seed", type=int, default=7)
    р.add_argument("--json", type=pathlib.Path)
    а = р.parse_args(аргв)
    домены = а.domain or list(СЕМЕЙСТВА.get(а.family or "", ()))
    if len(домены) < 2:
        print("нужно не меньше двух витрин семейства: --family или --domain дважды",
              file=sys.stderr)
        return 2

    нал = {д: слаги_наложения(д) for д in домены}
    print(f"{'витрина':24} {'размещено текстов':>18}")
    for д in домены:
        print(f"{д:24} {len(нал[д]):18}")
    слаги, беда = слаги_карты(домены[0])
    if беда:
        print(f"НЕ ИЗМЕРЕНО: {беда}", file=sys.stderr)
        return 2
    без_текста = [с for с in слаги if not any(с in нал[д] for д in домены)]
    доля = len(без_текста) / len(слаги) if слаги else 0.0
    print()
    print(f"слагов в карте {домены[0]}: {len(слаги)}")
    print(f"без редакционного текста НИ НА ОДНОЙ витрине семейства:"
          f" {len(без_текста)} ({доля:.1%})")

    random.seed(а.seed)
    выборка = random.sample(без_текста, min(а.sample, len(без_текста)))
    одинаково = различается = не_измерено = 0
    строки = []
    print()
    for слаг in выборка:
        тексты, коды = [], []
        for д in домены:
            т, к = описание(д, слаг)
            тексты.append(т)
            коды.append(к)
        если_все = коды.count("200") == len(домены)
        набор = {т for т, к in zip(тексты, коды, strict=False) if к == "200" and т}
        if not если_все or not набор:
            не_измерено += 1
            исход = f"НЕ ИЗМЕРЕНО (коды {','.join(коды)})"
        elif len(набор) == 1:
            одинаково += 1
            исход = f"ДОСЛОВНО ОДНО ОПИСАНИЕ НА {len(домены)} ({len(next(iter(набор)))} знаков)"
        else:
            различается += 1
            исход = f"различных описаний {len(набор)}"
        строки.append({"слаг": слаг, "исход": исход, "коды": коды})
        print(f"  {слаг[:42]:44} {исход}")

    print()
    print(f"в выборке {len(выборка)}: дословно одинаковых {одинаково},"
          f" различающихся {различается}, не измерено {не_измерено}")
    if а.json:
        а.json.parent.mkdir(parents=True, exist_ok=True)
        а.json.write_text(json.dumps(
            {"домены": домены, "размещено": {д: len(нал[д]) for д in домены},
             "слагов_в_карте": len(слаги), "без_текста": len(без_текста),
             "доля_без_текста": доля, "выборка": строки},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"подробности: {а.json}")
    проверено = одинаково + различается
    if проверено == 0:
        print("ВЫВОД: НЕ ИЗМЕРЕНО — ни одна страница выборки не отдалась целиком")
        return 3
    if различается:
        print(f"ВЫВОД: посылка НЕ подтверждена — у {различается} страниц без"
              " текста описания всё же различаются; считать охват дублей по"
              " отсутствию текста нельзя")
        return 1
    print(f"ВЫВОД: {len(без_текста)} страниц семейства ({доля:.0%} карты) несут"
          f" описание соседа дословно; посылка проверена на {проверено}"
          f" страницах из {len(выборка)} взятых в выборку")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
