#!/usr/bin/env python3
"""Запустить совместимого издателя на ЖИВОМ пакете `factory`, в изоляции.

Почему отдельным запускающим модулем. Издатель первой строкой делает
`sys.path.insert(0, parents[2])` — то есть сам кладёт свой корень в начало
пути. Если его копия лежит в этой ветви, выигрывает неполный пакет `factory`
этой ветви, и импорт падает на `rating_gateway`. Копия, собранная
`make-k2-publisher.py`, лежит в `var/k2-data/publisher/`, где никакого
`factory` нет: вставка издателя оказывается пустой полкой, и `import factory`
доходит до живого репозитория, который сюда подставляет этот модуль.

Изоляция по умолчанию полная: `--staging-out` в отдельный каталог, свой
`--report-dir`, и БЕЗ `--apply`. Производство в этом режиме не меняется — это
записано в самом издателе («без --apply production не изменяется»), и здесь
проверяется: после прогона сверяются время изменения файлов в
`/srv/lords/.frontend`.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ЖИВОЙ_РЕПО = Path("/srv/site-factory/repo")
ИЗДАТЕЛЬ = КОРЕНЬ / "var" / "k2-data" / "publisher" / "automation" / "host" / "nova-catalog-publish.py"
ХРАНИЛИЩЕ = Path("/srv/lords/.frontend")


def снимок_времён(каталог: Path) -> dict[str, float]:
    if not каталог.is_dir():
        return {}
    итог = {}
    for ф in каталог.glob("*.json"):
        try:
            итог[ф.name] = ф.stat().st_mtime
        except OSError:
            pass
    return итог


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--publisher", default=str(ИЗДАТЕЛЬ))
    р.add_argument("остальное", nargs=argparse.REMAINDER,
                   help="аргументы издателя после --")
    а = р.parse_args()

    издатель = Path(а.publisher)
    if not издатель.is_file():
        print(f"ОТКАЗ: нет собранного издателя {издатель}; сначала "
              f"automation/local/make-k2-publisher.py", file=sys.stderr)
        return 2
    аргументы = [с for с in а.остальное if с != "--"]
    if "--apply" in аргументы:
        print("ОТКАЗ: этот запускающий модуль предназначен для ИЗОЛИРОВАННОГО "
              "прогона; производственная публикация идёт действующим издателем "
              "и отдельным решением", file=sys.stderr)
        return 2

    до = снимок_времён(ХРАНИЛИЩЕ)

    # Живой пакет — первым; вставка самого издателя попадёт впереди, но там
    # пусто, и импорт дойдёт сюда.
    sys.path.insert(0, str(ЖИВОЙ_РЕПО))
    os.chdir(ЖИВОЙ_РЕПО)   # относительные пути издателя — от его репозитория

    spec = importlib.util.spec_from_file_location("nova_catalog_publish", издатель)
    м = importlib.util.module_from_spec(spec)
    sys.modules["nova_catalog_publish"] = м
    spec.loader.exec_module(м)

    import factory  # noqa: E402  — проверяем, ЧЕЙ пакет подхватился

    print(f"издатель: {издатель}")
    print(f"пакет factory: {factory.__file__}")
    print(f"витрин в профиле публикации: {len(м.ВИТРИНЫ)}")
    код = м.main(аргументы)

    после = снимок_времён(ХРАНИЛИЩЕ)
    изменённые = [и for и, t in после.items() if до.get(и) != t]
    # Производство живёт своей жизнью: рядом работают таймеры других витрин, и
    # их файлы меняются во время прогона. Беда — только если изменился файл
    # ТЕХ витрин, которые публиковал этот прогон; остальное называется, но
    # бедой не считается.
    мои = [с.split("=", 1)[1] for с in аргументы if с.startswith("--sites=")]
    если_список = мои[0].split(",") if мои else (
        аргументы[аргументы.index("--sites") + 1].split(",")
        if "--sites" in аргументы else [])
    наши = [и for и in изменённые
            if any(и.startswith(f"{с}-") for с in если_список)]
    чужие = [и for и in изменённые if и not in наши]
    print(f"\nфайлов изменено в {ХРАНИЛИЩЕ}: {len(изменённые)} "
          f"(из них наших витрин: {len(наши)})")
    if чужие:
        print(f"   чужие (соседние таймеры, к прогону не относятся): "
              f"{', '.join(sorted(чужие)[:5])}")
    if наши:
        print(f"ВНИМАНИЕ: изолированный прогон изменил производство: "
              f"{', '.join(sorted(наши))}", file=sys.stderr)
        return 1
    return код


if __name__ == "__main__":
    raise SystemExit(main())
