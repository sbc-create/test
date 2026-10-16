#!/usr/bin/env python3
"""Заполненность поля считается по ЗНАЧЕНИЯМ, а не по строкам.

Зачем. Линия SEO чуть не поставила оценку в описание 7 299 страниц, потому
что таблица `external_rating` покрывает все произведения: 14 598 строк,
`entity_id` заполнен на 100 %. Но у 14 161 строки `status = ABSENT`, и
настоящая оценка есть у 278 произведений из 7 299 — **3,8 %**. Проверено мною
независимо на том же файле: ABSENT 14 161, OK 437, из них imdb 261 и kp 176.

Правило, выведенное из этого: у поля со статусом охват по строкам ничего не
говорит об охвате по значениям, и «поле есть» — не то же самое, что «значение
есть». Инструмент считает второе.

Что считается пустым значением, кроме `null` и пустой строки: пометки
отсутствия (`ABSENT`, `UNKNOWN`, `N/A`, `NONE`, `-`, `—`, `0000-00-00`) и ноль
там, где ноль не бывает значением (оценка, длительность, число серий).

    # JSON-снимок каталога
    python3 automation/local/field-coverage.py --json /srv/zonafilm-space/data/zona-01-details.json
    # sqlite: таблица и, если есть, столбец статуса
    python3 automation/local/field-coverage.py --sqlite /srv/yummyani-site/data/yummy-readmodel.sqlite3 \
        --table entity --table external_rating:status:entity_id
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

#: Пометки отсутствия: выглядят как значение, значением не являются.
ПОМЕТКИ_ОТСУТСТВИЯ = {
    "absent", "unknown", "n/a", "na", "none", "null", "nil", "-", "—", "–",
    "", "0000-00-00", "undefined", "pending", "error", "failed",
}

#: Поля, где ноль не бывает значением.
НОЛЬ_НЕ_ЗНАЧЕНИЕ = {"value", "imdb_rating", "kinopoisk_rating", "duration",
                    "episodes_released", "votes", "year", "seasons_count"}


def пусто(поле: str, значение) -> bool:
    if значение is None:
        return True
    if isinstance(значение, (list, tuple, dict, set)):
        return len(значение) == 0
    if isinstance(значение, (int, float)):
        return поле in НОЛЬ_НЕ_ЗНАЧЕНИЕ and float(значение) == 0
    текст = str(значение).strip()
    return текст.lower() in ПОМЕТКИ_ОТСУТСТВИЯ


def по_json(путь: Path) -> None:
    д = json.loads(путь.read_text(encoding="utf-8"))
    записи = д.get("details") if isinstance(д, dict) else д
    если_словарь = isinstance(записи, dict)
    значения = list(записи.values()) if если_словарь else list(записи)
    всего = len(значения)
    поля: dict[str, int] = {}
    for з in значения:
        if not isinstance(з, dict):
            continue
        for поле, значение in з.items():
            if not пусто(поле, значение):
                поля[поле] = поля.get(поле, 0) + 1
    print(f"{путь}\nзаписей: {всего}\n")
    print(f"{'поле':28s} {'со значением':>12s} {'доля':>7s}")
    for поле, n in sorted(поля.items(), key=lambda кв: -кв[1]):
        print(f"{поле:28s} {n:12d} {100 * n / всего:6.1f}%")


def по_sqlite(путь: Path, таблицы: list[str]) -> None:
    c = sqlite3.connect(f"file:{путь}?mode=ro", uri=True)
    print(f"{путь}\n")
    for описание in таблицы:
        части = описание.split(":")
        таблица = части[0]
        столбец_статуса = части[1] if len(части) > 1 else ""
        ключ_сущности = части[2] if len(части) > 2 else ""
        строк = c.execute(f"select count(*) from {таблица}").fetchone()[0]
        столбцы = [r[1] for r in c.execute(f"pragma table_info({таблица})")]
        print(f"== {таблица}: строк {строк}")
        if столбец_статуса and столбец_статуса in столбцы:
            по_статусу = c.execute(
                f"select {столбец_статуса}, count(*) from {таблица} "
                f"group by {столбец_статуса}").fetchall()
            print(f"   по статусу {столбец_статуса}: {по_статусу}")
            годных = sum(n for с, n in по_статусу
                         if not пусто(столбец_статуса, с))
            всего_сущностей = None
            if ключ_сущности and ключ_сущности in столбцы:
                всего_сущностей = c.execute(
                    f"select count(distinct {ключ_сущности}) from {таблица}"
                ).fetchone()[0]
            print(f"   строк со значением: {годных} "
                  f"({100 * годных / строк:.1f}% строк таблицы)")
            if ключ_сущности and ключ_сущности in столбцы:
                # Сравнение в НИЖНЕМ регистре и с обрезкой пробелов: без
                # этого запрос не нашёл ни одной пометки («ABSENT» против
                # «absent» в списке) и объявил охват 100 % вместо 3,8 %.
                # Ошибка той же природы, что и сам измеряемый дефект.
                разных = c.execute(
                    f"select count(distinct {ключ_сущности}) from {таблица} "
                    f"where lower(trim(cast({столбец_статуса} as text))) "
                    f"not in ({','.join('?' * len(ПОМЕТКИ_ОТСУТСТВИЯ))})",
                    tuple(ПОМЕТКИ_ОТСУТСТВИЯ)).fetchone()[0]
                доля = (100 * разных / всего_сущностей) if всего_сущностей else 0
                print(f"   РАЗНЫХ сущностей со значением: {разных} из "
                      f"{всего_сущностей} ({доля:.1f} %) — именно это число и "
                      f"есть охват, а не доля строк")
        else:
            for поле in столбцы:
                n = c.execute(
                    f"select count(*) from {таблица} where {поле} is not null "
                    f"and trim(cast({поле} as text)) <> '' "
                    f"and lower(trim(cast({поле} as text))) not in "
                    f"({','.join('?' * len(ПОМЕТКИ_ОТСУТСТВИЯ))})",
                    tuple(ПОМЕТКИ_ОТСУТСТВИЯ)).fetchone()[0]
                print(f"   {поле:26s} {n:8d} {100 * n / строк:6.1f}%")
        print()


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--json", type=Path)
    р.add_argument("--sqlite", type=Path)
    р.add_argument("--table", action="append", default=[],
                   help="имя[:столбец_статуса[:ключ_сущности]]")
    опции = р.parse_args(аргв)
    if not опции.json and not опции.sqlite:
        р.error("нужен --json или --sqlite")
    if опции.json:
        по_json(опции.json)
    if опции.sqlite:
        по_sqlite(опции.sqlite, опции.table or ["entity"])
    print("пометки отсутствия считаются пустым значением: "
          + ", ".join(sorted(x for x in ПОМЕТКИ_ОТСУТСТВИЯ if x)[:8]) + " …")
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
