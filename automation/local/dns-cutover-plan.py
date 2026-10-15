#!/usr/bin/env python3
"""План и проверка перевода DNS партии: снимок, список изменений, откат.

Зачем инструмент, а не ручной список. Перевод DNS — отдельный журналируемый
шаг, и у него три части, которые легко перепутать: что СЕЙЧАС, что ДОЛЖНО
стать и чем вернуться. Снимок прежних значений — это и есть план откату, и
снимать его надо ДО правки, а не вспоминать после.

Что делает:

* спрашивает авторитетные NS зоны и публичный резолвер (две точки зрения:
  запись может быть изменена у регистратора и ещё не разойтись по кешам);
* сверяет A, AAAA и CNAME апекса и `www` с целью;
* печатает ровно те изменения, которых не хватает, и прежние значения для
  откату;
* `--verify` ничего не планирует: он отвечает на вопрос «перевод состоялся?»
  и годится как приёмка после операции владельца.

Чего инструмент НЕ делает: не меняет записи. Управление зоной требует
scoped-токена из `inventory/dns-zones.yaml`; пока зоны там нет, это
`BLOCKED_ACCESS`, а не повод подставить чужой токен.

    python3 automation/local/dns-cutover-plan.py --batch k2
    python3 automation/local/dns-cutover-plan.py --batch k2 --verify
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
#: Партия и целевой узел. Домены берутся из реестра ячеек по site_id, а не
#: переписываются сюда: реестр — источник истины о том, какой домен у витрины.
ПАРТИИ = {
    "k2": {
        "site_ids": [f"lords-{н}" for н in range(10, 18)],
        "target_a": "145.63.129.86",
        "node": "k2-zomro-01",
        "old_a": "45.131.182.225",
    },
}
ПУБЛИЧНЫЙ = "8.8.8.8"


def _dig(имя: str, тип: str, сервер: str | None = None) -> list[str]:
    команда = ["dig", "+short", тип, имя]
    if сервер:
        команда.append(f"@{сервер}")
    г = subprocess.run(команда, capture_output=True, text=True, timeout=30)
    return [с.strip() for с in (г.stdout or "").split() if с.strip()]


def _ns(зона: str) -> list[str]:
    return _dig(зона, "NS", ПУБЛИЧНЫЙ)


def домены(партия: dict) -> list[tuple[str, str]]:
    реестр = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))
    по_id = {я["site_id"]: я for я in реестр["cells"]}
    итог = []
    for site_id in партия["site_ids"]:
        ячейка = по_id.get(site_id)
        if ячейка is None:
            raise SystemExit(f"{site_id}: нет в реестре ячеек")
        итог.append((site_id, ячейка["domain"]))
    return итог


def снимок(домен: str) -> dict:
    """Что отдаёт публичный резолвер и что — авторитетные NS зоны."""
    зона = ".".join(домен.split(".")[-2:]) if домен.count(".") >= 1 else домен
    нс = _ns(домен) or _ns(зона)
    авторитет = нс[0].rstrip(".") if нс else None
    запись = {
        "домен": домен,
        "ns": нс,
        "публичный": {
            "A": _dig(домен, "A", ПУБЛИЧНЫЙ),
            "AAAA": _dig(домен, "AAAA", ПУБЛИЧНЫЙ),
            "CNAME": _dig(домен, "CNAME", ПУБЛИЧНЫЙ),
        },
        "www": {
            "A": _dig(f"www.{домен}", "A", ПУБЛИЧНЫЙ),
            "CNAME": _dig(f"www.{домен}", "CNAME", ПУБЛИЧНЫЙ),
        },
    }
    if авторитет:
        запись["авторитетный"] = {
            "сервер": авторитет,
            "A": _dig(домен, "A", авторитет),
            "AAAA": _dig(домен, "AAAA", авторитет),
            "www_A": _dig(f"www.{домен}", "A", авторитет),
            "www_CNAME": _dig(f"www.{домен}", "CNAME", авторитет),
        }
    return запись


def нужные_изменения(запись: dict, цель: str) -> list[str]:
    """Чего не хватает для перевода. Пустой список — переводить нечего."""
    нужно: list[str] = []
    a = запись["публичный"]["A"]
    if a != [цель]:
        нужно.append(f"A {запись['домен']} → {цель} (сейчас {a or 'нет записи'})")
    aaaa = запись["публичный"]["AAAA"]
    if aaaa:
        нужно.append(f"AAAA {запись['домен']}: {aaaa} — убрать или перевести на "
                     "адрес нового узла, иначе часть посетителей уйдёт на прежний")
    www_a, www_c = запись["www"]["A"], запись["www"]["CNAME"]
    if www_c:
        if not any(запись["домен"] in с for с in www_c):
            нужно.append(f"CNAME www.{запись['домен']}: {www_c} — ведёт не на свой апекс")
    elif www_a != [цель]:
        нужно.append(f"A www.{запись['домен']} → {цель} (сейчас {www_a or 'нет записи'})")
    return нужно


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--batch", default="k2", choices=sorted(ПАРТИИ))
    р.add_argument("--verify", action="store_true",
                   help="только проверка: перевод состоялся или нет")
    р.add_argument("--out", default=None, help="куда положить снимок (JSON)")
    а = р.parse_args()
    партия = ПАРТИИ[а.batch]
    цель = партия["target_a"]

    снимки, осталось = [], 0
    for site_id, домен in домены(партия):
        з = снимок(домен)
        з["site_id"] = site_id
        изменения = нужные_изменения(з, цель)
        з["нужные изменения"] = изменения
        снимки.append(з)
        осталось += len(изменения)
        метка = "v" if not изменения else "x"
        авт = з.get("авторитетный") or {}
        print(f"[{метка}] {site_id:9} {домен:22} "
              f"публичный A={з['публичный']['A'] or '—'} "
              f"авторитетный A={авт.get('A') or '—'} "
              f"www={(з['www']['CNAME'] or з['www']['A']) or '—'}")
        for строка in изменения:
            print(f"      нужно: {строка}")

    выход = Path(а.out or (КОРЕНЬ / "var" / "k2-data" / f"dns-{а.batch}.json"))
    выход.parent.mkdir(parents=True, exist_ok=True)
    выход.write_text(json.dumps({"batch": а.batch, "target_a": цель,
                                 "node": партия["node"], "snapshot": снимки},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nснимок (он же план откату): {выход.relative_to(КОРЕНЬ)}")
    if а.verify:
        print("перевод состоялся" if осталось == 0
              else f"перевод НЕ состоялся: не хватает изменений — {осталось}")
    else:
        print(f"изменений требуется: {осталось}")
    return 0 if осталось == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
