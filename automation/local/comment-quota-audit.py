#!/usr/bin/env python3
"""Сколько комментариев сеть выпустила за сутки и сколько мест осталось.

    python3 automation/local/comment-quota-audit.py            # текущие сутки UTC
    python3 automation/local/comment-quota-audit.py --day 2026-10-09
    python3 automation/local/comment-quota-audit.py --quiet

Зачем. Суточный предел сети — сто комментариев, и до сих пор его считал сам
редактор: читал журналы хранилищ накладок и складывал. Измерено 2026-10-10: за
сутки UTC вышло 102 публикации при одном снятии, то есть 101 — предел перейдён,
и самоотчёт запуска это честно назвал. Причина перехода не в пределе, а в
способе счёта:

* счёт делается ОДИН раз перед партией, а партия публикует до шести: запуск,
  начавшийся при 96, доводит сутки до 102;
* публикуют РАЗНЫЕ исполнители. В этих же сутках 7 записей сделаны не прогоном
  редактора (`prepared_by: "Редакция"`), и перед партией учесть их было нечем;
* ручной счёт нечем перепроверить, а значит нечем и поймать ошибку.

Инструмент считает по тому же правилу, но машинно: операции `publish-comment`
за НАЗВАННЫЕ сутки UTC минус снятия (`unpublish-comment`, `retract-comment`) в
тех же сутках. Предел он не меняет и ничего не публикует.

Код возврата: 0 — места есть; 1 — предел выработан.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import pathlib

КОРНИ = pathlib.Path("/srv/sites")
ПУБЛИКАЦИЯ = "publish-comment"
СНЯТИЯ = ("unpublish-comment", "retract-comment")


def записи(день: str) -> tuple[list[dict], list[dict]]:
    """Публикации и снятия названных суток по всем хранилищам накладок."""
    публикации: list[dict] = []
    снятия: list[dict] = []
    for журнал in КОРНИ.glob("*/runtime/overlays/*/history.jsonl"):
        домен = журнал.parent.name
        try:
            строки = журнал.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for строка in строки:
            if '"op"' not in строка or "comment" not in строка:
                continue
            try:
                з = json.loads(строка)
            except ValueError:
                continue
            if str(з.get("at") or "")[:10] != день:
                continue
            з["_домен"] = домен
            if з.get("op") == ПУБЛИКАЦИЯ:
                публикации.append(з)
            elif з.get("op") in СНЯТИЯ:
                снятия.append(з)
    return публикации, снятия


def главное(argv=None) -> int:
    ap = argparse.ArgumentParser(description="суточная квота комментариев сети")
    ap.add_argument("--day", default=datetime.datetime.utcnow().strftime("%Y-%m-%d"),
                    help="сутки UTC, по умолчанию текущие")
    ap.add_argument("--limit", type=int, default=100,
                    help="предел сети; этим инструментом он не меняется")
    ap.add_argument("--quiet", action="store_true", help="только числа")
    a = ap.parse_args(argv)

    публикации, снятия = записи(a.day)
    итог = len(публикации) - len(снятия)
    осталось = max(0, a.limit - итог)
    свод = {"day": a.day, "limit": a.limit, "published": len(публикации),
            "retracted": len(снятия), "counted": итог, "remaining": осталось,
            "over_limit": итог > a.limit}
    if a.quiet:
        print(json.dumps(свод, ensure_ascii=False))
        return 0 if осталось else 1

    print(json.dumps(свод, ensure_ascii=False, indent=1))
    по_домену = collections.Counter(з["_домен"] for з in публикации)
    по_часам = collections.Counter(str(з.get("at"))[11:13] for з in публикации)
    по_исполнителю = collections.Counter(
        str(з.get("prepared_by") or "не назван")[:52] for з in публикации)
    print("\nпо доменам:")
    for к, v in по_домену.most_common():
        print(f"   {v:>4}  {к}")
    print("\nпо часам UTC:", dict(sorted(по_часам.items())))
    print("\nпо исполнителям:")
    for к, v in по_исполнителю.most_common():
        # Исполнитель без формы `<роль>/<автоматизация>/<прогон>` — это запись,
        # которую счёт перед партией учесть не мог: её сделал не прогон.
        вид = "прогон" if к.count("/") >= 2 else "НЕ прогон"
        print(f"   {v:>4}  {к}  ({вид})")
    if итог > a.limit:
        print(f"\nпредел перейдён на {итог - a.limit}: публикаций "
              f"{len(публикации)}, снятий {len(снятия)}")
    return 0 if осталось else 1


if __name__ == "__main__":
    raise SystemExit(главное())
