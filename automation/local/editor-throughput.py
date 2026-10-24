#!/usr/bin/env python3
"""Сколько работы редактора доходит до текста, а сколько уходит в пустые исходы.

ПОВОД ИЗМЕРЕННЫЙ, 24.10. За сутки редактор закрыл 207 заданий: текст написан у
26, а 152 ушли в `SOURCES_MISSING` — и в `detail` каждого такого исхода
записано дословно «повтор без изменения условий … реестр источников не
менялся». То есть очередь знает, что повтор бессмысленен, и всё равно его
назначает: `ПОВТОР_ФАКТОВ_Ч = 24`, статус не меняется, счётчик попыток не
растёт (MOD-168).

Зачем отдельный инструмент. «Текстов за сутки» без знаменателя не отвечает на
главный вопрос — почему их столько. Полезный выход и пустая работа считаются
вместе, иначе рост числа заданий выглядит как рост работы.

ТРИ РАЗНЫЕ ВЕЩИ, которые инструмент не путает:
  написано      — `TEXT_WRITTEN`, единственный путь к тексту;
  пусто впервые — отказ по новому произведению: это нормальная цена разбора;
  пусто по кругу— отказ, в `detail` которого сказано, что условия не менялись.
Только третье — потеря. Первые два — работа.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys
from collections import Counter

АРЕНДЫ = pathlib.Path("/var/lib/seo-content-operator/editorial_leases.json")
ПУСТЫЕ = ("SOURCES_MISSING", "PAGE_ABSENT", "IDENTITY_UNCLEAR",
          "IDENTITY_REJECTED", "SOURCE_UNAVAILABLE", "NO_CHANGE_NEEDED",
          "DELIVERY_UNSUPPORTED")
#: Признак круга: очередь сама пишет его в `detail`.
ПО_КРУГУ = ("без изменения условий", "не менялся", "не менялись")


def аренды(путь: pathlib.Path = АРЕНДЫ) -> list[dict]:
    д = json.loads(путь.read_text(encoding="utf-8"))
    зп = д.get("leases") or д
    зп = list(зп.values()) if isinstance(зп, dict) else зп
    return [з for з in (зп or []) if isinstance(з, dict)]


def по_кругу(шаг: dict) -> bool:
    д = str(шаг.get("detail") or "")
    return any(п in д for п in ПО_КРУГУ)


def шаги(записи: list[dict], с: datetime.datetime, по: datetime.datetime
         ) -> list[tuple[dict, dict]]:
    из = []
    for з in записи:
        for ш in (з.get("history") or []):
            м = str(ш.get("at") or "")
            if not м:
                continue
            try:
                т = datetime.datetime.fromisoformat(м.replace("Z", "+00:00"))
            except ValueError:
                continue
            if т.tzinfo is None:
                т = т.replace(tzinfo=datetime.timezone.utc)
            if с <= т <= по:
                из.append((з, ш))
    return из


def свод(пары: list[tuple[dict, dict]]) -> dict:
    исходы = Counter(ш.get("outcome") for _, ш in пары)
    написано = исходы.get("TEXT_WRITTEN", 0)
    пусто = sum(в for к, в in исходы.items() if к in ПУСТЫЕ)
    круг = sum(1 for _, ш in пары
               if ш.get("outcome") in ПУСТЫЕ and по_кругу(ш))
    работы = [(з.get("work_id") or з.get("content_id")) for з, ш in пары]
    return {"всего": len(пары), "исходы": dict(исходы.most_common()),
            "написано": написано, "пусто": пусто, "пусто_по_кругу": круг,
            "различных_произведений": len(set(работы)),
            "витрин": len({з.get("site") for з, _ in пары})}


def контроль(путь: pathlib.Path) -> int:
    """Инструмент обязан различать круг и первый отказ."""
    ошибки = []
    if not по_кругу({"detail": "повтор без изменения условий: прежний отказ"}):
        ошибки.append("круг не распознан по собственной записи очереди")
    if по_кругу({"detail": "источники проверены, фактов о годе нет"}):
        ошибки.append("первый отказ принят за круг")
    if not путь.exists():
        ошибки.append(f"журнала аренд нет: {путь}")
    for о in ошибки:
        print(f"КОНТРОЛЬ НЕ ПРОЙДЕН: {о}")
    if ошибки:
        return 1
    print("контроль пройден: круг отличается от первого отказа")
    return 0


def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--hours", type=int, default=24)
    р.add_argument("--leases", type=pathlib.Path, default=АРЕНДЫ)
    р.add_argument("--control", action="store_true")
    р.add_argument("--max-empty-share", type=float, default=0.5,
                   help="доля пустых исходов, выше которой это отказ")
    а = р.parse_args(argv)

    if а.control:
        к = контроль(а.leases)
        if к:
            return к
    if not а.leases.exists():
        print(f"НЕ ИЗМЕРЕНО: журнала аренд нет — {а.leases}")
        return 2

    по = datetime.datetime.now(datetime.timezone.utc)
    с = по - datetime.timedelta(hours=а.hours)
    пары = шаги(аренды(а.leases), с, по)
    if not пары:
        print(f"НЕ ИЗМЕРЕНО: за последние {а.hours} ч в журнале аренд нет"
              " ни одного закрытого задания — редактор не работал либо журнал"
              " не пишется")
        return 2
    д = свод(пары)
    print(f"окно: последние {а.hours} ч (с {с:%Y-%m-%dT%H:%M}Z)")
    print(f"заданий закрыто {д['всего']} на {д['витрин']} витринах,"
          f" различных произведений {д['различных_произведений']}")
    print()
    for к, в in д["исходы"].items():
        доля = в / д["всего"]
        print(f"  {str(к):22} {в:5}  {доля:5.1%}")
    print()
    доля_пусто = д["пусто"] / д["всего"]
    print(f"написано текстов {д['написано']} ({д['написано'] / д['всего']:.1%});"
          f" пустых исходов {д['пусто']} ({доля_пусто:.1%})")
    print(f"из пустых — ПО КРУГУ (условия не менялись, очередь сама это пишет):"
          f" {д['пусто_по_кругу']}")
    if д["пусто"]:
        print(f"   то есть потеря, а не цена разбора:"
              f" {д['пусто_по_кругу'] / д['пусто']:.0%} пустых исходов")
    print()
    if доля_пусто > а.max_empty_share:
        print(f"ВЫВОД: пустых исходов {доля_пусто:.0%} при пороге"
              f" {а.max_empty_share:.0%} — работа редактора уходит не в текст;"
              f" из них {д['пусто_по_кругу']} повторены без изменения условий"
              " (MOD-168)")
        return 1
    print(f"ВЫВОД: пустых исходов {доля_пусто:.0%}, в пределах порога"
          f" {а.max_empty_share:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
