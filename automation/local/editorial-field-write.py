#!/usr/bin/env python3
"""Запись редакционного поля карточки штатным путём очереди.

    python3 automation/local/editorial-field-write.py --site zonafilm.space \
        --key 01a1252c-9a84-7175-bcf2-ec7cea1cf1b0 \
        --field name --value "История наших отношений" \
        --actor "zona-01/posters-titles/run-7" \
        --reason "подтверждено по ru-статье и Wikidata (путь D200)" [--dry-run]

Зачем. Передача 114: подтверждённое русское название внести было нечем.
Описания публикует редактор (`factory.qwen`), а файл правок заменяется целиком,
поэтому запись `name` в обход либо отказывала его следующей доставке («кто-то
записал новее»), либо исчезала при ней. Хранилище правок `name` принимало
давно — не хватало сохранения состава и операции, которая идёт ТЕМ ЖЕ путём.

Что делает: читает ЖИВОЙ файл правок витрины, добавляет к составу одну запись с
названным полем и подаёт полный состав через `editorial._подать_правки` — то
есть подготовка в управляющем слое, заявка в очередь, запись исполнителем от
имени учётной записи сайта и ожидание исхода `edited`. Сам в хранилище витрины
не пишет и писать не может.

Чего не делает: не трогает описания редактора (они переносятся как есть вместе
с авторством), не отключает заставу чужой правки, не повторяет заявку слепо.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import editorial_store  # noqa: E402
from factory.cell import runtime  # noqa: E402
from factory.qwen import editorial, registry  # noqa: E402


#: Поля, которые витрина берёт из записи КАТАЛОГА (главная, сетки, поиск,
#: заголовок и постер карточки). Соответствие полей — `editorial_overlay.В_ЗАПИСИ`.
ПОЛЯ_КАТАЛОГА = ("name", "original_name", "poster_url", "year", "kind")


def _похоже_на_uuid(значение: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F-]{32,40}", значение or ""))


def _слаг_по_ид(s, ид: str) -> str:
    """Слаг записи по её постоянному идентификатору — из снимка витрины.

    Связь «id → slug» есть только в подробностях: каталог её не несёт. Файл
    читается потоком по записям верхнего уровня, чтобы не разбирать десятки
    мегабайт ради одной строки.
    """
    место = runtime.размещение(s.site_id)
    путь = pathlib.Path(место.data_dir) / f"{s.site_id}-details.json"
    try:
        подробности = json.loads(путь.read_text(encoding="utf-8")).get("details") or {}
    except (OSError, ValueError):
        return ""
    for слаг, запись in подробности.items():
        if str((запись or {}).get("id") or "") == str(ид):
            return слаг
    return ""


def главное(argv=None) -> int:
    ap = argparse.ArgumentParser(description="запись редакционного поля карточки")
    ap.add_argument("--site", required=True, help="домен витрины")
    ap.add_argument("--key", required=True,
                    help="идентификатор записи (постоянный id, он же ключ накладки)")
    ap.add_argument("--field", required=True, choices=sorted(editorial_store.ПОЛЯ))
    ap.add_argument("--value", required=True)
    ap.add_argument("--actor", required=True,
                    help="кто вносит: <роль>/<автоматизация>/<прогон>")
    ap.add_argument("--reason", required=True, help="почему, с источником")
    ap.add_argument("--dry-run", action="store_true",
                    help="показать состав и не подавать заявку")
    a = ap.parse_args(argv)

    s = editorial._сайт(a.site, опрашивать_сеть=False)
    if registry.механизм(s) != "editorial-queue":
        print(f"{s.domain}: механизм доставки {registry.механизм(s)!r}, а эта "
              "операция рассчитана на очередь ячеек", file=sys.stderr)
        return 2

    # Застава чужой правки проверяется ДО сборки: слепая перезапись запрещена,
    # и решение о расхождении принимает человек, а не этот сценарий.
    беда = editorial._чужая_правка(s)
    if беда:
        print(f"{s.domain}: {беда}. Состав не собирается", file=sys.stderr)
        return 3

    # Ключ накладки зависит от того, КУДА ложится поле, и это измерено, а не
    # выведено из названия.
    #
    # Витрина применяет накладку к записи каталога (`наложить_на_запись`) по
    # `id`, затем по слагу. Но в записи каталога Lords/Zona поля `id` НЕТ
    # вовсе — там только slug, title, poster, kind, year, url, published_at.
    # Поэтому правка `name`, записанная под UUID, не меняет ни заголовок, ни
    # сетку, ни поиск: она молча не находится. Проверено 2026-10-10 на
    # выложенном модуле zonafilm.space: под ключом-UUID `_edited` остаётся
    # False, под ключом-слагом название подставляется.
    #
    # Поля подробностей (`description`, `seo_*`) наоборот ложатся по `id`:
    # запись подробностей его несёт. Поэтому ключ приводится к нужному виду
    # здесь, один раз, а не оставляется на память вызывающего.
    ключ_записи = a.key
    if a.field in ПОЛЯ_КАТАЛОГА and _похоже_на_uuid(a.key):
        слаг = _слаг_по_ид(s, a.key)
        if not слаг:
            print(f"{s.domain}: поле {a.field} ложится в запись каталога, а она "
                  f"ищется по слагу; слаг для {a.key} в снимке не найден",
                  file=sys.stderr)
            return 5
        print(f"поле {a.field} — каталожное: ключ приведён к слагу {слаг!r} "
              f"(запись каталога не несёт id)")
        ключ_записи = слаг

    состав: dict[str, dict] = {}
    for ключ, запись in editorial._живые_правки(s).items():
        поля = {к: з for к, з in (запись.get("fields") or {}).items()
                if з not in (None, "")}
        if поля:
            состав[ключ] = {"fields": поля, "actor": запись.get("actor"),
                            "reason": запись.get("reason")}
    гнездо = состав.setdefault(ключ_записи, {"fields": {}})
    гнездо["fields"][a.field] = a.value
    гнездо["actor"] = a.actor
    гнездо["reason"] = a.reason

    содержимое = editorial_store.собрать(s.site_id, состав,
                                         actor=a.actor, reason=a.reason)
    print(json.dumps({"site": s.domain, "entries": len(содержимое["overrides"]),
                      "digest": editorial_store.отпечаток(содержимое),
                      "key": ключ_записи, "field": a.field},
                     ensure_ascii=False, indent=1))
    if a.dry_run:
        print("сухой прогон: заявка не подавалась")
        return 0

    try:
        итог = editorial._подать_правки(s, состав, author=a.actor, reason=a.reason)
    except editorial.ОперацияОтклонена as ош:
        print(f"отказ: {ош}", file=sys.stderr)
        return 4
    print(json.dumps(итог, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
