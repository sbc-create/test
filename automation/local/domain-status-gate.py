#!/usr/bin/env python3
"""Действующий статус домена — спросить ДО того, как назначить ему работу.

ПОВОД, измеренный 27.10. `animedia.space` выведен владельцем из активной
работы 2026-10-25 и переведён в `awaiting_replacement`. Это записано в
`config/active-domains.json`. Но реестр ячеек `config/site-cells.json`, по
которому идёт ВЫПУСК, остался со `status: live`, и на выведенный домен уехали
два выпуска подряд. До этой проверки статус домена на пути работы не
спрашивался вовсе — ни при назначении задачи, ни перед выпуском.

ЧТО ДЕЛАЕТ. Отвечает одним словом на вопрос «можно ли назначать этому домену
работу», и отвечает по тому реестру, который объявлен единственным
версионируемым списком активных домéнов сети и правится только по заданию
владельца. Коды выхода: 0 — активен, 2 — выведен, 1 — НЕ ИЗМЕРЕНО.

ЧЕГО НЕ ДЕЛАЕТ. Не считает отсутствие домена в реестре запретом: так выглядит
витрина, которую ещё только заводят. «Не измерено» — это третий ответ, а не
разрешение и не отказ.

    python3 automation/local/domain-status-gate.py --site animedia-02
    python3 automation/local/domain-status-gate.py --all --json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
АКТИВНЫЕ = КОРЕНЬ / "config" / "active-domains.json"
ЯЧЕЙКИ = КОРЕНЬ / "config" / "site-cells.json"
#: Статусы реестра ячеек, которые НЕ противоречат выводу домена из работы.
СОГЛАСНЫЕ_С_ВЫВОДОМ = ("excluded", "awaiting_replacement", "withdrawn", "retired")


def _реестр(путь: pathlib.Path) -> dict:
    return json.loads(путь.read_text(encoding="utf-8"))


def _ряды_ячеек(данные) -> list:
    ряды = данные.get("cells") or данные.get("sites") or данные
    return list(ряды.values()) if isinstance(ряды, dict) else list(ряды)


def статус(ключ: str) -> dict:
    """Статус по site_id или домену: состояние, причина и согласие реестров."""
    try:
        акт = _реестр(АКТИВНЫЕ)
    except (OSError, ValueError) as сбой:
        return {"ключ": ключ, "состояние": "НЕ ИЗМЕРЕНО",
                "причина": f"реестр активных не прочитан: {type(сбой).__name__}"}
    найдено = None
    for раздел, по_умолчанию in (("domains", "active"),
                                 ("awaiting_replacement", "awaiting_replacement")):
        for з in акт.get(раздел) or []:
            if ключ in (str(з.get("site_id") or ""), str(з.get("domain") or "")):
                найдено = {"ключ": ключ,
                           "домен": з.get("domain"), "site_id": з.get("site_id"),
                           "состояние": str(з.get("state") or по_умолчанию),
                           "причина": str(з.get("reason") or "")}
                break
        if найдено:
            break
    if не_найдено := (найдено is None):
        return {"ключ": ключ, "состояние": "НЕ ИЗМЕРЕНО",
                "причина": "домена нет ни в одном разделе реестра активных"}
    # Второй реестр не решает, но его расхождение называется: именно оно и
    # пропустило выпуск на выведенный домен.
    try:
        по_ид = {str(з.get("site_id")): з for з in _ряды_ячеек(_реестр(ЯЧЕЙКИ))}
    except (OSError, ValueError, AttributeError):
        найдено["реестр ячеек"] = "не прочитан"
        return найдено
    я = по_ид.get(str(найдено.get("site_id")))
    статус_ячейки = str((я or {}).get("status") or "нет записи")
    найдено["реестр ячеек"] = статус_ячейки
    найдено["реестры согласны"] = (
        найдено["состояние"] != "awaiting_replacement"
        or статус_ячейки in СОГЛАСНЫЕ_С_ВЫВОДОМ or статус_ячейки == "нет записи")
    return найдено


def все() -> list[dict]:
    акт = _реестр(АКТИВНЫЕ)
    ключи = [str(з.get("site_id")) for раздел in ("domains", "awaiting_replacement")
             for з in акт.get(раздел) or []]
    return [статус(к) for к in ключи]


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--site", default="", help="site_id или домен")
    р.add_argument("--all", action="store_true")
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    if not а.site and not а.all:
        print("нужен --site или --all", file=sys.stderr)
        return 2
    if а.all:
        ряды = все()
        if а.json:
            print(json.dumps(ряды, ensure_ascii=False, indent=1))
        else:
            for з in ряды:
                знак = {"active": "активен ", "awaiting_replacement": "ВЫВЕДЕН "}.get(
                    з["состояние"], "НЕ ИЗМЕРЕНО ")
                согласие = "" if з.get("реестры согласны", True) else \
                    f"  ← реестр ячеек говорит «{з.get('реестр ячеек')}»"
                print(f"{знак}{str(з.get('домен') or з['ключ']):26s}{согласие}")
        расход = [з for з in ряды if not з.get("реестры согласны", True)]
        if расход:
            print(f"\nрасхождений реестров: {len(расход)} — выпуск читает "
                  "реестр ячеек, и для них он не знает о выводе")
        return 1 if расход else 0
    з = статус(а.site)
    if а.json:
        print(json.dumps(з, ensure_ascii=False, indent=1))
    else:
        print(f"{з['ключ']}: {з['состояние']}"
              + (f" — {з['причина']}" if з.get("причина") else ""))
    if з["состояние"] == "awaiting_replacement":
        return 2
    return 0 if з["состояние"] == "active" else 1


if __name__ == "__main__":
    sys.exit(главная())
