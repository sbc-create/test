#!/usr/bin/env python3
"""Сборка контекста образа D1 для `yummyani.site`: ТОЛЬКО файлы карты и D4.

Почему не «собрать из исправленного образа целиком». Образы разошлись не одной
правкой: между `rel-9cbfac20fbe8` (работает на `.site`) и `rel-944c932e76ff`
(работает на остальных четырёх) различаются двадцать файлов — главная, полки,
`globals.css`, `truncate.ts`, удалённые `franchise.ts` и `actual-shelf.ts`,
добавленный `trending-shelf.ts`. Выпуск «нового образа» принёс бы на `.site`
две недели чужой работы под видом исправления карты, а заодно СНЁС бы условие
эксперимента B031: именно `seo-core/truncate.ts` и отличает контроль (обрезанный
заголовок) от подопытных.

Поэтому переносится ровно шесть файлов карты плюс правка D4, а `truncate.ts`,
главная и полки остаются те, что работают на `.site` сейчас.

Проверка происхождения, которую требует задание: исходники берутся из САМИХ
образов (`docker create` + `docker cp`), а не из ветки — ревизий работающих
образов в локальных копиях нет вовсе.

    python3 automation/local/assemble-yummy-d1-context.py \\
        --fixed var/yummy-src/fixed-src --site var/yummy-src/site-src \\
        --d4 var/yummy-build/d4-site --out var/yummy-build/d1-site
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

#: Файлы карты, переносимые с исправленного образа. Список закрытый: всё, что
#: в него не входит, на витрине остаётся прежним.
ПОРТ = (
    "lib/seo/sitemap-catalog.ts",
    "lib/seo/sitemap-detail-order.ts",
    "lib/seo/sitemap-inventory.ts",
    "lib/seo/sitemap.ts",
    "app/sitemap.xml/route.ts",
    "app/sitemap/[id]/route.ts",
)

#: Файлы, которые переносить НЕЛЬЗЯ, и причина у каждого. Проверяется, что они
#: не попали в перенос ни по невнимательности, ни после правки списка.
ЗАПРЕЩЕНО = {
    "seo-core/truncate.ts": "условие эксперимента B031 (обрезка заголовка)",
    "app/(portal)/page.tsx": "главная витрины — чужая работа, не предмет D1",
    "app/globals.css": "оформление — чужая работа, не предмет D1",
    "modules/catalog/home-shelves.ts": "полки главной — чужая работа",
    "modules/catalog/trending-shelf.ts": "полка, которой у .site нет вовсе",
}


def хеш(путь: Path) -> str:
    return hashlib.sha256(путь.read_bytes()).hexdigest()[:16]


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--fixed", required=True, help="src исправленного образа")
    р.add_argument("--site", required=True, help="src образа .site")
    р.add_argument("--d4", required=True, help="контекст D4 для .site")
    р.add_argument("--out", required=True)
    а = р.parse_args(аргв)

    исправленный, витрина = Path(а.fixed), Path(а.site)
    выход = Path(а.out)
    (выход / "src").mkdir(parents=True, exist_ok=True)

    отчёт: list[str] = []
    for файл in ПОРТ:
        источник = исправленный / файл
        if not источник.is_file():
            print(f"НЕ СОБРАНО: в исправленном образе нет {файл}")
            return 2
        цель = выход / "src" / файл
        цель.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(источник, цель)
        прежний = витрина / файл
        состояние = ("новый файл" if not прежний.is_file()
                     else ("тот же" if хеш(прежний) == хеш(источник)
                           else f"заменяет {хеш(прежний)} → {хеш(источник)}"))
        отчёт.append(f"{файл}: {состояние}")

    for файл, причина in ЗАПРЕЩЕНО.items():
        if (выход / "src" / файл).exists():
            print(f"НЕ СОБРАНО: в переносе оказался {файл} — {причина}")
            return 2

    # Правка D4 идёт тем же образом, что и на остальных витринах.
    d4 = Path(а.d4) / "src" / "modules" / "catalog"
    for имя in ("walk-budget.ts", "catalog-query.ts"):
        источник = d4 / имя
        if not источник.is_file():
            print(f"НЕ СОБРАНО: нет файла D4 {источник}")
            return 2
        цель = выход / "src" / "modules" / "catalog" / имя
        цель.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(источник, цель)
        отчёт.append(f"modules/catalog/{имя}: правка D4")

    print(f"контекст: {выход}")
    for строка in отчёт:
        print(f"   {строка}")
    print(f"\nфайлов в переносе: {len(ПОРТ)} карты + 2 D4;"
          f" запрещённых к переносу проверено: {len(ЗАПРЕЩЕНО)}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
