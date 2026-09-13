#!/usr/bin/env python3
"""Инвентарь reference pack: что есть, чего нет и на что оно годится.

Пригодность определяется по наличию данных, а не по желанию: для SSIM и ΔE
нужны изображения, для сравнения геометрии достаточно чисел. Артефакт без
изображения не становится пригодным к пиксельному сравнению оттого, что
сравнение требуется.

    python3 scripts/lords_reference_inventory.py --out docs/product/LORDS-REFERENCE-INVENTORY.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[1]

#: Одиннадцать обязательных архетипов задания. Знаменатель матрицы охвата.
АРХЕТИПЫ = (
    ("home", "главная"),
    ("movie", "страница фильма"),
    ("series", "страница сериала"),
    ("season", "сезон"),
    ("episode_player", "эпизод / страница с player shell"),
    ("genre_catalog", "жанровый каталог"),
    ("country_catalog", "каталог по стране"),
    ("collection", "подборка"),
    ("search_results", "результаты поиска"),
    ("empty_state", "пустая или отсутствующая выдача"),
    ("mobile_nav", "мобильная навигация"),
)
ВЬЮПОРТЫ = (360, 390, 768, 1024, 1366, 1440, 1920)

#: Что известно о существующих артефактах. Источник — сами файлы; значения,
#: которых в файле нет, помечаются как неизмеренные, а не додумываются.
ИЗВЕСТНЫЕ = (
    {"reference_id": "lordfilm-hit-home",
     "url": "https://lordfilm-hit.org/", "page_type": "home",
     "captured_at": "2026-08-27T15:06:30.913Z",
     "viewports": [390, 768, 1024, 1440, 1920],
     "archetypes": ["home"]},
    {"reference_id": "lordfilm-title",
     "url": "https://lordfilm-hit.org/3629-bunker-2023.html", "page_type": "title",
     "captured_at": "2026-08-27T15:06:47.910Z",
     "viewports": [390, 768, 1024, 1440, 1920],
     "archetypes": ["movie", "episode_player"]},
    {"reference_id": "lordserials-home",
     "url": "https://lordserials.fan/", "page_type": "home",
     "captured_at": "2026-08-27T15:07:03.610Z",
     "viewports": [390, 768, 1024, 1440, 1920],
     "archetypes": ["home"]},
)
ФАЙЛ_ЗАМЕРОВ = КОРЕНЬ / "docs" / "product" / "LORDS-REFERENCE-MEASUREMENTS.md"
ФАЙЛ_ТОКЕНОВ = КОРЕНЬ / "docs" / "product" / "REFERENCE-DESIGN-TOKENS.md"
ФАЙЛ_СРАВНЕНИЯ = КОРЕНЬ / "docs" / "product" / "CURRENT-VS-REFERENCE.md"
РАЗРЕШЁННЫЕ_ИСТОЧНИКИ = КОРЕНЬ / "inventory" / "reference-sources.yaml"


def отпечаток(п: pathlib.Path) -> str:
    return hashlib.sha256(п.read_bytes()).hexdigest() if п.is_file() else "ФАЙЛА НЕТ"


#: Каталоги, где мог бы лежать снимок РЕФЕРЕНСА. Всё остальное — наши
#: собственные снимки, и путать их с эталоном нельзя ни при каких условиях:
#: кандидат не может служить эталоном самому себе.
#:
#: Первая версия этой функции обходила `artifacts/` целиком и насчитала 159
#: «референсных» изображений. Все 159 оказались нашими: витрины lords-02,
#: animedia-portal, zona-cinema и basis-video. Отчёт с таким числом объявил бы
#: эталон существующим.
КАТАЛОГИ_РЕФЕРЕНСА = ("docs/reference-packs", "docs/reference",
                      "artifacts/reference", "artifacts/lords-reference")
#: Признаки наших собственных снимков в именах файлов.
НАШИ = ("lords-01", "lords-02", "lords-03", "zona-cinema", "animedia-portal",
        "basis-video", "yummy", "candidate", "before", "after", "series1",
        "series2")


def изображения() -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """(снимки референса, наши снимки). Второе — не эталон и им не станет."""
    референс, наши = [], []
    for отн in КАТАЛОГИ_РЕФЕРЕНСА:
        к = КОРЕНЬ / отн
        if not к.is_dir():
            continue
        for п in к.rglob("*"):
            if п.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and п.is_file():
                (наши if any(и in п.name.lower() for и in НАШИ) else референс).append(п)
    for к in (КОРЕНЬ / "artifacts",):
        if not к.is_dir():
            continue
        for п in к.rglob("*"):
            if п.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and п.is_file():
                наши.append(п)
    return референс, наши


def разрешён_ли_хост(хост: str) -> bool:
    try:
        т = РАЗРЕШЁННЫЕ_ИСТОЧНИКИ.read_text("utf-8")
    except OSError:
        return False
    return хост in т


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", default="docs/product/LORDS-REFERENCE-INVENTORY.md")
    а = р.parse_args(аргв)

    снимки, наши_снимки = изображения()
    домены = sorted({re.sub(r"^https?://([^/]+).*", r"\1", з["url"])
                     for з in ИЗВЕСТНЫЕ})
    разрешены = {д: разрешён_ли_хост(д) for д in домены}

    # Охват архетипов: что покрыто существующими артефактами.
    покрытие: dict[tuple[str, int], str] = {}
    покрыто_числами = {(а_, в) for з in ИЗВЕСТНЫЕ for а_ in з["archetypes"]
                       for в in з["viewports"]}
    for код, _ in АРХЕТИПЫ:
        for в in ВЬЮПОРТЫ:
            if (код, в) in покрыто_числами:
                # Числа есть, изображения нет: для геометрии годно, для пикселей нет.
                покрытие[(код, в)] = "EXISTING_VALID_GEOMETRY_ONLY"
            elif в in (360, 1366):
                покрытие[(код, в)] = "MISSING_REFERENCE"
            else:
                покрытие[(код, в)] = "MISSING_REFERENCE"
    # Подборки выключены владельцем в манифесте — архетип к Lords не применим.
    for в in ВЬЮПОРТЫ:
        покрытие[("collection", в)] = "REFERENCE_ROUTE_ABSENT"

    свод: dict[str, int] = {}
    for з in покрытие.values():
        свод[з] = свод.get(з, 0) + 1

    строки = ["# Инвентарь reference pack Lords", "",
              "## Доступ", ""]
    for д, ок in разрешены.items():
        строки.append(f"- `{д}` — в `inventory/reference-sources.yaml` "
                      f"{'ЕСТЬ' if ок else 'ОТСУТСТВУЕТ'}")
    строки += ["",
               "Разрешённый список источников содержит только `amd.online` и",
               "`w140.zona.plus`. Хостов Lords в нём нет ни в одном рабочем дереве.",
               "Список не расширяется по инициативе исполнителя — это записано в",
               "самом файле, — поэтому живой захват невозможен не технически, а по",
               "правилу. Снять блокировку может только владелец, добавив запись.", "",
               "## Существующие артефакты", "",
               "| reference_id | URL | тип | снят | вьюпорты | снимки | DOM/geometry | sha256 |",
               "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    от = отпечаток(ФАЙЛ_ЗАМЕРОВ)
    for з in ИЗВЕСТНЫЕ:
        строки.append(
            f"| {з['reference_id']} | {з['url']} | {з['page_type']} | "
            f"{з['captured_at']} | {', '.join(str(в) for в in з['viewports'])} | "
            f"нет | числа есть | `{от[:16]}…` |")
    строки += ["", f"Файл замеров: `{ФАЙЛ_ЗАМЕРОВ.relative_to(КОРЕНЬ)}`, sha256 `{от}`.",
               f"Токены: `{ФАЙЛ_ТОКЕНОВ.relative_to(КОРЕНЬ)}`, sha256 `{отпечаток(ФАЙЛ_ТОКЕНОВ)}`.",
               f"Сравнение: `{ФАЙЛ_СРАВНЕНИЯ.relative_to(КОРЕНЬ)}`, sha256 `{отпечаток(ФАЙЛ_СРАВНЕНИЯ)}`.",
               "",
               f"Изображений референса в репозитории: **{len(снимки)}**.",
               f"Наших собственных снимков: {len(наши_снимки)} — это не эталон и",
               "эталоном не становится: кандидат не может служить референсом сам",
               "себе. Первая версия инвентаризатора насчитала их как референсные,",
               "и отчёт объявил бы эталон существующим.", ""]
    if снимки:
        for п in снимки[:10]:
            строки.append(f"- `{п.relative_to(КОРЕНЬ)}` sha256 `{отпечаток(п)[:16]}…`")
    else:
        строки += ["Ни одного. Полностраничных снимков, кропов компонентов и",
                   "цветовых проб нет, поэтому SSIM, ΔE и наложение недоступны —",
                   "не по строгости порога, а потому что сравнивать не с чем.", ""]

    строки += ["## Матрица охвата: 11 архетипов × 7 вьюпортов", "",
               "| Архетип | " + " | ".join(str(в) for в in ВЬЮПОРТЫ) + " |",
               "| --- | " + " | ".join("---" for _ in ВЬЮПОРТЫ) + " |"]
    КРАТКО = {"EXISTING_VALID_GEOMETRY_ONLY": "числа",
              "MISSING_REFERENCE": "нет",
              "REFERENCE_ROUTE_ABSENT": "н/п"}
    for код, подпись in АРХЕТИПЫ:
        ячейки = [КРАТКО[покрытие[(код, в)]] for в in ВЬЮПОРТЫ]
        строки.append(f"| {подпись} | " + " | ".join(ячейки) + " |")
    строки += ["",
               "`числа` — EXISTING_VALID, пригодно только для сравнения геометрии и",
               "типографики. `нет` — MISSING_REFERENCE. `н/п` — REFERENCE_ROUTE_ABSENT:",
               "подборки выключены владельцем в манифесте (`тип выключен в manifest",
               "владельцем`), у витрины такого маршрута нет и сравнивать нечего.", "",
               "| Статус | Клеток |", "| --- | ---: |"]
    for к, n in sorted(свод.items()):
        строки.append(f"| {к} | {n} |")
    строки += ["", f"Всего клеток: {len(покрытие)}.",
               "Пригодных к пиксельному сравнению: **0** — изображений нет ни одного.", ""]

    (КОРЕНЬ / а.out).write_text("\n".join(строки) + "\n", encoding="utf-8")
    print(json.dumps({"archetypes": len(АРХЕТИПЫ), "viewports": len(ВЬЮПОРТЫ),
                      "cells": len(покрытие), "by_status": свод,
                      "reference_images": len(снимки),
                      "own_screenshots": len(наши_снимки),
                      "hosts_allowlisted": разрешены, "out": а.out},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
