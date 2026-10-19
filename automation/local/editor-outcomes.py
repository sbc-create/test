#!/usr/bin/env python3
"""Чем кончаются задания редактора: доли исходов по периодам. Только чтение.

Зачем. «Редактор работает» и «редактор пишет тексты» — разные утверждения. За
ночь 18→19.10 из 83 исходов 45 были `SOURCES_MISSING`: прогон шёл, модель
работала, текста не появлялось. Чтобы судить о правках источников (MOD-85), доли
исходов нужно сравнивать до и после, а не смотреть на один прогон.

Считается по `*.run.json` самих прогонов: поле `outcomes`. Журнал `runs.jsonl`
исходов заданий не несёт — считать по нему ошибка, она уже делалась.

    python3 automation/local/editor-outcomes.py --since 2026-10-18T20:00Z
    python3 automation/local/editor-outcomes.py --split 2026-10-19T06:30Z
    python3 automation/local/editor-outcomes.py --split 2026-10-19T06:30Z --json

`--split` делит прогоны на «до» и «после» указанного времени и печатает доли
рядом: именно так видно, изменилось ли что-то после правки.

Коды: 0 — посчитано; 2 — прогонов в периоде нет.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import sys

ПРОГОНЫ = pathlib.Path("/home/claude/wt-portable-site-cell-01/var/editor-runs")
ШЛЮЗ = ПРОГОНЫ / "gate.jsonl"

#: Ниже этого числа заданий доли шумят сильнее любой правки.
ПОРОГ_ЗАДАНИЙ = 30
#: Ключевой исход, по которому судят о правках источников (MOD-85).
КЛЮЧЕВОЙ_ИСХОД = "SOURCES_MISSING"


def _время(метка: str) -> dt.datetime | None:
    for формат in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%MZ", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(метка, формат).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


def прогоны(каталог: pathlib.Path, с: dt.datetime | None,
            по: dt.datetime | None) -> list[tuple[dt.datetime, dict]]:
    итог = []
    for п in sorted(каталог.glob("*.run.json")):
        try:
            когда = dt.datetime.strptime(п.name.split(".")[0], "%Y%m%dT%H%M%SZ").replace(
                tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if (с and когда < с) or (по and когда > по):
            continue
        try:
            итог.append((когда, json.loads(п.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return итог


def свод(записи: list[tuple[dt.datetime, dict]]) -> dict:
    исходы = collections.Counter()
    публикаций = 0
    for _, д in записи:
        for и in д.get("outcomes") or []:
            исходы[str(и.get("outcome") or "?")] += 1
        публикаций += len((д.get("self_report") or {}).get("urls") or [])
    всего = sum(исходы.values())
    return {
        "прогонов": len(записи),
        "заданий": всего,
        "публикаций": публикаций,
        "исходы": dict(исходы),
        "доли": {к: round(100 * v / всего, 1) for к, v in исходы.items()} if всего else {},
        "период": (f"{записи[0][0]:%Y-%m-%dT%H:%MZ}..{записи[-1][0]:%Y-%m-%dT%H:%MZ}"
                   if записи else ""),
    }


def направления(журнал: pathlib.Path = ШЛЮЗ) -> dict:
    """Направление каждого прогона по журналу шлюза: `anime` или `lords`.

    Направление решает, КАКОЙ источник спрашивают: у anime это шикимори с
    успехом 98.8 %, у lords — Википедия с 17.0 %. Поэтому доля
    `SOURCES_MISSING` зависит от состава заданий сильнее, чем от любой нашей
    правки, и сравнивать части разного состава нельзя.
    """
    итог: dict[str, str] = {}
    try:
        строки = журнал.read_text(encoding="utf-8").splitlines()
    except OSError:
        return итог
    for с in строки:
        if not с.strip():
            continue
        try:
            з = json.loads(с)
        except ValueError:
            continue
        ворота = з.get("gate") or {}
        if not ворота.get("run"):
            continue
        метка = str(з.get("at") or "")
        куда = ворота.get("direction")
        if метка and куда:
            итог[метка] = str(куда)
    return итог


def _состав(записи, карта: dict) -> dict:
    """Сколько заданий пришло из каждого направления."""
    счёт: dict[str, int] = {}
    for когда, д in записи:
        метка = f"{когда:%Y-%m-%dT%H:%M:%SZ}"
        куда = карта.get(метка)
        заданий = len(д.get("outcomes") or [])
        if not заданий:
            continue
        счёт[куда or "не измерено"] = счёт.get(куда or "не измерено", 0) + заданий
    return счёт


def _доли_состава(состав: dict) -> dict:
    всего = sum(состав.values())
    if not всего:
        return {}
    return {к: v / всего for к, v in состав.items()}


def вердикт(до: dict, после: dict) -> tuple[str, str]:
    """Одно из четырёх слов и причина. Молчания среди исходов нет.

    Порядок проверок намеренно такой: сначала хватает ли материала, потом
    сравнимы ли части по составу, и только потом — величина различия. Если
    переставить, получится вывод о правке, объяснённый составом заданий.
    """
    мало = min(до.get("заданий", 0), после.get("заданий", 0))
    if мало < ПОРОГ_ЗАДАНИЙ:
        return ("данных недостаточно",
                f"в меньшей части {мало} заданий при пороге {ПОРОГ_ЗАДАНИЙ}: "
                "доли на таком числе шумят сильнее любой правки")

    сд, сп = до.get("направления") or {}, после.get("направления") or {}
    if not сд or not сп or "не измерено" in сд or "не измерено" in сп:
        return ("данных недостаточно",
                f"состав заданий по направлениям не прочитан (до: {сд or '—'}, "
                f"после: {сп or '—'}); без него разница объясняется и правкой, "
                "и источником")
    дд, дп = _доли_состава(сд), _доли_состава(сп)
    расхождение = max(abs(дд.get(к, 0) - дп.get(к, 0))
                      for к in set(дд) | set(дп))
    if расхождение > 0.2:
        return ("данных недостаточно",
                f"состав заданий различается (до: {сд}, после: {сп}): "
                f"доли направлений расходятся на {расхождение * 100:.0f} пунктов, "
                "а у направлений разные источники")

    p1 = до.get("доли", {}).get(КЛЮЧЕВОЙ_ИСХОД, 0) / 100
    p2 = после.get("доли", {}).get(КЛЮЧЕВОЙ_ИСХОД, 0) / 100
    разница = (p2 - p1) * 100
    шум = 2 * (max(p1 * (1 - p1), 0.01) / мало) ** 0.5 * 100
    общий = f"{КЛЮЧЕВОЙ_ИСХОД} {p1 * 100:.1f} % → {p2 * 100:.1f} % " \
            f"(разница {разница:+.1f} пункта, шум ±{шум:.1f})"
    if abs(разница) <= шум:
        return "эффект не обнаружен", общий
    if мало >= 10 * ПОРОГ_ЗАДАНИЙ and abs(разница) >= 3 * шум:
        return "подтверждённый результат", общий
    return "предварительный сигнал", общий


def _печать(имя: str, с: dict) -> None:
    print(f"=== {имя}: прогонов {с['прогонов']}, заданий {с['заданий']},"
          f" публикаций {с['публикаций']} ({с['период']})")
    if с.get("направления"):
        print(f"      направления: {с['направления']}")
    for исход, сколько in sorted(с["исходы"].items(), key=lambda п: -п[1]):
        print(f"      {исход:20} {сколько:4}  {с['доли'].get(исход, 0):5.1f} %")


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="доли исходов заданий редактора")
    р.add_argument("--dir", default=str(ПРОГОНЫ))
    р.add_argument("--since", default="")
    р.add_argument("--until", default="")
    р.add_argument("--split", default="", help="разделить период этим временем")
    р.add_argument("--json", action="store_true")
    дов = р.parse_args(аргв)

    каталог = pathlib.Path(дов.dir)
    с, по = _время(дов.since) if дов.since else None, _время(дов.until) if дов.until else None
    if дов.since and с is None:
        print(f"НЕ ИЗМЕРЕНО: время --since {дов.since!r} не разобрано")
        return 2
    if дов.until and по is None:
        print(f"НЕ ИЗМЕРЕНО: время --until {дов.until!r} не разобрано")
        return 2
    записи = прогоны(каталог, с, по)
    if not записи:
        print("НЕ ИЗМЕРЕНО: прогонов в периоде нет")
        return 2

    if дов.split:
        рубеж = _время(дов.split)
        if рубеж is None:
            print(f"НЕ ИЗМЕРЕНО: время --split {дов.split!r} не разобрано")
            return 2
        до = [з for з in записи if з[0] < рубеж]
        после = [з for з in записи if з[0] >= рубеж]
        карта = направления()
        свод_до, свод_после = свод(до), свод(после)
        свод_до["направления"] = _состав(до, карта)
        свод_после["направления"] = _состав(после, карта)
        слово, почему = вердикт(свод_до, свод_после)
        итог = {"до": свод_до, "после": свод_после, "рубеж": дов.split,
                "вердикт": слово, "почему": почему}
        if дов.json:
            print(json.dumps(итог, ensure_ascii=False, indent=2))
            return 0
        _печать(f"до {дов.split}", итог["до"])
        _печать(f"после {дов.split}", итог["после"])
        print()
        print(f"ВЕРДИКТ: {слово} — {почему}")
        return 0

    свод_ = свод(записи)
    if дов.json:
        print(json.dumps(свод_, ensure_ascii=False, indent=2))
    else:
        _печать("период", свод_)
    return 0


if __name__ == "__main__":
    sys.exit(main())
