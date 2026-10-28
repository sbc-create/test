#!/usr/bin/env python3
"""Доставить витрине Lords проверки режима индексации (MOD-216, пробел 1 из 4).

    python3 automation/local/wire-lords-indexing-checks.py \
        --source var/site-repos/lordserials22-info \
        --target var/site-repos/1lordserials1-online \
        --target var/site-repos/lordserial33-biz [--check] [--dry-run]

Что измерено и почему инструмент нужен
--------------------------------------

Замер 28.10 по всем действующим витринам Lords: механизм
`src/indexing_mode.py` есть у ВСЕХ ТРЁХ, а проверки его поведения
(`checks/indexing_mode_rules.py`, `checks/indexing_live_switch.py`) — только у
`lordserials22.info`. То есть у двух витрин механизм, решающий, открыт сайт
поисковику или закрыт, работает без проверки, что он не откроется и не
закроется случайно.

Почему перенос безопасен — проверено, а не предположено
-------------------------------------------------------

1. Обе проверки уже параметризованы: домен они берут из `config/site.json`
   (`ДОМЕН = НАСТРОЙКА["domain"]`), а не из своего текста. Встречающийся в них
   буквальный `lordserials22.site` — это НАРОЧНО чужой сайт в данных опыта:
   им доказывается, что механизм отвергает запись соседнего домена. На любой
   витрине он остаётся чужим и осмысленным.
2. Механизм у `1lordserials1.online` и `lordserials22.info` побайтово
   одинаков (sha256 совпадает, 8237 байт).
3. У `lordserial33.biz` механизм РАЗОШЁЛСЯ: 9144 байта, один добавленный
   блок — адрес карты достаётся из `lords_sitemap_layer`, когда ядро зовёт
   `_тело_robots()` без адреса. Расхождение задевает ровно то утверждение
   проверки, которое гласит «robots.txt без карты не обещает карту», поэтому
   оно ИЗМЕРЕНО, а не оценено на глаз: вызов `robots_txt(ОТКРЫТ)` без адреса
   у обоих модулей не содержит строки `Sitemap:`. Проверка проходит на обеих
   витринах без правки.

Этот инструмент повторяет замер пункта 3 перед каждой доставкой и отказывает,
если поведение модулей разойдётся. Расхождение исходников само по себе
доставку не останавливает — останавливает расхождение НАБЛЮДАЕМОГО поведения,
потому что именно его и закрепляет проверка.

Чего инструмент не делает
-------------------------

* не правит ни механизм, ни рантайм, ни настройку витрины: только добавляет
  файлы проверок;
* не перезаписывает уже существующий файл проверки — такая витрина
  пропускается с названной причиной, чтобы не затереть чужую работу;
* не открывает и не закрывает ни один домен;
* без любого нужного условия отказывает с причиной и не меняет ни файла.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys

ПРОВЕРКИ = ("indexing_mode_rules.py", "indexing_live_switch.py")
НУЖНЫЕ_КЛЮЧИ = ("domain",)


def _модуль_режима(корень: pathlib.Path):
    """Загружает src/indexing_mode.py витрины в изоляции."""
    f = корень / "src" / "indexing_mode.py"
    if not f.is_file():
        return None, f"нет {f}"
    sys.path.insert(0, str(корень / "src"))
    try:
        спец = importlib.util.spec_from_file_location(
            f"им_{hashlib.sha256(str(f).encode()).hexdigest()[:8]}", f)
        if спец is None or спец.loader is None:
            return None, f"не загружается: {f}"
        м = importlib.util.module_from_spec(спец)
        спец.loader.exec_module(м)
        return м, ""
    except Exception as сбой:  # noqa: BLE001 — любая беда модуля = отказ доставки
        return None, f"модуль не исполняется: {type(сбой).__name__}: {сбой}"
    finally:
        sys.path.pop(0)


def _наблюдаемое(корень: pathlib.Path) -> tuple[dict | None, str]:
    """Поведение, которое закрепляют переносимые проверки."""
    м, причина = _модуль_режима(корень)
    if м is None:
        return None, причина
    try:
        наблюдение = {
            "закрытый": м.robots_txt(м.ЗАКРЫТ).strip(),
            "открытый обещает карту": "Sitemap:" in м.robots_txt(м.ОТКРЫТ),
            "открытый разрешает": "Allow: /" in м.robots_txt(м.ОТКРЫТ),
            "мета закрытого": м.МЕТА[м.ЗАКРЫТ],
            "мета открытого": м.МЕТА[м.ОТКРЫТ],
            "неизвестное закрывает": м.robots_txt("ЧТО-ТО") == м.ЗАКРЫТЫЙ_ROBOTS,
        }
    except Exception as сбой:  # noqa: BLE001
        return None, f"поведение не снято: {type(сбой).__name__}: {сбой}"
    return наблюдение, ""


def _настройка(корень: pathlib.Path) -> tuple[dict | None, str]:
    f = корень / "config" / "site.json"
    if not f.is_file():
        return None, f"нет {f}"
    try:
        return json.loads(f.read_text(encoding="utf-8")), ""
    except json.JSONDecodeError as сбой:
        return None, f"настройка не читается: {сбой}"


def доставить(источник: pathlib.Path, цель: pathlib.Path,
              писать: bool) -> tuple[str, str]:
    """Возвращает (исход, пояснение). Исход: ok | skip | refuse."""
    эталон, причина = _наблюдаемое(источник)
    if эталон is None:
        return "refuse", f"источник: {причина}"
    своё, причина = _наблюдаемое(цель)
    if своё is None:
        return "refuse", f"цель: {причина}"

    расхождения = [к for к in эталон if эталон[к] != своё[к]]
    if расхождения:
        подробно = "; ".join(
            f"{к}: источник {эталон[к]!r}, цель {своё[к]!r}" for к in расхождения)
        return "refuse", ("наблюдаемое поведение механизма расходится, перенос "
                          f"остановлен — {подробно}")

    настройка, причина = _настройка(цель)
    if настройка is None:
        return "refuse", причина
    нет_ключей = [к for к in НУЖНЫЕ_КЛЮЧИ if not настройка.get(к)]
    if нет_ключей:
        return "refuse", (f"в config/site.json нет значений: {', '.join(нет_ключей)} "
                          "— проверка берёт домен оттуда, подставлять нельзя")

    каталог = цель / "checks"
    if not каталог.is_dir():
        return "refuse", f"нет каталога {каталог}"

    уже = [и for и in ПРОВЕРКИ if (каталог / и).is_file()]
    если_нет = [и for и in ПРОВЕРКИ if и not in уже]
    if not если_нет:
        return "skip", "обе проверки уже на месте, ничего не переписываю"

    for имя in если_нет:
        откуда = источник / "checks" / имя
        if not откуда.is_file():
            return "refuse", f"в источнике нет {откуда}"
        if писать:
            (каталог / имя).write_bytes(откуда.read_bytes())
    хвост = f"; уже были: {', '.join(уже)}" if уже else ""
    действие = "доставлено" if писать else "будет доставлено"
    return "ok", f"{действие}: {', '.join(если_нет)}{хвост}"


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--source", required=True,
                   help="витрина-источник проверок (lordserials22-info)")
    р.add_argument("--target", action="append", required=True)
    р.add_argument("--check", action="store_true",
                   help="только вердикт: 0 — доставлять нечего, 1 — есть пробел")
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args()

    источник = pathlib.Path(а.source).resolve()
    писать = not (а.check or а.dry_run)
    отказы = пробелы = 0

    for путь in а.target:
        цель = pathlib.Path(путь).resolve()
        исход, пояснение = доставить(источник, цель, писать)
        print(f"[{исход:6s}] {цель.name}: {пояснение}")
        if исход == "refuse":
            отказы += 1
        elif исход == "ok":
            пробелы += 1

    if отказы:
        print(f"ОТКАЗ по {отказы} витринам: причина названа выше, файлы не менялись")
        return 2
    if а.check:
        print("пробел есть" if пробелы else "пробела нет")
        return 1 if пробелы else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
