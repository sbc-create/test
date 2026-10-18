#!/usr/bin/env python3
"""Сколько исполнитель реально работал, по журналам прогонов. Только чтение.

    python3 automation/local/executor-time.py --from 2026-10-11 --to 2026-10-18

Зачем. «Исполнитель простаивал» обычно выводят из промежутков между коммитами,
а это не доказательство: коммит появляется в конце работы, а не во время. Здесь
время считается по журналам самих прогонов, где у каждого есть начало и конец:

  `var/seo-tech/runs.jsonl`     прогон задачи: начало, конец, вердикт;
  `var/seo-tech/claims.jsonl`   взятие задачи в работу;
  `var/seo-tech/publish.jsonl`  решение о выпуске и его исход.

Что печатается по суткам: число прогонов, занятое время (сумма длительностей),
доля суток под работой, вердикты, выпуски и их исходы.

Чего инструмент НЕ делает: не называет простоем время вне прогонов. Журнал не
знает, была ли в этот момент готовая задача, ждал ли исполнитель внешнего
действия или не работал вовсе — поэтому остаток суток печатается как
«не классифицировано журналом». Чтобы отделить простой от ожидания, нужен
журнал состояния очереди на тот же момент; пока его нет, вывод останется
честным пробелом, а не догадкой.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path("/home/claude/wt-portable-site-cell-01/var/seo-tech")
СУТКИ_С = 24 * 3600


def строки(имя: str) -> list[dict]:
    п = КОРЕНЬ / имя
    итог = []
    try:
        текст = п.read_text(encoding="utf-8")
    except OSError as сбой:
        print(f"не прочитан {п}: {сбой}", file=sys.stderr)
        return итог
    for строка in текст.splitlines():
        строка = строка.strip()
        if not строка:
            continue
        try:
            итог.append(json.loads(строка))
        except ValueError:
            continue
    return итог


def момент(значение: str):
    try:
        return dt.datetime.fromisoformat((значение or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--from", dest="с", default="2026-10-11")
    р.add_argument("--to", dest="по", default="2026-10-18")
    а = р.parse_args(аргв)

    прогоны = строки("runs.jsonl")
    выпуски = строки("publish.jsonl")
    if not прогоны:
        return 2

    по_суткам: dict[str, dict] = collections.defaultdict(
        lambda: {"прогонов": 0, "секунд": 0.0, "вердикты": collections.Counter(),
                 "без_конца": 0, "задачи": set()})
    for з in прогоны:
        н, к = момент(з.get("started_at")), момент(з.get("finished_at"))
        if not н:
            continue
        день = н.date().isoformat()
        if not (а.с <= день <= а.по):
            continue
        d = по_суткам[день]
        d["прогонов"] += 1
        d["вердикты"][str(з.get("verdict"))] += 1
        d["задачи"].add(str(з.get("task_id")))
        if к:
            d["секунд"] += max(0.0, (к - н).total_seconds())
        else:
            d["без_конца"] += 1

    по_суткам_выпуски: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter)
    for з in выпуски:
        м = момент(з.get("at"))
        if not м:
            continue
        день = м.date().isoformat()
        if а.с <= день <= а.по:
            по_суткам_выпуски[день][str(з.get("outcome") or з.get("decision"))] += 1

    print(f"{'сутки':12} {'прогонов':9} {'задач':6} {'занято':10} "
          f"{'доля суток':11} {'вердикты':34} выпуски")
    итого = {"прогонов": 0, "секунд": 0.0, "вердикты": collections.Counter(),
             "выпуски": collections.Counter()}
    день = dt.date.fromisoformat(а.с)
    конец = dt.date.fromisoformat(а.по)
    while день <= конец:
        к = день.isoformat()
        d = по_суткам.get(к)
        в = по_суткам_выпуски.get(к) or collections.Counter()
        if not d:
            print(f"{к:12} {'—':9} {'—':6} {'нет записей':10} {'—':11} "
                  f"{'—':34} {dict(в) or '—'}")
            день += dt.timedelta(days=1)
            continue
        часы = d["секунд"] / 3600
        доля = 100 * d["секунд"] / СУТКИ_С
        вердикты = ", ".join(f"{и}:{н}" for и, н in d["вердикты"].most_common(3))
        print(f"{к:12} {d['прогонов']:<9} {len(d['задачи']):<6} "
              f"{часы:6.1f} ч   {доля:5.1f} %     {вердикты:34} "
              f"{dict(в) or '—'}")
        итого["прогонов"] += d["прогонов"]
        итого["секунд"] += d["секунд"]
        итого["вердикты"].update(d["вердикты"])
        итого["выпуски"].update(в)
        день += dt.timedelta(days=1)

    суток = (конец - dt.date.fromisoformat(а.с)).days + 1
    print()
    print(f"всего прогонов: {итого['прогонов']}; занято "
          f"{итого['секунд'] / 3600:.1f} ч из {суток * 24} ч календаря "
          f"({100 * итого['секунд'] / (суток * СУТКИ_С):.1f} %)")
    print(f"вердикты: {dict(итого['вердикты'])}")
    print(f"исходы выпусков: {dict(итого['выпуски'])}")
    print()
    print("Остаток календарного времени НЕ называется простоем: журнал "
          "прогонов не знает, была ли в тот момент готовая задача и не ждал "
          "ли исполнитель внешнего действия. Чтобы отделить простой от "
          "ожидания, нужен журнал состояния очереди на тот же момент.")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная())
