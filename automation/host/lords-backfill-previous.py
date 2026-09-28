#!/usr/bin/env python3
"""Заводит ссылку `previous` действующим витринам по журналу переключений.

Зачем
-----

`LORDS-ROLLBACK-POINT-MISSING-39`. Ссылку `previous` не создавал никто, и
`lords-refresh-guard` писал в rollback.json `null`. Исправление в
`factory/lords/refresh_release.py` заводит её при следующем переключении — но
витрины, уже стоящие на своих релизах, до этого момента остаются без записанной
точки отката. Здесь она восстанавливается из журнала `release-log.jsonl`,
который вёлся всё это время и знает и `from`, и `to`.

Что проверяется перед записью
-----------------------------

Ничего не додумывается. Ссылка появляется только когда сходится всё:

* журнал существует и его последняя запись разбирается;
* `to` последней записи совпадает с тем, куда указывает `current` сейчас;
* `from` не пуст и такой каталог релиза действительно лежит на диске;
* `from` не совпадает с `to`.

Любое расхождение — отказ по этой витрине, а не запись «по смыслу». Точка
отката, указывающая не туда, хуже отсутствующей: по ней откатятся.

Запуск:
    sudo python3 automation/host/lords-backfill-previous.py            # показать
    sudo python3 automation/host/lords-backfill-previous.py --apply    # записать
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

БАЗА = Path("/srv/lords")
САЙТЫ = ("lords-01", "lords-02", "lords-03")
ЖУРНАЛ = "release-log.jsonl"


def последняя_запись(путь: Path) -> dict | None:
    try:
        строки = [с for с in путь.read_text(encoding="utf-8").splitlines() if с.strip()]
    except OSError:
        return None
    for строка in reversed(строки):
        try:
            return json.loads(строка)
        except json.JSONDecodeError:
            continue
    return None


def разобрать(сайт: str) -> dict:
    рантайм = БАЗА / сайт
    итог: dict[str, object] = {"site": сайт}

    ссылка = рантайм / "current"
    if not ссылка.is_symlink():
        return {**итог, "verdict": "ОТКАЗ", "reason": "нет ссылки current"}
    текущий = ссылка.resolve().name
    итог["current"] = текущий

    # Ссылка есть — ещё не значит, что точка отката есть.
    #
    # Первая версия этого инструмента возвращала УЖЕ_ЕСТЬ по одному факту
    # существования символической ссылки и потому объявляла целыми ровно те
    # витрины, где хранение удалило цель. Висячая ссылка — это не точка отката,
    # а обещание вернуться туда, чего нет; по ней и откатятся.
    если_есть = рантайм / "previous"
    if если_есть.is_symlink():
        цель_ссылки = Path(os.readlink(если_есть))
        if not цель_ссылки.is_absolute():
            цель_ссылки = рантайм / цель_ссылки
        if цель_ссылки.is_dir():
            return {**итог, "verdict": "УЖЕ_ЕСТЬ", "previous": цель_ссылки.name}
        итог["dangling"] = цель_ссылки.name

    запись = последняя_запись(рантайм / ЖУРНАЛ)
    if запись is None:
        return {**итог, "verdict": "ОТКАЗ", "reason": "журнал пуст или нечитаем"}
    итог["journal"] = {"from": запись.get("from"), "to": запись.get("to"),
                       "at": запись.get("at")}

    если_то = запись.get("to")
    если_от = запись.get("from")
    if если_то != текущий:
        return {**итог, "verdict": "ОТКАЗ",
                "reason": f"журнал ведёт на {если_то}, а current указывает на {текущий}"}
    if not если_от:
        return {**итог, "verdict": "НЕКУДА",
                "reason": "первое переключение витрины: откатываться некуда"}
    if если_от == если_то:
        return {**итог, "verdict": "ОТКАЗ", "reason": "from и to совпадают"}
    каталог = рантайм / "releases" / если_от
    if not каталог.is_dir():
        return {**итог, "verdict": "ОТКАЗ",
                "reason": f"релиз {если_от} по журналу есть, а каталога нет"}

    return {**итог, "verdict": "ГОТОВО", "previous": если_от, "target": str(каталог)}


def записать(решение: dict) -> None:
    рантайм = БАЗА / str(решение["site"])
    цель = Path(str(решение["target"]))
    временная = рантайм / ".previous.new"
    if временная.exists() or временная.is_symlink():
        временная.unlink()
    # os.replace поверх висячей ссылки работает, но существующую проверяем явно.
    временная.symlink_to(цель)
    os.replace(временная, рантайм / "previous")


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--apply", action="store_true", help="записать; без него только показ")
    args = р.parse_args()

    решения = [разобрать(с) for с in САЙТЫ]
    отказы = 0
    for решение in решения:
        print(json.dumps(решение, ensure_ascii=False))
        if решение["verdict"] == "ОТКАЗ":
            отказы += 1
        if args.apply and решение["verdict"] == "ГОТОВО":
            записать(решение)
            проверка = (БАЗА / str(решение["site"]) / "previous").resolve().name
            если_ждали = решение["previous"]
            print(f"  записано: previous -> {проверка} "
                  f"({'совпало' if проверка == если_ждали else 'НЕ СОВПАЛО'})")
    return 1 if отказы else 0


if __name__ == "__main__":
    sys.exit(main())
