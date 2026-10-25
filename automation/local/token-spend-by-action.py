#!/usr/bin/env python3
"""Чей расход: привязка контекста обращения к ВИДУ действия, а не к сеансу.

ЗАЧЕМ. Свод по сеансам говорит «один сеанс съел 72 % недели», но не говорит,
НА ЧТО. В агентной работе цена обращения — это почти целиком чтение кеша
(контекст, который модель перечитывает каждый раз), поэтому расход правильно
относить к ДЕЙСТВИЮ, которое это обращение запустило: правка файла, запуск
проверки, опрос фонового задания, чтение журнала.

Как считается. Для каждого обращения (дедупликация по `requestId`, как в
`token-spend-audit.py`) берутся имена инструментов из блоков `tool_use` того же
сообщения и первые 120 знаков их входа. Содержимое ответов и текст сообщений не
читаются. Расход обращения относится ко ВСЕМ его инструментам поровну — если в
одном обращении два вызова, каждому достаётся половина; это сказано прямо,
потому что иначе доли не сложатся в целое.

Отдельно выделяется ОПРОС ФОНОВОГО ЗАДАНИЯ: обращение, единственное действие
которого — посмотреть, не закончилось ли что-то (`tail`/`stat`/`ps`/`date` по
журналу или файлу вывода). Такое обращение не меняет состояния мира и стоит
полного перечитывания контекста.

    python3 automation/local/token-spend-by-action.py --session <файл.jsonl>
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import json
import re
import sys

#: Признаки обращения-опроса: команда только смотрит, не изменилось ли что-то.
ОПРОС = re.compile(
    r"(tail -c|tail -\d|\btail\b.*(output|\.txt|\.log|jsonl)|\bstat\b|\bps -e|"
    r"pgrep|date -u|grep -c \"\"|проверить прогресс|progress)", re.I)
#: Признаки запуска полной проверки — дорого по времени, дёшево по токенам.
ПРОГОН = re.compile(r"(pytest|verify\.sh|record-evidence)", re.I)


def действия(сообщение: dict) -> list[tuple[str, str]]:
    итог = []
    for блок in (сообщение.get("content") or []):
        if isinstance(блок, dict) and блок.get("type") == "tool_use":
            вход = json.dumps(блок.get("input") or {}, ensure_ascii=False)[:160]
            итог.append((блок.get("name") or "—", вход))
    return итог


def класс(инструмент: str, вход: str) -> str:
    if инструмент == "Bash":
        if ОПРОС.search(вход):
            return "Bash: ОПРОС фонового задания"
        if ПРОГОН.search(вход):
            return "Bash: запуск проверок"
        if "git commit" in вход or "git add" in вход:
            return "Bash: фиксация в git"
        if "python3 - <<" in вход or "python3 -" in вход:
            return "Bash: разовый скрипт"
        if "curl" in вход:
            return "Bash: обращение к витрине"
        return "Bash: прочее"
    return инструмент


def собрать(файлы: list[str], с: dt.datetime, по: dt.datetime) -> dict:
    видено: set[str] = set()
    по_классу: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    без_действий = collections.Counter()
    всего = collections.Counter()
    for путь in файлы:
        with open(путь, encoding="utf-8", errors="replace") as ф:
            for строка in ф:
                if '"usage"' not in строка:
                    continue
                try:
                    з = json.loads(строка)
                except ValueError:
                    continue
                м = з.get("message") or {}
                u = м.get("usage")
                if not isinstance(u, dict):
                    continue
                чк = u.get("cache_read_input_tokens") or 0
                вых = u.get("output_tokens") or 0
                зк = u.get("cache_creation_input_tokens") or 0
                if not (чк or вых or зк):
                    continue
                т = з.get("timestamp") or ""
                try:
                    когда = dt.datetime.fromisoformat(т.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if not (с <= когда <= по):
                    continue
                ключ = з.get("requestId") or f"uuid:{з.get('uuid')}"
                if ключ in видено:
                    continue
                видено.add(ключ)
                всего.update({"обращений": 1, "чтение_кеша": чк, "выходные": вых,
                              "запись_кеша": зк})
                д = действия(м)
                if not д:
                    без_действий.update({"обращений": 1, "чтение_кеша": чк,
                                         "выходные": вых, "запись_кеша": зк})
                    continue
                доля = len(д)
                for инстр, вход in д:
                    по_классу[класс(инстр, вход)].update({
                        "обращений": 1,
                        "чтение_кеша": чк // доля,
                        "выходные": вых // доля,
                        "запись_кеша": зк // доля})
    return {"по_классу": по_классу, "без_действий": без_действий, "всего": всего}


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--session", action="append", default=[],
                   help="файл стенограммы; по умолчанию — все этого проекта")
    р.add_argument("--days", type=float, default=7.0)
    р.add_argument("--project", default="-home-claude-wt-nova-publish-memory-02")
    а = р.parse_args(аргв)
    файлы = а.session or sorted(glob.glob(
        f"/home/claude/.claude/projects/{а.project}/*.jsonl"))
    по = dt.datetime.now(dt.timezone.utc)
    с = по - dt.timedelta(days=а.days)
    итог = собрать(файлы, с, по)
    в = итог["всего"]
    print(f"файлов {len(файлы)}; окно {а.days:g} сут ({с:%Y-%m-%dT%H:%M}Z … {по:%Y-%m-%dT%H:%M}Z)")
    print(f"обращений {в['обращений']}, чтение кеша {в['чтение_кеша']:,},"
          f" выходных {в['выходные']:,}, запись кеша {в['запись_кеша']:,}")
    если = в["чтение_кеша"] or 1
    print(f"\n{'вид действия':38} {'обращений':>9} {'чтение кеша':>15} {'доля':>6} {'выходных':>9}")
    строки = sorted(итог["по_классу"].items(), key=lambda п: -п[1]["чтение_кеша"])
    for к, зн in строки:
        print(f"{к:38} {зн['обращений']:>9} {зн['чтение_кеша']:>15,}"
              f" {зн['чтение_кеша']/если*100:>5.1f}% {зн['выходные']:>9,}")
    бд = итог["без_действий"]
    print(f"{'без вызова инструмента (только текст)':38} {бд['обращений']:>9}"
          f" {бд['чтение_кеша']:>15,} {бд['чтение_кеша']/если*100:>5.1f}%"
          f" {бд['выходные']:>9,}")
    опрос = итог["по_классу"].get("Bash: ОПРОС фонового задания", collections.Counter())
    if опрос["обращений"]:
        print(f"\nОПРОС ФОНОВОГО ЗАДАНИЯ: {опрос['обращений']} обращений,"
              f" {опрос['чтение_кеша']:,} токенов чтения кеша"
              f" — это {опрос['чтение_кеша']/если*100:.1f}% всего чтения кеша окна,"
              f" и ни одно из них не изменило состояния мира.")
    print("\nЧЕГО ЭТОТ СЧЁТ НЕ ГОВОРИТ: расход обращения делится между его"
          " инструментами ПОРОВНУ, потому что иначе доли не сложатся; значит доля"
          " вида действия — оценка, а не точная цена. Обращения без вызова"
          " инструмента (ответ владельцу, рассуждение) показаны отдельной строкой.")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
