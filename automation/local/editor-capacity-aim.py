#!/usr/bin/env python3
"""Куда нацелена ёмкость редактора: по наличию источника, со знаменателями.

Повод измеренный (25.10). Ёмкость редактора уходит на работы, у которых у
источника НЕТ описания: из 176 отказов аниме-семейств за 7 суток у 170 (97 %)
описания в снимке нет вовсе. Для посетителя это верная цель — такие страницы
показывают только шаблон фактов. Но источника там нет, поэтому 86 % заходов
кончаются отказом, а 5 067 работ с готовой завязкой не берутся и остаются
дословными дублями сестёр.

Инструмент НЕ судит, какая цель правильная. Он печатает три числа рядом, чтобы
выбор цели перестал быть молчаливым:

* каталог: сколько работ с описанием, сколько без;
* размещено: сколько из них уже несут редакционный текст;
* взятые задания: на какие из них ушли заходы редактора и чем кончились.

Без третьего числа первые два — просто инвентарь. Без первых двух третье не
говорит, был ли выбор.

    python3 automation/local/editor-capacity-aim.py --family animedia --days 7
"""
from __future__ import annotations

import argparse
import datetime as dt
import gc
import importlib.util
import json
import pathlib
import sys

НАЛОЖЕНИЯ = pathlib.Path("/srv/sites")
СНИМКИ = pathlib.Path("/srv/lords/.frontend")
АРЕНДЫ = pathlib.Path("/var/lib/seo-content-operator/editorial_leases.json")
#: Семейство → (витрины, файл снимка каталога).
СЕМЕЙСТВА = {
    "animedia": (("animedia.icu", "animedia.space"), "animedia-01-details.json"),
    "animego": (("animeg0.site", "an1meg0.site", "an1mego.site"),
                "animedia-01-details.json"),
}
ПОРОГ_ЗАВЯЗКИ = 200


def слаги_наложения(домен: str) -> set[str]:
    из: set[str] = set()
    for путь in sorted(НАЛОЖЕНИЯ.glob(
            f"*/runtime/overlays/{домен}/title-overlays.json")):
        try:
            д = json.loads(pathlib.Path(путь).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        зп = д.get("items")
        зп = list(зп.values()) if isinstance(зп, dict) else (зп or [])
        из |= {з.get("slug") for з in зп
               if isinstance(з, dict) and з.get("slug")
               and (з.get("body") or "").strip()}
    return из


def описания_каталога(файл: pathlib.Path) -> dict[str, int]:
    """Слаг → длина описания у источника. Снимок читается один раз."""
    д = json.loads(файл.read_text(encoding="utf-8"))
    подробности = д.get("details") or {}
    из = {с: len((з.get("description") or "").strip())
          for с, з in подробности.items() if isinstance(з, dict)}
    del д, подробности
    gc.collect()
    return из


def исходы_заданий(витрины: tuple[str, ...], дней: float) -> list[tuple[str, str, str]]:
    """(витрина, слаг, исход) по шагам журнала аренд за окно."""
    спец = importlib.util.spec_from_file_location(
        "erc", pathlib.Path(__file__).resolve().parent / "editorial-refusal-causes.py")
    М = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(М)
    записи = М.аренды(АРЕНДЫ)
    с = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=дней)
    из = []
    for з, ш in М.шаги(записи, с, ()):
        сайт = з.get("site") or ""
        if сайт in витрины:
            из.append((сайт, з.get("work_id") or "", str(ш.get("outcome") or "")))
    return из


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--family", choices=sorted(СЕМЕЙСТВА), required=True)
    р.add_argument("--days", type=float, default=7.0)
    р.add_argument("--snapshots", type=pathlib.Path, default=СНИМКИ)
    р.add_argument("--json", type=pathlib.Path)
    а = р.parse_args(аргв)
    витрины, имя_снимка = СЕМЕЙСТВА[а.family]
    файл = а.snapshots / имя_снимка
    if not файл.is_file():
        print(f"НЕ ИЗМЕРЕНО: снимка каталога нет по пути {файл}", file=sys.stderr)
        return 2
    длины = описания_каталога(файл)
    всего = len(длины)
    с_завязкой = {с for с, д_ in длины.items() if д_ >= ПОРОГ_ЗАВЯЗКИ}
    пустые = {с for с, д_ in длины.items() if д_ == 0}
    короткие = всего - len(с_завязкой) - len(пустые)
    print(f"каталог ({имя_снимка}): работ {всего}")
    print(f"   описание ≥{ПОРОГ_ЗАВЯЗКИ} знаков: {len(с_завязкой)}"
          f" ({len(с_завязкой)/всего:.0%})")
    print(f"   описание короче порога:  {короткие}")
    print(f"   описания нет вовсе:      {len(пустые)} ({len(пустые)/всего:.0%})")
    print()
    print(f"{'витрина':22} {'размещено':>10} {'с завязкой без текста':>23}"
          f" {'пустых без текста':>19}")
    сводка = {}
    for д_ in витрины:
        есть = слаги_наложения(д_)
        сводка[д_] = {"размещено": len(есть),
                      "с_завязкой_без_текста": len(с_завязкой - есть),
                      "пустых_без_текста": len(пустые - есть)}
        print(f"{д_:22} {len(есть):10} {len(с_завязкой - есть):23}"
              f" {len(пустые - есть):19}")

    исходы = исходы_заданий(витрины, а.days)
    print()
    if not исходы:
        print(f"за {а.days:g} сут заходов редактора по этим витринам нет —"
              " цель ёмкости НЕ ИЗМЕРЕНА")
        return 3
    по_источнику = {"с завязкой": 0, "короткое описание": 0, "пусто": 0,
                    "нет в снимке": 0}
    отказы_пустых = 0
    for _, слаг, исход in исходы:
        д_ = длины.get(слаг)
        если = ("нет в снимке" if д_ is None else
                "с завязкой" if д_ >= ПОРОГ_ЗАВЯЗКИ else
                "пусто" if д_ == 0 else "короткое описание")
        по_источнику[если] += 1
        if если == "пусто" and исход.startswith("SOURCES_MISSING"):
            отказы_пустых += 1
    всего_заходов = len(исходы)
    print(f"заходов редактора за {а.days:g} сут: {всего_заходов}")
    for имя, n in по_источнику.items():
        print(f"   по работам «{имя}»: {n} ({n/всего_заходов:.0%})")
    print(f"   из них отказов «нет источника» по пустым работам: {отказы_пустых}"
          f" ({отказы_пустых/всего_заходов:.0%} всех заходов)")
    if а.json:
        а.json.parent.mkdir(parents=True, exist_ok=True)
        а.json.write_text(json.dumps(
            {"семейство": а.family, "окно_сут": а.days, "каталог_работ": всего,
             "с_завязкой": len(с_завязкой), "пустых": len(пустые),
             "по_витринам": сводка, "заходов": всего_заходов,
             "заходы_по_источнику": по_источнику,
             "отказы_по_пустым": отказы_пустых},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"подробности: {а.json}")
    print()
    доля_пустых_в_заходах = по_источнику["пусто"] / всего_заходов
    доля_пустых_в_каталоге = len(пустые) / всего
    print(f"ВЫВОД: ёмкость нацелена на работы без источника —"
          f" {доля_пустых_в_заходах:.0%} заходов при их доле в каталоге"
          f" {доля_пустых_в_каталоге:.0%}."
          " Это не ошибка отбора: такие страницы показывают только шаблон"
          " фактов. Но источника там нет, поэтому заходы кончаются отказом, а"
          f" работы с готовой завязкой (у {витрины[0]} их"
          f" {сводка[витрины[0]]['с_завязкой_без_текста']} без текста) не"
          " берутся. Выбор цели — решение владельца, здесь он только измерен")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
