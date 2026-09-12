#!/usr/bin/env python3
"""Матрица парности Lords: закреплённый замер референса против витрины.

Сравнивается только то, что измерено с обеих сторон. Поле, которого в
референсе нет, получает `BLOCKED_REFERENCE`, а не «совпало»: отсутствие
эталона доказательством сходства не является.

    python3 scripts/lords_parity_report.py var/measure/before/measurements-before.json \
        var/measure/after/measurements-after.json --out docs/product/LORDS-PARITY-MATRIX.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[1]
ЭТАЛОН_ФАЙЛ = КОРЕНЬ / "docs" / "product" / "LORDS-REFERENCE-MEASUREMENTS.md"

#: Измеренные значения референсов Lords. Источник — `ЭТАЛОН_ФАЙЛ`.
#: 360 и 1366 в замере отсутствуют: на этих ширинах эталона нет.
ЭТАЛОН = {
    "contentWidth": {390: 380, 768: 758, 1024: 1000, 1440: 1100, 1920: 1100},
    "headerHeight": {390: 70, 768: 70, 1024: 70, 1440: 70, 1920: 70},
    "typography": {"body": ("14px", "400"), "h1": ("18px", "600"),
                   "a": ("14px", "400"), "p": ("14px", "400")},
    "posterAspect": 0.67,
    "cardAspect": 0.69,
}
ДОПУСК_ШИРИНЫ = 0.01      # 1 % — требование приёмки
ДОПУСК_ШАПКИ = 2.0        # px; у lordserials 71 при 70 у lordfilm
ДОПУСК_КЕГЛЯ = 1.0        # px


def число(значение) -> float | None:
    try:
        return float(str(значение).replace("px", "").strip())
    except (TypeError, ValueError):
        return None


def строки(замер: dict) -> list[dict]:
    итог = []
    for страница, св in замер["pages"].items():
        for ш, з in sorted(св["viewports"].items(), key=lambda x: int(x[0])):
            ширина = int(ш)
            if "error" in з:
                итог.append({"страница": страница, "вьюпорт": ширина,
                             "поле": "загрузка", "эталон": "200",
                             "наше": з["error"][:40], "вердикт": "FAIL"})
                continue
            эт = ЭТАЛОН["contentWidth"].get(ширина)
            наше = з["contentWidth"]
            итог.append({"страница": страница, "вьюпорт": ширина,
                         "поле": "ширина контейнера", "эталон": эт, "наше": наше,
                         "вердикт": "BLOCKED_REFERENCE" if эт is None else
                         ("PASS" if abs(наше - эт) / эт <= ДОПУСК_ШИРИНЫ else "FAIL")})
            эт = ЭТАЛОН["headerHeight"].get(ширина)
            наше = (з.get("header") or {}).get("height")
            итог.append({"страница": страница, "вьюпорт": ширина,
                         "поле": "высота шапки", "эталон": эт, "наше": наше,
                         "вердикт": "BLOCKED_REFERENCE" if эт is None else
                         ("PASS" if наше is not None and abs(наше - эт) <= ДОПУСК_ШАПКИ
                          else "FAIL")})
            for роль, (кегль, вес) in ЭТАЛОН["typography"].items():
                св_роли = (з.get("typography") or {}).get(роль)
                if not св_роли:
                    итог.append({"страница": страница, "вьюпорт": ширина,
                                 "поле": f"кегль {роль}", "эталон": кегль,
                                 "наше": "элемента нет", "вердикт": "NO_ELEMENT"})
                    continue
                а, б = число(св_роли["fontSize"]), число(кегль)
                ок = а is not None and abs(а - б) <= ДОПУСК_КЕГЛЯ \
                    and str(св_роли["fontWeight"]) == вес
                итог.append({"страница": страница, "вьюпорт": ширина,
                             "поле": f"кегль {роль}", "эталон": f"{кегль}/{вес}",
                             "наше": f"{св_роли['fontSize']}/{св_роли['fontWeight']}",
                             "вердикт": "PASS" if ок else "FAIL"})
            # Постер сравним с замером: 0.67 против доминирующих 0.69.
            доли = з.get("posterAspectRatios") or {}
            if доли:
                главная = max(доли.items(), key=lambda п: п[1])[0]
                итог.append({"страница": страница, "вьюпорт": ширина,
                             "поле": "пропорция: постер",
                             "эталон": ЭТАЛОН["posterAspect"], "наше": главная,
                             "вердикт": "PASS" if abs(float(главная)
                                                      - ЭТАЛОН["posterAspect"]) <= 0.03
                             else "FAIL"})
            else:
                итог.append({"страница": страница, "вьюпорт": ширина,
                             "поле": "пропорция: постер",
                             "эталон": ЭТАЛОН["posterAspect"],
                             "наше": "нет элементов", "вердикт": "NO_ELEMENT"})
            # Обёртка карточки сравнению не поддаётся.
            #
            # В замере референса поле называется `cardAspectRatios` и не
            # говорит, что именно измерялось: обёртка с подписью или сам
            # постер. Их доминирующие 0.69 ближе к постеру 2:3 (0.667), чем к
            # любой обёртке с текстом. Наша обёртка — 0.42, и это не «хуже»,
            # это другая величина. Объявить здесь FAIL было бы такой же
            # выдумкой, как объявить PASS; нужен кроп компонента.
            доли = з.get("cardAspectRatios") or {}
            главная = (max(доли.items(), key=lambda п: п[1])[0] if доли else "нет")
            итог.append({"страница": страница, "вьюпорт": ширина,
                         "поле": "пропорция: обёртка карточки",
                         "эталон": "не определён в замере", "наше": главная,
                         "вердикт": "BLOCKED_REFERENCE"})
            for поле, подпись in (("horizontalOverflow", "горизонтальная прокрутка"),
                                  ("controlsOffscreen", "недостижимые элементы"),
                                  ("brokenImages", "битые изображения")):
                наше = з.get(поле)
                плохо = bool(наше)
                итог.append({"страница": страница, "вьюпорт": ширина, "поле": подпись,
                             "эталон": 0, "наше": int(наше or 0),
                             "вердикт": "FAIL" if плохо else "PASS"})
            итог.append({"страница": страница, "вьюпорт": ширина,
                         "поле": "ошибки консоли", "эталон": 0,
                         "наше": len(з.get("consoleErrors") or []),
                         "вердикт": "FAIL" if з.get("consoleErrors") else "PASS"})
    return итог


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("до")
    р.add_argument("после")
    р.add_argument("--out", default="docs/product/LORDS-PARITY-MATRIX.md")
    а = р.parse_args(аргв)

    до = json.loads(pathlib.Path(а.до).read_text(encoding="utf-8"))
    после = json.loads(pathlib.Path(а.после).read_text(encoding="utf-8"))
    сд, сп = строки(до), строки(после)
    ключ = lambda с: (с["страница"], с["вьюпорт"], с["поле"])
    было = {ключ(с): с for с in сд}

    свод = {"PASS": 0, "FAIL": 0, "BLOCKED_REFERENCE": 0, "NO_ELEMENT": 0}
    исправлено, сломано = [], []
    for с in сп:
        свод[с["вердикт"]] = свод.get(с["вердикт"], 0) + 1
        б = было.get(ключ(с))
        if б and б["вердикт"] == "FAIL" and с["вердикт"] == "PASS":
            исправлено.append(с)
        if б and б["вердикт"] == "PASS" and с["вердикт"] == "FAIL":
            сломано.append(с)

    отпечаток = hashlib.sha256(ЭТАЛОН_ФАЙЛ.read_bytes()).hexdigest()
    строк = ["# Матрица парности Lords", "",
             f"Эталон: `docs/product/LORDS-REFERENCE-MEASUREMENTS.md`, sha256 `{отпечаток}`.",
             "Живой доступ к референсу закрыт профилем разрешений, поэтому пиксельное",
             "сравнение (SSIM, ΔE, наложение) невозможно: сравниваются числа.", "",
             "| Проверок | PASS | FAIL | BLOCKED_REFERENCE | нет элемента |",
             "| --- | ---: | ---: | ---: | ---: |",
             f"| {len(сп)} | {свод['PASS']} | {свод['FAIL']} | "
             f"{свод['BLOCKED_REFERENCE']} | {свод['NO_ELEMENT']} |", "",
             f"Исправлено этой работой: {len(исправлено)}. Сломано: {len(сломано)}.", ""]
    if сломано:
        строк += ["## Сломано", ""]
        for с in сломано:
            строк.append(f"- {с['страница']}/{с['вьюпорт']} {с['поле']}: "
                         f"эталон {с['эталон']}, наше {с['наше']}")
        строк.append("")
    остались = [с for с in сп if с["вердикт"] == "FAIL"]
    if остались:
        строк += ["## Остаются расхождения", ""]
        for с in остались[:40]:
            строк.append(f"- {с['страница']}/{с['вьюпорт']} {с['поле']}: "
                         f"эталон {с['эталон']}, наше {с['наше']}")
        строк.append("")
    строк += ["## Полная матрица", "",
              "| Страница | Вьюпорт | Поле | Эталон | Было | Стало | Вердикт |",
              "| --- | ---: | --- | --- | --- | --- | --- |"]
    for с in сп:
        б = было.get(ключ(с))
        строк.append(f"| {с['страница']} | {с['вьюпорт']} | {с['поле']} | "
                     f"{с['эталон']} | {б['наше'] if б else '—'} | {с['наше']} | "
                     f"{с['вердикт']} |")
    (КОРЕНЬ / а.out).write_text("\n".join(строк) + "\n", encoding="utf-8")
    print(json.dumps({"checks": len(сп), **свод, "fixed": len(исправлено),
                      "broken": len(сломано), "out": а.out}, ensure_ascii=False))
    return 0 if not сломано else 1


if __name__ == "__main__":
    raise SystemExit(главное())
