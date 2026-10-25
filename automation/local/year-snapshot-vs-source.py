#!/usr/bin/env python3
"""Расходится ли год СНИМКА каталога с годом ИСТОЧНИКА, и как часто.

Повод — MOD-178. Ворота качества материала требуют назвать в тексте год из
снимка каталога, а редактор отказывается писать год, которого источник не
подтверждает. На `an1meg0.site/rukovodstvo-soten-demonov-4` снимок говорит 2020,
Shikimori 57995 — `aired_on 2024-02-23`; материал непубликуем в обе стороны.

Чего до этого инструмента не было — ЧАСТОТЫ. Охват назывался «не меньше пяти
пар за 10 суток» (нижняя граница по формулировкам в журнале), а доля работ с
расхождением не мерилась вовсе. Без неё нельзя отличить дешёвую правку с узким
следствием от рычага.

Три свойства, без которых счёт был бы видимостью:

* **«года в снимке нет» — это НЕ «год совпал».** Такие работы идут в «не
  измерено» и в знаменатель доли не попадают;
* **сиквелы считаются отдельно.** Гипотеза, ради которой инструмент и написан:
  снимок сиквела несёт год ПЕРВОГО сезона. Проверяется разделением выборки, а
  не общим средним, иначе редкий случай растворится;
* **выборка воспроизводима** (семя задаётся), и источник читается только
  штатным путём (`source_fetch.py`, не чаще 4 запросов в секунду).

    python3 automation/local/year-snapshot-vs-source.py --seed 20261025 --sample 12
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib
import random
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

ХРАНИЛИЩА = "/srv/sites/*/runtime/overlays/*/drafts.json"
ИНСТРУМЕНТ = pathlib.Path(__file__).resolve().parent / "source_fetch.py"


def вид_работы(слаг: str) -> str:
    """«сиквел» у слага, кончающегося числом, иначе «прочее».

    Признак нарочно грубый и назван: `-2`, `-3`, `-4` в конце слага — так сеть
    записывает сезоны и продолжения. Работа, у которой число стоит в середине
    (`detektiv-konan-pentagramma-na-milliard`), сиквелом не считается.
    """
    return "сиквел" if re.search(r"-\d+$", слаг or "") else "прочее"


def год_даты(значение: str) -> str:
    """Год из даты источника; пустая строка, если даты нет."""
    с = str(значение or "")
    return с[:4] if с[:4].isdigit() else ""


def исход(снимок: str, источник: str) -> str:
    if not снимок or not источник:
        return "НЕ ИЗМЕРЕНО"
    return "расходятся" if str(снимок) != str(источник) else "совпадают"


def свод(записи: list[tuple[str, str]]) -> dict:
    """Доли по видам работ. Знаменатель — только ИЗМЕРЕННЫЕ работы."""
    итог: dict[str, dict] = {}
    for вид, если in записи:
        с = итог.setdefault(вид, {"измерено": 0, "расходятся": 0, "не измерено": 0})
        if если == "НЕ ИЗМЕРЕНО":
            с["не измерено"] += 1
            continue
        с["измерено"] += 1
        if если == "расходятся":
            с["расходятся"] += 1
    for с in итог.values():
        с["доля"] = (f"{с['расходятся'] / с['измерено'] * 100:.0f} %"
                     if с["измерено"] else "—")
    return итог


def черновики(хранилища: str = ХРАНИЛИЩА) -> list[tuple[str, str, str]]:
    итог = []
    for путь in sorted(glob.glob(хранилища)):
        домен = pathlib.Path(путь).parent.name
        try:
            данные = json.loads(pathlib.Path(путь).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        если = данные.get("items") if isinstance(данные, dict) else данные
        пары = (если.items() if isinstance(если, dict)
                else [((з or {}).get("slug"), з) for з in (если or [])])
        for слаг, запись in пары:
            if not слаг or not isinstance(запись, dict):
                continue
            ид = [s for s in (запись.get("sources") or [])
                  if "shikimori.io/animes/" in str(s)]
            if ид:
                итог.append((домен, слаг, str(ид[0]).rsplit("/", 1)[-1]))
    return итог


def год_источника(ид: str, таймаут: int = 180) -> str:
    г = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "shikimori", ид],
                       capture_output=True, text=True, timeout=таймаут)
    if г.returncode != 0:
        return ""
    try:
        д = json.loads(г.stdout)
    except ValueError:
        return ""
    return год_даты(д.get("aired_on") or д.get("released_on") or "")


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--seed", type=int, default=20261025)
    р.add_argument("--sample", type=int, default=12,
                   help="сколько работ каждого вида брать")
    а = р.parse_args(аргв)

    from factory.qwen import editorial

    все = черновики()
    по_виду: dict[str, list] = {}
    for т in все:
        по_виду.setdefault(вид_работы(т[1]), []).append(т)
    print(f"черновиков с карточкой Shikimori: {len(все)}"
          + "".join(f" ({в} {len(с)})" for в, с in sorted(по_виду.items())))
    случ = random.Random(а.seed)
    выборка = []
    for вид, список in sorted(по_виду.items()):
        выборка += случ.sample(список, min(а.sample, len(список)))

    печать = f"{'вид':8} {'домен':16} {'слаг':34} {'снимок':7} {'источник':9} исход"
    print(печать)
    собрано = []
    for домен, слаг, ид in выборка:
        вид = вид_работы(слаг)
        try:
            ф = (editorial.факты(домен, слаг).get("facts") or {})
        except Exception as ош:  # отказ чтения фактов — результат, не сбой
            print(f"{вид:8} {домен:16} {слаг[:34]:34} отказ фактов:"
                  f" {type(ош).__name__}")
            собрано.append((вид, "НЕ ИЗМЕРЕНО"))
            continue
        снимок = str(ф.get("year") or "")
        ист = год_источника(ид)
        если = исход(снимок, ист)
        собрано.append((вид, если))
        print(f"{вид:8} {домен:16} {слаг[:34]:34} {снимок:7} {ист:9} {если}")
    print()
    for вид, с in sorted(свод(собрано).items()):
        print(f"{вид}: измерено {с['измерено']}, расходятся {с['расходятся']}"
              f" ({с['доля']}), не измерено {с['не измерено']}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
