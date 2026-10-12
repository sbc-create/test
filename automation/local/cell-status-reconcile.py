#!/usr/bin/env python3
"""Паспорт ячейки против следов исполнителя: кто `live` на самом деле.

Расхождение, которое это закрывает. В реестре (`config/site-cells.json`)
`status` стоит `live` у двух ячеек, а витрин отвечает семнадцать. Писателя у
этого поля не было ни одного во всём дереве, и вот почему: ручная активация
закрыта (`admin_exec.активировать` при `dry_run=False` отвечает
`ExecutorRefused`), выпуск идёт очередью, и единственный, кто ЗНАЕТ об удачной
активации, — привилегированный исполнитель. А паспорт лежит в git, куда
исполнителю писать нечем и не следует.

Отсюда и устройство: факт берётся из следов исполнителя
(`/var/lib/site-cells/results/*.json`, `operation=activate`), а в паспорт он
попадает отдельным осознанным шагом через `registry.update` — ту же
проверенную точку, которой пользуется фабрика. Ручная правка JSON обошла бы и
проверку формы, и отметку времени.

По умолчанию НИЧЕГО не пишет: печатает расхождение. Запись — только с
`--confirm-writes`, как у `factory analytics`.

Чего этот инструмент не делает:

* не придумывает статусов: ставит ровно `live` и ровно тем, у кого есть
  подтверждённая НЕ сухая активация с исходом `ok`;
* не создаёт записей в реестре: ячейка со следами, но без паспорта — названа,
  а не добавлена;
* не трогает `not_extracted`. Это слово сказано про происхождение витрины, а
  не про её жизнь, и затереть его значило бы потерять сведение. Такие случаи
  выводятся отдельным разделом как противоречие.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

СЛЕДЫ = Path("/var/lib/site-cells/results")
#: Слово, которое ставится после подтверждённой активации. Единственное.
ЖИВАЯ = "live"
#: Слова, которые этот инструмент не перезаписывает ни при каких следах.
НЕ_ТРОГАТЬ = ("not_extracted",)


def активации(следы: Path) -> dict[str, list[str]]:
    """site_id → времена подтверждённых НЕ сухих активаций с исходом ok."""
    итог: dict[str, list[str]] = defaultdict(list)
    if not следы.is_dir():
        return {}
    for ф in sorted(следы.glob("*.json")):
        try:
            д = json.loads(ф.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue  # битый след — не факт об активации
        if (д.get("operation") == "activate" and д.get("status") == "ok"
                and not д.get("dry_run") and д.get("site_id")):
            итог[д["site_id"]].append(д.get("finished_at") or "")
    return dict(итог)


def разобрать(аргв=None) -> argparse.Namespace:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--results", type=Path, default=СЛЕДЫ,
                   help="каталог следов исполнителя")
    р.add_argument("--registry", type=Path, default=None,
                   help="путь к реестру ячеек (по умолчанию — путь фабрики)")
    р.add_argument("--confirm-writes", action="store_true",
                   help="перевести статус в реестре; без флага только отчёт")
    return р.parse_args(аргв)


def главное(аргв=None) -> int:
    опции = разобрать(аргв)
    from factory.cell import registry as реестр_модуль

    следы = активации(опции.results)
    if not следы:
        print(f"следов активации нет в {опции.results} — сверять не с чем",
              file=sys.stderr)
        return 2

    # `all_cells`, а не `load`: разбор формы делает реестр, и своя копия
    # разбора разошлась бы с ним молча.
    ячейки = {я.site_id: я for я in реестр_модуль.all_cells(опции.registry)}

    перевести: list[tuple[str, str, str]] = []
    противоречия: list[tuple[str, str, int]] = []
    без_паспорта: list[str] = []
    уже: list[str] = []

    for site_id, когда in sorted(следы.items()):
        ячейка = ячейки.get(site_id)
        if ячейка is None:
            без_паспорта.append(site_id)
            continue
        если = ячейка.status
        if если == ЖИВАЯ:
            уже.append(site_id)
        elif если in НЕ_ТРОГАТЬ:
            противоречия.append((site_id, если, len(когда)))
        else:
            перевести.append((site_id, если, max(когда)))

    без_следов = sorted(и for и, я in ячейки.items()
                        if я.status == ЖИВАЯ and и not in следы)

    print(f"следы: {опции.results}, сайтов с подтверждённой активацией "
          f"{len(следы)}; записей в реестре {len(ячейки)}")
    print(f"\nуже live и подтверждено следами: {len(уже)} "
          f"{sorted(уже) if уже else ''}")

    if перевести:
        print(f"\nпаспорт отстал от следов — {len(перевести)}:")
        for site_id, было, когда in перевести:
            print(f"   {site_id:16} {было:14} → {ЖИВАЯ}   последняя активация {когда}")
    else:
        print("\nпаспорт от следов не отстал")

    if противоречия:
        print(f"\nпротиворечие (статус не перезаписывается) — {len(противоречия)}:")
        for site_id, было, сколько in противоречия:
            print(f"   {site_id:16} статус {было!r}, а активаций {сколько}: "
                  "происхождение и жизнь расходятся, решает человек")

    if без_паспорта:
        print(f"\nследы есть, записи в реестре нет — {len(без_паспорта)}: "
              f"{без_паспорта}; запись НЕ создаётся")

    if без_следов:
        print(f"\nв реестре live, а следов активации нет — {len(без_следов)}: "
              f"{без_следов}; статус НЕ снимается: отсутствие следа не "
              "доказывает отсутствия активации")

    if not опции.confirm_writes:
        print(f"\nничего не записано: нужен --confirm-writes "
              f"(к переводу {len(перевести)})")
        return 1 if перевести else 0

    записано, отказы = 0, []
    for site_id, _было, _когда in перевести:
        try:
            реестр_модуль.update(site_id, {"status": ЖИВАЯ},
                                 path=опции.registry)
            записано += 1
        except Exception as сбой:  # noqa: BLE001 — отказ называется, а не глотается
            отказы.append(f"{site_id}: {type(сбой).__name__}: {сбой}")
    print(f"\nзаписано статусов: {записано} из {len(перевести)}")
    for о in отказы:
        print(f"   ОТКАЗ {о}", file=sys.stderr)
    return 1 if отказы else 0


if __name__ == "__main__":
    raise SystemExit(главное())
