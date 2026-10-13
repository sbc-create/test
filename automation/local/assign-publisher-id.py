#!/usr/bin/env python3
"""Назначить витрине `publisher_id` во всех ТРЁХ местах сразу (D177).

Зачем отдельный инструмент. D177 называет три места и требует их согласия:

1. **значение** — файл производителя `/srv/lords/.frontend/player-<site_id>.json`
   (его читает привилегированный исполнитель и копирует в выпуск);
2. **объявление** — `config/site.json: publisher_id_expected` в пакете витрины;
3. **учёт** — `config/site-cells.json: publisher.publisher_id`.

«Правка одного места без остальных возвращается следующей выкладкой» — это не
предупреждение, а измеренный 2026-10-05 случай zonafilm.cc. Руками три места
согласовать можно, но каждая такая правка — новый шанс разойтись, поэтому здесь
они меняются вместе или не меняются вовсе.

Значение публичное, а не секретное: по D138 оно стоит в разметке страницы
атрибутом `data-publisher-id`, и секретом остаётся `api_token`, которого этот
инструмент не касается. Тем не менее номер НЕ печатается — ни в выводе, ни в
сообщениях об отказе: в терминале владельца и в журналах сессии ему делать
нечего, а проверить согласие можно и равенством.

Один номер на несколько домен — РЕШЕНИЕ, а не умолчание. В сети это уже есть
(измерено 2026-10-13: `10252` у пяти домен, `10238` у двух), поэтому запрета
нет; но повторное использование требует `--allow-shared`. Без флага отказ
называет, какой домен уже носит этот номер. Молчаливое совместное
использование однажды уже дало домену чужой идентификатор.

    python3 automation/local/assign-publisher-id.py --site lords-10 --publisher-id ХХХХХ
    python3 automation/local/assign-publisher-id.py --site lords-10 --publisher-id ХХХХХ --apply

Без `--apply` — сухой прогон: печатает, что изменится, и не меняет ничего.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import tempfile
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import registry  # noqa: E402

#: Каталог производителя: здесь лежит значение, которое исполнитель копирует в
#: выпуск. Путь — root-side константа того же исполнителя
#: (`factory/cell/privileged.py::ПЛЕЕР_ПРОИЗВОДИТЕЛЯ`), а не выбор этого файла.
ПРОИЗВОДИТЕЛЬ = Path("/srv/lords/.frontend")


class Отказ(RuntimeError):
    """Назначение не выполнено, и причина названа."""


def проверить_номер(значение: str) -> str:
    """Форма номера и его отзыв поставщиком. Значение в текст отказа не идёт."""
    номер = (значение or "").strip()
    if not номер:
        raise Отказ("BLOCKED_INPUT: номер издателя не передан")
    if not номер.isdigit() or номер.startswith("0"):
        raise Отказ("номер издателя непригоден по форме: ожидаются только цифры "
                    "без ведущего нуля (значение не печатается)")
    try:
        registry.check_publisher_id(номер)
    except registry.RetiredPublisherId as ош:
        raise Отказ(f"номер отозван поставщиком: {ош}") from None
    return номер


def чей_уже(номер: str, кроме: str, path: Path | None = None) -> list[str]:
    """Домены, у которых этот номер уже записан в учёте."""
    итог = []
    for c in registry.all_cells(path):
        if c.site_id == кроме:
            continue
        if str((c.publisher or {}).get("publisher_id") or "") == номер:
            итог.append(c.domain)
    return итог


def _записать_рядом(цель: Path, тело: str, режим: int) -> None:
    """Атомарная запись: обрыв на половине не оставляет негодного JSON."""
    цель.parent.mkdir(parents=True, exist_ok=True)
    fd, врем = tempfile.mkstemp(dir=str(цель.parent), prefix=f".{цель.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as ф:
            ф.write(тело)
        os.chmod(врем, режим)
        os.replace(врем, цель)
    except BaseException:
        Path(врем).unlink(missing_ok=True)
        raise


def назначить(site_id: str, номер: str, *, apply: bool = False,
              allow_shared: bool = False, path: Path | None = None,
              производитель: Path = ПРОИЗВОДИТЕЛЬ) -> dict:
    """Три места или ни одного. Возвращает отчёт без значения номера."""
    номер = проверить_номер(номер)
    try:
        ячейка = registry.resolve(site_id, path)
    except registry.RegistryError as ош:
        raise Отказ(str(ош)) from None

    чужие = чей_уже(номер, ячейка.site_id, path)
    if чужие and not allow_shared:
        raise Отказ(
            f"этот номер уже записан у {', '.join(чужие)}. Один номер на "
            "несколько домен в сети встречается, но это решение владельца, а не "
            "умолчание: повторите с --allow-shared, если так и задумано")

    путь_репо = str((ячейка.repo or {}).get("path") or "").strip()
    if not путь_репо:
        raise Отказ(f"{ячейка.site_id}: в реестре не записан путь репозитория — "
                    "объявлять publisher_id_expected некуда")
    п = Path(путь_репо)
    конфиг = (п if п.is_absolute() else КОРЕНЬ / п) / "config" / "site.json"
    if not конфиг.is_file():
        raise Отказ(f"{ячейка.site_id}: нет {конфиг}")

    данные = json.loads(конфиг.read_text(encoding="utf-8"))
    файл_значения = производитель / f"player-{ячейка.site_id}.json"

    было_объявление = str(данные.get("publisher_id_expected") or "")
    было_значение = ""
    if файл_значения.is_file():
        try:
            было_значение = str(json.loads(
                файл_значения.read_text(encoding="utf-8")).get("publisher_id") or "")
        except (OSError, ValueError):
            было_значение = "(файл не читается как JSON)"
    было_учёт = str((ячейка.publisher or {}).get("publisher_id") or "")

    отчёт = {
        "site_id": ячейка.site_id,
        "domain": ячейка.domain,
        "shared_with": чужие,
        "совпадало_до": {
            "значение": было_значение == номер,
            "объявление": было_объявление == номер,
            "учёт": было_учёт == номер,
        },
        "файл_значения": str(файл_значения),
        "объявление": str(конфиг),
        "применено": bool(apply),
    }
    if all(отчёт["совпадало_до"].values()):
        отчёт["итог"] = "менять нечего: три места уже согласны"
        return отчёт
    if not apply:
        отчёт["итог"] = "сухой прогон: будут приведены к согласию все три места"
        return отчёт

    # 1. значение у производителя
    тело = json.dumps({"publisher_id": номер, "source_mode": "provider-id",
                       "_note": "значение витрины; в git не попадает"},
                      ensure_ascii=False, indent=2) + "\n"
    _записать_рядом(файл_значения, тело, 0o600)

    # 2. объявление в пакете витрины
    данные["publisher_id_expected"] = номер
    _записать_рядом(конфиг, json.dumps(данные, ensure_ascii=False, indent=2) + "\n",
                    0o644)

    # 3. учёт в реестре
    registry.register(dataclasses.replace(
        ячейка, publisher={**(ячейка.publisher or {}),
                           "publisher_id": номер,
                           "publisher_id_ref": "repo://config/site.json#publisher_id_expected",
                           "note": ((ячейка.publisher or {}).get("note") or "")}),
        path=path, replace=True)

    # Сверка ПОСЛЕ записи: отчёт не вправе утверждать согласие, которого нет.
    снова = registry.resolve(ячейка.site_id, path)
    стало = {
        "значение": str(json.loads(файл_значения.read_text(encoding="utf-8"))
                        .get("publisher_id") or "") == номер,
        "объявление": str(json.loads(конфиг.read_text(encoding="utf-8"))
                          .get("publisher_id_expected") or "") == номер,
        "учёт": str((снова.publisher or {}).get("publisher_id") or "") == номер,
    }
    отчёт["совпадает_после"] = стало
    if not all(стало.values()):
        raise Отказ(f"{ячейка.site_id}: после записи согласия нет: {стало}")
    отчёт["итог"] = "три места согласованы"
    return отчёт


def main() -> int:
    р = argparse.ArgumentParser(description="Назначить publisher_id витрине (D177)")
    р.add_argument("--site", required=True, help="site_id ячейки")
    р.add_argument("--publisher-id", required=True,
                   help="номер издателя (значение не печатается)")
    р.add_argument("--apply", action="store_true", help="записать; без флага — сухой прогон")
    р.add_argument("--allow-shared", action="store_true",
                   help="номер уже у другого домена, и так задумано")
    р.add_argument("--registry", help="иной путь к реестру ячеек (для проверок)")
    а = р.parse_args()
    try:
        отчёт = назначить(а.site, а.publisher_id, apply=а.apply,
                          allow_shared=а.allow_shared,
                          path=Path(а.registry) if а.registry else None)
    except Отказ as ош:
        print(f"ОТКАЗ: {ош}", file=sys.stderr)
        return 2
    print(json.dumps(отчёт, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
