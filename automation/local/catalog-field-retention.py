#!/usr/bin/env python3
"""Теряет ли обновление каталога постеры и русские названия.

    python3 automation/local/catalog-field-retention.py <site_id> [<before-образ>]

Зачем. Доставка каталога заменяет файл витрины целиком. Если поставщик в этот
раз не отдал постер или русское название для записи, у которой они БЫЛИ,
страница теряет их без единой ошибки: витрина честно показывает то, что ей
привезли. Такую потерю видно только сравнением поколений, и сравнивать надо
содержимое, а не количество записей.

Сравниваются ПРЕЖНИЙ образ (его оставляет сам издатель перед записью) и
действующий каталог. Инструмент только читает.

Что считается потерей:

* **постер** — был непустой `poster`, стал пустой или исчез;
* **русское название** — в прежнем `title` были буквы кириллицы, в новом их
  не осталось (запись «перешла» на латиницу или на слаг);
* **исчезновение записи** — была в прежнем поколении, нет в новом.

Выход: 0 — потерь нет; 1 — потери есть; 2 — сравнивать нечем.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ФРОНТ = pathlib.Path("/srv/lords/.frontend")
КОПИИ = pathlib.Path("/srv/site-factory/repo/var/lords/publish-backups")
КИРИЛЛИЦА = re.compile(r"[А-Яа-яЁё]")


def _последний_образ(site_id: str) -> pathlib.Path | None:
    образы = sorted(КОПИИ.glob(f"{site_id}-catalog.json.before.*"),
                    key=lambda п: п.stat().st_mtime)
    return образы[-1] if образы else None


def _записи(путь: pathlib.Path) -> dict[str, dict]:
    данные = json.loads(путь.read_text(encoding="utf-8"))
    итог = {}
    for з in данные.get("items") or []:
        ключ = str(з.get("id") or з.get("slug") or "")
        if ключ:
            итог[ключ] = з
    return итог, str(данные.get("revision") or "")[:12], str(данные.get("builtAt") or "")


def главное() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    site_id = sys.argv[1]
    новый_путь = ФРОНТ / f"{site_id}-catalog.json"
    прежний_путь = (pathlib.Path(sys.argv[2]) if len(sys.argv) > 2
                    else _последний_образ(site_id))
    if not новый_путь.is_file():
        print(f"нет действующего каталога {новый_путь}", file=sys.stderr)
        return 2
    if not прежний_путь or not prejniy_exists(прежний_путь):
        print(f"нет прежнего образа для {site_id} в {КОПИИ}", file=sys.stderr)
        return 2

    прежние, рев_п, дата_п = _записи(прежний_путь)
    новые, рев_н, дата_н = _записи(новый_путь)
    print(f"прежнее поколение {рев_п} ({дата_п}): записей {len(прежние)}")
    print(f"новое поколение   {рев_н} ({дата_н}): записей {len(новые)}")

    исчезли = [к for к in прежние if к not in новые]
    постеры, названия, латиница = [], [], []
    for ключ, было in прежние.items():
        стало = новые.get(ключ)
        if стало is None:
            continue
        if str(было.get("poster") or "").strip() and not str(стало.get("poster") or "").strip():
            постеры.append((ключ, было.get("title")))
        т_было, т_стало = str(было.get("title") or ""), str(стало.get("title") or "")
        if КИРИЛЛИЦА.search(т_было) and not КИРИЛЛИЦА.search(т_стало):
            названия.append((ключ, т_было, т_стало))
        elif т_было != т_стало:
            латиница.append((ключ, т_было, т_стало))

    print(f"\nисчезло записей:           {len(исчезли)}")
    print(f"потеряно постеров:         {len(постеры)}")
    print(f"потеряно русских названий: {len(названия)}")
    print(f"названия изменились иначе:  {len(латиница)}")
    for ключ, назв in постеры[:5]:
        print(f"   постер пропал: {ключ} {назв!r}")
    for ключ, было, стало in названия[:5]:
        print(f"   русское название пропало: {ключ} {было!r} → {стало!r}")
    for ключ, было, стало in латиница[:5]:
        print(f"   название изменено: {ключ} {было!r} → {стало!r}")

    # Постеров и названий может не быть у записи ИЗНАЧАЛЬНО — это не потеря, а
    # свойство источника. Считается отдельно, чтобы одно не выдавали за другое.
    без_постера = sum(1 for з in новые.values() if not str(з.get("poster") or "").strip())
    без_кириллицы = sum(1 for з in новые.values()
                        if not КИРИЛЛИЦА.search(str(з.get("title") or "")))
    print(f"\nв новом поколении без постера: {без_постера} из {len(новые)}")
    print(f"в новом поколении без кириллицы в названии: {без_кириллицы} из {len(новые)}")
    return 1 if (исчезли or постеры or названия) else 0


def prejniy_exists(путь: pathlib.Path) -> bool:
    return путь.is_file()


if __name__ == "__main__":
    raise SystemExit(главное())
