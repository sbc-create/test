#!/usr/bin/env python3
"""Сверка доставки каталогов: поколение и содержимое, а не время файла.

    python3 automation/local/publish-delivery-audit.py

Зачем. Прерванный прогон публикации оставляет вопрос «кому доставили»: 9 и 10
октября шаг публикации убивал OOM killer, и ответ по `mtime` был бы неверным —
файл мог быть переписан прежним поколением. Поэтому сверяется ПОКОЛЕНИЕ
(`revision`, `builtAt`, `count` внутри файла) и совпадение каталога с
подробностями, а время файла печатается рядом как справка.

Что печатается:

* поколение production-цели каждой витрины (`/srv/lords/.frontend`);
* поколение в каталоге данных каждой ячейки по реестру;
* отставшие ячейки — те, чьё поколение не совпало с production;
* частичные файлы (`*.tmp`, `*.new`) в обоих местах;
* сохранность редакционных правок ячейки (`editorial-overrides.json`) и
  пользовательских данных (`site-data`, `*-community.json`): файл есть, читается
  и не пуст.

Инструмент ТОЛЬКО ЧИТАЕТ. Выход: 0 — все ячейки на поколении production и
частичных файлов нет; 1 — есть отставшие или частичные; 2 — читать нечем.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ФРОНТ = pathlib.Path("/srv/lords/.frontend")
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"


def _поколение(путь: pathlib.Path) -> dict:
    """Поколение файла каталога: то, что внутри, а не время на диске."""
    if not путь.is_file():
        return {"есть": False}
    try:
        данные = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        return {"есть": True, "ошибка": f"{type(ош).__name__}: {ош}"}
    return {"есть": True,
            "revision": str(данные.get("revision") or "")[:12],
            "builtAt": str(данные.get("builtAt") or "")[:19],
            "count": данные.get("count"),
            "mtime": time.strftime("%d.%m %H:%M", time.gmtime(путь.stat().st_mtime))}


def _частичные(каталог: pathlib.Path) -> list[str]:
    if not каталог.is_dir():
        return []
    return sorted([ф.name for ф in каталог.glob("*.tmp")]
                  + [ф.name for ф in каталог.glob("*.new")])


def _данные_посетителей(каталог: pathlib.Path) -> list[str]:
    """Что в этом каталоге принадлежит посетителям и редактору."""
    итог = []
    for образец in ("editorial-overrides.json", "*-community.json", "site-data"):
        for п in sorted(каталог.glob(образец)):
            if п.is_dir():
                сколько = sum(1 for _ in п.rglob("*"))
                итог.append(f"{п.name}/ ({сколько} файлов)")
                continue
            try:
                размер = п.stat().st_size
                json.loads(п.read_text(encoding="utf-8"))
                итог.append(f"{п.name} ({размер} Б, читается)")
            except PermissionError:
                # Хранилище сообщества принадлежит учётной записи сайта и
                # закрыто правами 0600. Это порядок, а не повреждение:
                # проверка его не читает и не должна.
                итог.append(f"{п.name} (закрыт правами, на месте)")
            except (OSError, ValueError) as ош:
                итог.append(f"{п.name} — НЕ ЧИТАЕТСЯ: {type(ош).__name__}")
    return итог


def главное() -> int:
    if not РЕЕСТР.is_file():
        print(f"нет реестра ячеек {РЕЕСТР}", file=sys.stderr)
        return 2
    реестр = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    отставшие, частичные = [], []

    print("=== production-цели")
    поколения_prod = {}
    for ф in sorted(ФРОНТ.glob("*-catalog.json")):
        site_id = ф.name[: -len("-catalog.json")]
        п = _поколение(ф)
        поколения_prod[site_id] = п
        print(f"   {site_id:12} count={str(п.get('count')):>6} "
              f"revision={п.get('revision')} builtAt={п.get('builtAt')} "
              f"файл {п.get('mtime')}")
    мусор = _частичные(ФРОНТ)
    if мусор:
        частичные.append((str(ФРОНТ), мусор))

    print("\n=== каталоги данных ячеек")
    for ячейка in реестр.get("cells") or []:
        site_id = ячейка["site_id"]
        рантайм = ячейка.get("runtime") or {}
        каталог_данных = рантайм.get("data_dir")
        if not каталог_данных:
            continue
        # Доставку ЭТИМ конвейером получает не всякая ячейка: условие то же,
        # что у издателя (`managed_by == cell`, `data_owner == pipeline`).
        # Витрины Yummy наполняет другой механизм, и сравнивать их поколение с
        # production этого конвейера значило бы называть отставанием чужую
        # работу.
        наш_конвейер = (рантайм.get("managed_by") == "cell"
                        and рантайм.get("data_owner") == "pipeline")
        каталог = pathlib.Path(каталог_данных)
        if not каталог.is_dir():
            print(f"   {site_id:12} каталога данных нет: {каталог}")
            continue
        п = _поколение(каталог / f"{site_id}-catalog.json")
        пp = поколения_prod.get(site_id) or {}
        # Признак «витрина этого конвейера» берётся из содержимого, а не из
        # списка в коде: издатель каталога Lords/Zona ставит в файл `revision`,
        # а конвейер Yummy — нет. Так профиль не приходится держать вторым
        # перечнем, который разойдётся с первым.
        наш_конвейер = наш_конвейер and bool(пp.get("revision"))
        if not наш_конвейер:
            метка = "доставка не этим конвейером"
        elif not пp:
            метка = "цели в production нет (заимствованный снимок)"
        else:
            совпало = (п.get("revision") == пp.get("revision")
                       and п.get("builtAt") == пp.get("builtAt")
                       and п.get("count") == пp.get("count"))
            метка = "ок" if совпало else "ОТСТАЁТ"
            if not совпало:
                отставшие.append(site_id)
        print(f"   {site_id:12} count={str(п.get('count')):>6} "
              f"revision={п.get('revision')} builtAt={п.get('builtAt')} "
              f"файл {п.get('mtime')}  {метка}")
        мусор = _частичные(каталог)
        if мусор:
            частичные.append((str(каталог), мусор))
            print(f"                ЧАСТИЧНЫЕ ФАЙЛЫ: {мусор}")
        своё = _данные_посетителей(каталог)
        if своё:
            print(f"                данные посетителей и редактора: {'; '.join(своё)}")

    print(f"\nотстающих ячеек: {len(отставшие)} {отставшие}")
    print(f"мест с частичными файлами: {len(частичные)}")
    for место, файлы in частичные:
        print(f"   {место}: {файлы}")
    return 1 if (отставшие or частичные) else 0


if __name__ == "__main__":
    raise SystemExit(главное())
