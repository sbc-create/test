#!/usr/bin/env python3
"""Сверка витрины с НАСТОЯЩИМ эталоном: геометрия, типографика, палитра.

Сравнивается только одинаково измеренное. Эталон снят тем же способом, что и
витрина (`scripts/capture_reference.cjs` и `scripts/measure_template.cjs`), и
поля совпадают по смыслу, а не по названию.

Чего здесь нет и почему
-----------------------

SSIM и наложение не вычисляются: в окружении нет ни одной библиотеки обработки
изображений (`numpy`, `PIL`, `skimage`, `cv2`, `pixelmatch`, `pngjs`), а
установка потребовала бы сетевого доступа к хранилищу пакетов, которого
владелец не разрешал — разрешены два хоста референса и только чтение. Снимки
эталона при этом сняты и лежат рядом: посчитать их можно будет, не переснимая.

ΔE считается: это арифметика над цветами, измеренными с обеих сторон, и
никакой библиотеки не требует.

    python3 scripts/lords_reference_parity.py \
        artifacts/reference/lordfilm-hit/reference-measurements.json \
        var/measure/r2/measurements-r2.json \
        --out docs/product/LORDS-REFERENCE-PARITY.md
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[1]

#: Какой архетип эталона с каким слотом витрины сопоставляется.
#: Сопоставление явное: «похоже по названию» — не основание.
СООТВЕТСТВИЕ = {
    "home": "home",
    "catalog": "catalog",
    "genre": "genres",
    "search": "search",
    "not_found": "not-found",
}
ВЬЮПОРТЫ = ("360", "390", "768", "1024", "1366", "1440", "1920")

ДОПУСК_ШИРИНЫ = 0.01       # доля
ДОПУСК_ШАПКИ = 2.0         # px
ДОПУСК_КЕГЛЯ = 1.0         # px
ДОПУСК_DELTA_E_МЕДИАНА = 3.0
ДОПУСК_DELTA_E_P95 = 6.0


def разобрать_цвет(значение) -> tuple[float, float, float] | None:
    if not значение:
        return None
    м = re.match(r"rgba?\(([^)]+)\)", str(значение))
    if not м:
        return None
    части = [ч.strip() for ч in м.group(1).replace("/", ",").split(",")]
    try:
        return tuple(float(ч) for ч in части[:3])
    except ValueError:
        return None


def в_lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """sRGB → CIE Lab (D65). Формулы стандартные, библиотек не требуют."""
    def линейно(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (линейно(c) for c in rgb)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    xn, yn, zn = 0.95047, 1.0, 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29
    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(a, b) -> float | None:
    """ΔE*ab — прямое евклидово расстояние в Lab.

    Взята именно CIE76, а не CIEDE2000: формула проще, поведение известно, а
    для сравнения фона и текста разница между ними на решение не влияет. Если
    порог будет решать судьбу приёмки, формулу надо назвать явно — она названа.
    """
    ra, rb = разобрать_цвет(a), разобрать_цвет(b)
    if ra is None or rb is None:
        return None
    la, lb = в_lab(ra), в_lab(rb)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(la, lb)))


def число(значение) -> float | None:
    try:
        return float(str(значение).replace("px", "").strip())
    except (TypeError, ValueError):
        return None


def строки(эталон: dict, наше: dict) -> list[dict]:
    итог: list[dict] = []
    for архетип_эт, слот in СООТВЕТСТВИЕ.items():
        эт_арх = (эталон.get("archetypes") or {}).get(архетип_эт)
        наш_слот = (наше.get("pages") or {}).get(слот)
        for в in ВЬЮПОРТЫ:
            общая = {"архетип": архетип_эт, "слот": слот, "вьюпорт": int(в)}
            э = (эт_арх or {}).get("viewports", {}).get(в)
            н = (наш_слот or {}).get("viewports", {}).get(в)
            if э is None or "error" in э:
                итог.append({**общая, "поле": "эталон", "эталон": "нет снимка",
                             "наше": "—", "вердикт": "BLOCKED_REFERENCE"})
                continue
            if н is None or "error" in н:
                итог.append({**общая, "поле": "витрина", "эталон": "—",
                             "наше": "нет замера", "вердикт": "NO_MEASUREMENT"})
                continue
            # Ширина контейнера
            а, б = число(э.get("contentWidth")), число(н.get("contentWidth"))
            итог.append({**общая, "поле": "ширина контейнера", "эталон": а, "наше": б,
                         "вердикт": "PASS" if а and б and abs(б - а) / а <= ДОПУСК_ШИРИНЫ
                         else "FAIL"})
            # Высота шапки
            а = (э.get("header") or {}).get("height")
            б = (н.get("header") or {}).get("height")
            итог.append({**общая, "поле": "высота шапки", "эталон": а, "наше": б,
                         "вердикт": "PASS" if а is not None and б is not None
                         and abs(б - а) <= ДОПУСК_ШАПКИ else "FAIL"})
            # Положение шапки
            а = (э.get("header") or {}).get("position")
            б = (н.get("header") or {}).get("position")
            итог.append({**общая, "поле": "положение шапки", "эталон": а, "наше": б,
                         "вердикт": "PASS" if а and б and а == б else "FAIL"})
            # Типографика по ролям
            # Роли `a` и `p` сравниваются только по кеглю и начертанию:
            # какой именно элемент попадёт под `querySelector('a')`, у двух
            # разных сайтов решает их собственная разметка.
            for роль in ("body", "h1", "a", "p"):
                эр = (э.get("typography") or {}).get(роль)
                нр = (н.get("typography") or {}).get(роль)
                if not эр:
                    итог.append({**общая, "поле": f"кегль {роль}",
                                 "эталон": "роли нет у эталона", "наше": "—",
                                 "вердикт": "BLOCKED_REFERENCE"})
                    continue
                if not нр:
                    итог.append({**общая, "поле": f"кегль {роль}",
                                 "эталон": эр.get("fontSize"), "наше": "элемента нет",
                                 "вердикт": "NO_ELEMENT"})
                    continue
                а, б = число(эр.get("fontSize")), число(нр.get("fontSize"))
                ок = (а is not None and б is not None and abs(б - а) <= ДОПУСК_КЕГЛЯ
                      and str(эр.get("fontWeight")) == str(нр.get("fontWeight")))
                итог.append({**общая, "поле": f"кегль {роль}",
                             "эталон": f"{эр.get('fontSize')}/{эр.get('fontWeight')}",
                             "наше": f"{нр.get('fontSize')}/{нр.get('fontWeight')}",
                             "вердикт": "PASS" if ок else "FAIL"})
            # Палитра.
            #
            # Фон сравним: это один и тот же наблюдаемый признак у обоих
            # сайтов. Цвет текста по `body` — нет: у эталона он вычисляется
            # как #444 на фоне #111, то есть это унаследованное умолчание, а
            # не цвет читаемого текста; настоящий текст у него белый. Цвет,
            # снятый одним `querySelector` на двух разных сайтах, сравнивает
            # разные элементы, и ΔE между ними ничего не значит.
            d = delta_e((э.get("colors") or {}).get("background"),
                        (н.get("colors") or {}).get("background"))
            итог.append({**общая, "поле": "ΔE фона",
                         "эталон": (э.get("colors") or {}).get("background"),
                         "наше": (н.get("colors") or {}).get("background"),
                         "delta_e": None if d is None else round(d, 2),
                         "вердикт": "NO_MEASUREMENT" if d is None else
                         ("PASS" if d <= ДОПУСК_DELTA_E_МЕДИАНА else "FAIL")})
            итог.append({**общая, "поле": "ΔE текста",
                         "эталон": (э.get("colors") or {}).get("text"),
                         "наше": (н.get("colors") or {}).get("text"),
                         "вердикт": "NOT_COMPARABLE_BY_SELECTOR"})
            # Горизонтальная прокрутка
            итог.append({**общая, "поле": "горизонтальная прокрутка",
                         "эталон": э.get("horizontalOverflow"),
                         "наше": н.get("horizontalOverflow"),
                         "вердикт": "PASS" if not н.get("horizontalOverflow") else "FAIL"})
    return итог


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("эталон")
    р.add_argument("наше")
    р.add_argument("--out", default="docs/product/LORDS-REFERENCE-PARITY.md")
    а = р.parse_args(аргв)

    эталон = json.loads(pathlib.Path(а.эталон).read_text("utf-8"))
    наше = json.loads(pathlib.Path(а.наше).read_text("utf-8"))
    итог = строки(эталон, наше)
    свод: dict[str, int] = {}
    for с in итог:
        свод[с["вердикт"]] = свод.get(с["вердикт"], 0) + 1

    де = [с["delta_e"] for с in итог if с.get("delta_e") is not None]
    де.sort()
    медиана = де[len(де) // 2] if де else None
    p95 = де[int(len(де) * 0.95)] if де else None

    строк = ["# Сверка Lords с настоящим эталоном", "",
             f"Эталон: `{эталон.get('base')}`, снят {эталон.get('captured_at')}.",
             f"Витрина: `{наше.get('base')}`, замер {наше.get('measured_at')}.", "",
             "Сопоставление архетипов задано явно, а не по совпадению названий:",
             ""]
    for э, с in СООТВЕТСТВИЕ.items():
        строк.append(f"- эталон `{э}` ↔ слот витрины `{с}`")
    строк += ["", "| Проверок | " + " | ".join(sorted(свод)) + " |",
              "| ---: | " + " | ".join("---:" for _ in свод) + " |",
              f"| {len(итог)} | " + " | ".join(str(свод[к]) for к in sorted(свод)) + " |",
              "",
              f"ΔE (CIE76) по измеренным цветам: медиана {медиана}, p95 {p95}; "
              f"порог медианы {ДОПУСК_DELTA_E_МЕДИАНА}, p95 {ДОПУСК_DELTA_E_P95}.",
              "",
              "SSIM и наложение не вычислялись: в окружении нет библиотек обработки",
              "изображений, а установка потребовала бы сетевого доступа, которого",
              "владелец не разрешал. Снимки эталона сняты и сохранены — посчитать",
              "можно будет, не переснимая.", "",
              "| Архетип | Вьюпорт | Поле | Эталон | Наше | Вердикт |",
              "| --- | ---: | --- | --- | --- | --- |"]
    for с in итог:
        строк.append(f"| {с['архетип']} | {с['вьюпорт']} | {с['поле']} | "
                     f"{с['эталон']} | {с['наше']} | {с['вердикт']} |")
    (КОРЕНЬ / а.out).write_text("\n".join(строк) + "\n", encoding="utf-8")
    print(json.dumps({"checks": len(итог), **свод,
                      "delta_e_median": медиана, "delta_e_p95": p95,
                      "out": а.out}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
