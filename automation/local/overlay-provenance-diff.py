#!/usr/bin/env python3
"""Переклеймляет ли публикация авторство соседних записей — по живым данным.

Повод. Правка 85bf620 (12.10 22:57Z) называется «публикация переклеймляла
авторство всей истории накладки — исправлено». Служба моста запущена 12.10
17:42Z, то есть за десять минут ДО этой правки, и с тех пор не перезапускалась:
на диске правка есть, в памяти работает прежний код. Дата процесса — лишь
подозрение; здесь дефект проверяется ПО ДАННЫМ витрин.

Что считается подменой. У записи, которую мы публиковали раньше, в ЖИВОМ файле
витрины стоит автор (или причина) последней публикации ДРУГОГО тайтла. Публикация
одного текста вправе менять происхождение только своей записи.

Два устройства хранилищ, оба проверяются:

* `items[]` с полем `provenance` (adapter animedia/animego/yummy) — рядом лежит
  `title-overlays.last-good.json`, состояние до последнего выпуска, и сверка
  идёт с ним;
* `overrides{}` с полями `actor`/`reason` (adapter lords: Lords и Zona) — автора
  по записям хранит НАШ учёт `published.json`, и сверка идёт с ним.

Третий исход обязателен. Нет живого файла, нет нашего учёта, не та структура —
«не измерено» с причиной. «Подмен не найдено» про такой домен не говорится:
именно так тихое отсутствие данных и выглядит как успех.

Чем отличается от `editorial-overlay-before-after.py`. Тот сверяет витрину с
ЗАРАНЕЕ снятым снимком и без снимка честно отказывает — поэтому про публикации
09–12.10, когда снимков ещё не делали, он сказать ничего не может. Здесь
основанием служат данные, которые витрина и так хранит: её прошлая хорошая
копия и наш учёт публикаций. Снимок точнее для приёмки будущей публикации;
этот инструмент отвечает про уже случившееся и про всю сеть сразу.

Только чтение. Постоянные данные витрин принадлежат витринам
(docs/RUNTIME_DATA_OWNERSHIP.md): ни одной записи, ни одного восстановления.

    python3 automation/local/overlay-provenance-diff.py
    python3 automation/local/overlay-provenance-diff.py --domain zonafilm.space
    python3 automation/local/overlay-provenance-diff.py --json

Коды: 0 — подмен не найдено; 1 — найдены; 2 — не измерено ни по одному домену.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

from factory.qwen import registry  # noqa: E402

ЖИВОЕ_ПРЕЖНЕЕ = "title-overlays.last-good.json"
НАШ_УЧЁТ = "published.json"


def _читать(п: pathlib.Path):
    try:
        return json.loads(п.read_text(encoding="utf-8")), ""
    except FileNotFoundError:
        return None, f"нет файла {п}"
    except OSError as сбой:
        return None, f"{п}: {сбой}"
    except ValueError as сбой:
        return None, f"{п}: не JSON ({сбой})"


def по_slug(д: dict) -> tuple[dict | None, str]:
    """Записи накладки вида items[] → {slug: запись}."""
    сп = д.get("items")
    if not isinstance(сп, list):
        return None, "в файле нет списка items"
    итог = {str(и["slug"]): и for и in сп if isinstance(и, dict) and и.get("slug")}
    return (итог, "") if итог else (None, "список items пуст")


def по_title_id(д: dict) -> tuple[dict | None, str]:
    """Записи доставленного файла вида overrides{} → {title_id: запись}."""
    зп = д.get("overrides")
    if not isinstance(зп, dict):
        return None, "в файле нет словаря overrides"
    итог = {str(к): v for к, v in зп.items() if isinstance(v, dict)}
    return (итог, "") if итог else (None, "словарь overrides пуст")


def сверить_items(живой: pathlib.Path, прежний: pathlib.Path) -> dict:
    """Накладка с provenance: сверка с её же прошлой хорошей копией."""
    a, беда = _читать(живой)
    if a is None:
        return {"измерено": False, "почему": беда}
    b, беда = _читать(прежний)
    if b is None:
        return {"измерено": False, "почему": f"сравнивать не с чем: {беда}"}
    A, беда = по_slug(a)
    if A is None:
        return {"измерено": False, "почему": f"живой файл: {беда}"}
    B, беда = по_slug(b)
    if B is None:
        return {"измерено": False, "почему": f"прошлая копия: {беда}"}
    общие = sorted(set(A) & set(B))
    подмены = [
        {"ключ": s,
         "было": (B[s].get("provenance") or {}).get("author"),
         "стало": (A[s].get("provenance") or {}).get("author")}
        for s in общие
        if A[s].get("provenance") != B[s].get("provenance")
        and A[s].get("body") == B[s].get("body")
    ]
    return {
        "измерено": True,
        "вид": "items+provenance",
        "сверено_с": str(прежний),
        "записей": len(A),
        "сверено": len(общие),
        "новых": sorted(set(A) - set(B)),
        "подмены": подмены,
        "авторы": collections.Counter(
            (и.get("provenance") or {}).get("author", "?") for и in A.values()),
    }


def сверить_overrides(живой: pathlib.Path, наш: pathlib.Path) -> dict:
    """Доставленный файл Lords/Zona: сверка с нашим учётом published.json.

    Сверяется по `title_id`: в живом файле ключ записи — он, в нашем учёте он
    лежит полем. Записи, которых в нашем учёте нет (ручные правки, восстановления),
    не трогаются: про их автора наш учёт ничего не знает, и молча объявлять их
    подменой нельзя.
    """
    a, беда = _читать(живой)
    if a is None:
        return {"измерено": False, "почему": беда}
    b, беда = _читать(наш)
    if b is None:
        return {"измерено": False, "почему": f"нашего учёта нет: {беда}"}
    A, беда = по_title_id(a)
    if A is None:
        return {"измерено": False, "почему": f"живой файл: {беда}"}
    сп = b.get("items")
    if not isinstance(сп, list) or not сп:
        return {"измерено": False, "почему": "в нашем учёте нет списка items"}
    наши = {str(и.get("title_id")): и for и in сп
            if isinstance(и, dict) and и.get("title_id")}
    if not наши:
        return {"измерено": False, "почему": "в нашем учёте нет ни одного title_id"}
    общие = sorted(set(A) & set(наши))
    if not общие:
        return {"измерено": False,
                "почему": "ни одна запись живого файла не опознана нашим учётом"}
    подмены = []
    for к in общие:
        наш_автор = str((наши[к].get("provenance") or {}).get("author") or "")
        живой_актор = str(A[к].get("actor") or "")
        if наш_автор and живой_актор and наш_автор != живой_актор:
            подмены.append({"ключ": к, "slug": наши[к].get("slug"),
                            "было": наш_автор, "стало": живой_актор})
    # Причина записи — второй след того же дефекта: она называет СВОЙ тайтл.
    чужая_причина = []
    for к in общие:
        slug = str(наши[к].get("slug") or "")
        причина = str(A[к].get("reason") or "")
        if slug and причина and slug not in причина and "тайтла" in причина:
            чужая_причина.append({"ключ": к, "slug": slug, "причина": причина})
    return {
        "измерено": True,
        "вид": "overrides+actor",
        "сверено_с": str(наш),
        "записей": len(A),
        "сверено": len(общие),
        "не_наши": sorted(set(A) - set(наши)),
        "подмены": подмены,
        "чужая_причина": чужая_причина,
        "авторы": collections.Counter(str(и.get("actor") or "?") for и in A.values()),
    }


def сверить_домен(s) -> dict:
    живой = pathlib.Path(registry.путь_доставки(s))
    try:
        наш_каталог = pathlib.Path(registry.корень_хранилища(s.adapter)) / s.domain
    except Exception as сбой:  # адаптер без корня хранилища — честная причина
        return {"измерено": False, "почему": f"корень хранилища не определён: {сбой}"}
    if живой.name == "title-overlays.json":
        return сверить_items(живой, живой.parent / ЖИВОЕ_ПРЕЖНЕЕ)
    return сверить_overrides(живой, наш_каталог / НАШ_УЧЁТ)


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description="подмена авторства соседних записей при публикации",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", action="append", default=[])
    р.add_argument("--json", action="store_true")
    р.add_argument("--authors", action="store_true",
                   help="печатать разбивку по авторам (длинно)")
    дов = р.parse_args(аргв)

    сайты = [s for s in registry.собрать(опрашивать_сеть=False)
             if not дов.domain or s.domain in дов.domain]
    нет_в_реестре = [д for д in дов.domain
                     if д not in {s.domain for s in сайты}]
    итоги = {s.domain: сверить_домен(s) for s in сайты}

    измерено = [и for и in итоги.values() if и["измерено"]]
    подмен = sum(len(и["подмены"]) for и in измерено)
    причин = sum(len(и.get("чужая_причина", [])) for и in измерено)
    свод = {"измерено": len(измерено), "домены": len(итоги),
            "подмен_авторства": подмен, "записей_с_чужой_причиной": причин}

    if дов.json:
        # Машинный вывод — один документ: сводка внутри, а не строкой после.
        печать = {д: {к: (dict(v) if isinstance(v, collections.Counter) else v)
                      for к, v in и.items()} for д, и in итоги.items()}
        print(json.dumps({"домены": печать, "нет_в_реестре": нет_в_реестре,
                          "сводка": свод}, ensure_ascii=False, indent=2))
        if not измерено:
            return 2
        return 1 if (подмен or причин) else 0
    else:
        for дом in sorted(итоги):
            и = итоги[дом]
            if not и["измерено"]:
                print(f"{дом}: НЕ ИЗМЕРЕНО — {и['почему']}")
                continue
            подмен = len(и["подмены"])
            print(f"{дом}: записей {и['записей']}, сверено {и['сверено']}"
                  f" ({и['вид']}); подмена авторства у {подмен}")
            for п in и["подмены"][:5]:
                print(f"    {п.get('slug') or п['ключ']}: автор {п['было']}"
                      f" → {п['стало']}")
            for п in и.get("чужая_причина", [])[:5]:
                print(f"    {п['slug']}: причина записи называет чужой тайтл"
                      f" — {п['причина'][:70]}")
            if дов.authors:
                for автор, сколько in и["авторы"].most_common():
                    print(f"    автор {автор}: {сколько}")
        for дом in нет_в_реестре:
            print(f"{дом}: НЕ ИЗМЕРЕНО — домена нет в реестре ячеек")

    print()
    print(f"домены: измерено {len(измерено)} из {len(итоги)};"
          f" подмен авторства {подмен}; записей с чужой причиной {причин}")
    if not измерено:
        return 2
    return 1 if (подмен or причин) else 0


if __name__ == "__main__":
    sys.exit(main())
