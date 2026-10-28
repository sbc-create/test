#!/usr/bin/env python3
"""T348: подготовленные подборки вливаются в `config/collections.json` витрины.

    python3 automation/local/collections-merge.py \
        --storefront var/site-repos/zonafilm-space \
        --new /path/ZONAFILM_SPACE_COLLECTIONS_20261028.json \
        [--check | --dry-run]

Что делает
----------

Дополняет файл подборок витрины новыми подборками, НЕ заменяя существующие, и
проверяет итог по схеме приёмки `schemas/site-collections.schema.json`. Схема
авторитетна: если документ и схема расходятся, прав документ схемы, а не
удобство слияния.

Чего инструмент НЕ делает
-------------------------

* не меняет и не переписывает существующие подборки — только добавляет;
* не придумывает полей: что не пришло из подготовленного файла, того в итоге
  нет. `home_rail` новым подборкам не ставится: полка главной — отдельное
  решение владельца, а не следствие появления подборки;
* не отправляет ничего наружу. Выпуск витрины — push в её репозиторий, и это
  решение владельца, а не инструмента.

Ворота
------

Отказ (код 2), если: ключ новой подборки уже есть; у подборки нет решения об
индексации или пояснения; у работы нет `id`, `slug` или пояснения; итог не
проходит схему. Молчаливое слияние с потерей подборки невозможно: число
подборок до и после сверяется арифметикой.
"""
from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys

СХЕМА = pathlib.Path(__file__).resolve().parents[2] / "schemas" / "site-collections.schema.json"


def _проверить_подборку(с: dict) -> list[str]:
    беды = []
    ключ = str(с.get("key") or "") or "<без ключа>"
    индексация = с.get("indexing") or {}
    if "open" not in индексация:
        беды.append(f"{ключ}: нет решения об индексации (indexing.open)")
    if not str(индексация.get("reason") or "").strip():
        беды.append(f"{ключ}: нет пояснения к решению об индексации")
    работы = с.get("items") or []
    if not работы:
        беды.append(f"{ключ}: нет ни одной работы")
    for р in работы:
        имя = str(р.get("name") or р.get("slug") or "?")
        for поле in ("id", "slug", "reason"):
            if not str(р.get(поле) or "").strip():
                беды.append(f"{ключ} / {имя}: нет поля {поле}")
    return беды


def слить(текущее: dict, новое: dict) -> tuple[dict, list[str], list[str]]:
    было = list(текущее.get("collections") or [])
    добавляемые = list(новое.get("collections") or [])
    беды: list[str] = []
    if not добавляемые:
        беды.append("в подготовленном файле нет ни одной подборки")
    есть_ключи = {str(с.get("key") or "") for с in было}
    новые_ключи: list[str] = []
    for с in добавляемые:
        ключ = str(с.get("key") or "")
        if ключ in есть_ключи:
            беды.append(f"{ключ}: такая подборка в витрине уже есть — "
                        "слияние не заменяет существующие")
        if ключ in новые_ключи:
            беды.append(f"{ключ}: дважды в подготовленном файле")
        новые_ключи.append(ключ)
        беды.extend(_проверить_подборку(с))
    итог = copy.deepcopy(текущее)
    итог["collections"] = было + добавляемые
    if len(итог["collections"]) != len(было) + len(добавляемые):
        беды.append("арифметика слияния не сходится — подборка потерялась")
    return итог, новые_ключи, беды


def по_схеме(документ: dict) -> list[str]:
    if not СХЕМА.is_file():
        return [f"НЕ ИЗМЕРЕНО: нет схемы {СХЕМА}"]
    try:
        import jsonschema
    except ImportError:
        return ["НЕ ИЗМЕРЕНО: jsonschema не установлена"]
    схема = json.loads(СХЕМА.read_text(encoding="utf-8"))
    проверяльщик = jsonschema.Draft7Validator(схема)
    return [f"схема: {'/'.join(str(ч) for ч in о.path)}: {о.message}"
            for о in sorted(проверяльщик.iter_errors(документ),
                            key=lambda о: list(о.path))][:12]


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--storefront", required=True)
    р.add_argument("--new", required=True)
    р.add_argument("--check", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args()
    витрина = pathlib.Path(а.storefront).resolve()
    файл = витрина / "config" / "collections.json"
    подготовленное = pathlib.Path(а.new)
    if not файл.is_file():
        print(f"НЕ ИЗМЕРЕНО: нет {файл}")
        return 2
    if not подготовленное.is_file():
        print(f"НЕ ИЗМЕРЕНО: нет {подготовленное}")
        return 2
    текущее = json.loads(файл.read_text(encoding="utf-8"))
    новое = json.loads(подготовленное.read_text(encoding="utf-8"))
    итог, ключи, беды = слить(текущее, новое)
    if not беды:
        беды = по_схеме(итог)
    голова = (f"{витрина.name}: было {len(текущее.get('collections') or [])}, "
              f"добавляется {len(ключи)} ({', '.join(ключи)}), "
              f"станет {len(итог.get('collections') or [])}")
    if беды:
        print(f"[refuse] {голова}")
        for б in беды:
            print("   ", б)
        return 2
    if а.check or а.dry_run:
        print(f"[ok    ] {голова}; схема пройдена, запись не велась")
        return 0
    файл.write_text(json.dumps(итог, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    print(f"[ok    ] {голова}; схема пройдена, записано в {файл}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
