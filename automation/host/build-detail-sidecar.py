#!/usr/bin/env python3
"""Боковой файл подробностей витрины: slug → то, из чего состоит страница тайтла.

## Зачем он нужен

Снимок каталога витрины (`<site>-catalog.json`) знает про запись семь полей:
slug, название, постер, вид, год и две даты. Страницу произведения из этого не
собрать — в ней нет ни описания, ни жанров, ни страны, ни сезонов, ни оценок.
Именно поэтому страницы тайтлов до сих пор отдавались из старого статического
релиза, а витрина, чей снимок ушёл вперёд релиза, отвечала на КАЖДУЮ карточку
404. На zonafilm.space так ломались все 3868 карточек разом.

Подробности при этом давно лежат на диске: обогащение
(`factory/lords/detail_enrichment.py`) складывает ответы detail API в
`var/lords/detail-cache/<external_id>.json`. Не хватало только связи между
снимком каталога и этим кэшем.

## Как связываются snapshot и кэш

Через UUID в адресе постера: `https://poster.cdnvideohub.com/<id>.webp` — это
тот же `<external_id>`, которым назван файл кэша. Связь взята из самих данных,
а не назначена: поле `detail.poster_url` кэша совпадает с полем `poster`
снимка байт в байт.

Записи без UUID в постере (их сотни на витрину) просто не получают
подробностей. Это честный исход: страница у них всё равно будет — на тех
полях, которые есть.

## Что сюда НЕ попадает

Ничего, чего нет в источнике. Отсутствующее описание не заменяется на
сгенерированное, пустой жанр не угадывается по названию, оценка без значения
не превращается в ноль. Поле, которого нет, в боковом файле отсутствует, и
шаблон покажет его отсутствие, а не выдумку.

`crew` обрезается до пятнадцати человек: страница печатает не больше, а
несколько тысяч записей по сорок имён превращают боковой файл в обузу без
единого нового факта на экране.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

#: Поля, которые переносятся в боковой файл. Список закрытый: «перенести всё»
#: означало бы тащить в рантайм поля, которых страница не показывает, и
#: разбираться в них уже на живой витрине.
ПОЛЯ = (
    "description", "short_description", "original_name", "english_name",
    "countries", "genres", "genre_codes", "duration", "premiere_date",
    "seasons", "seasons_count", "year_end", "voice_studios",
    "kinopoisk_rating", "imdb_rating", "external_ids", "is_series",
    "backdrop_url", "licensed",
)

#: Сколько человек съёмочной группы переносится.
ЛЮДЕЙ = 15

UUID = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")


def внешний_ид(постер: str) -> str:
    """UUID записи из адреса постера. Пусто — значит связи нет."""
    совпало = UUID.search(постер or "")
    return совпало.group(1) if совпало else ""


def очистить(значение):
    """Пустое значение — это отсутствие, а не значение.

    Пустой список жанров, пустая строка описания и `null` оценки обязаны
    ИСЧЕЗНУТЬ из бокового файла. Иначе шаблон получит поле, проверит «оно
    есть» и напечатает пустое место как факт.
    """
    if значение is None:
        return None
    if isinstance(значение, str):
        значение = значение.strip()
        return значение or None
    if isinstance(значение, (list, tuple)):
        очищенное = [э for э in значение if э not in (None, "", [], {})]
        return очищенное or None
    if isinstance(значение, dict):
        очищенное = {к: з for к, з in значение.items() if з not in (None, "", [], {})}
        return очищенное or None
    return значение


def сезоны(сырые) -> list | None:
    """Сезоны в том виде, в каком их печатает страница.

    Номер сезона источник отдаёт строкой. Приводится к целому здесь, один раз:
    сравнение «"10" < "9"» верно для строк и ложно для сезонов, и разбираться
    с этим в шаблоне — значит разбираться с этим на каждой странице.
    """
    if not isinstance(сырые, list):
        return None
    готовые = []
    for сезон in сырые:
        if not isinstance(сезон, dict):
            continue
        try:
            номер = int(str(сезон.get("number")).strip())
        except (TypeError, ValueError):
            continue
        всего = сезон.get("episodes_count")
        доступно = сезон.get("available_episodes_count")
        try:
            всего = int(всего)
        except (TypeError, ValueError):
            всего = 0
        try:
            доступно = int(доступно)
        except (TypeError, ValueError):
            доступно = 0
        if номер < 1 or всего < 1:
            continue
        # Доступных не бывает больше, чем всего: источник иногда отдаёт
        # рассогласованную пару, и без этой обрезки страница обещала бы серии,
        # которых нет даже по её собственному счёту.
        готовые.append({"n": номер, "eps": всего, "avail": min(доступно, всего)})
    готовые.sort(key=lambda с: с["n"])
    return готовые or None


def подробность(запись: dict) -> dict:
    """Одна запись бокового файла."""
    итог = {}
    for поле in ПОЛЯ:
        значение = очистить(запись.get(поле))
        if значение is None:
            continue
        if поле == "seasons":
            значение = сезоны(значение)
            if not значение:
                continue
        итог[поле] = значение
    команда = запись.get("crew")
    if isinstance(команда, list):
        люди = [
            {"role": str(ч.get("role") or ""), "name": str(ч.get("person_name") or "")}
            for ч in команда[:ЛЮДЕЙ]
            if isinstance(ч, dict) and ч.get("person_name")
        ]
        if люди:
            итог["crew"] = люди
    return итог


def собрать(каталог: Path, кэш: Path) -> dict:
    снимок = json.loads(каталог.read_text(encoding="utf-8"))
    записи = снимок.get("items") or []
    подробности: dict[str, dict] = {}
    связей = 0
    for запись in записи:
        ид = внешний_ид(запись.get("poster") or "")
        if not ид:
            continue
        файл = кэш / f"{ид}.json"
        if not файл.is_file():
            continue
        try:
            сырое = json.loads(файл.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        деталь = сырое.get("detail")
        if not isinstance(деталь, dict):
            continue
        готовое = подробность(деталь)
        if not готовое:
            continue
        готовое["id"] = ид
        подробности[запись["slug"]] = готовое
        связей += 1
    return {
        "schema": "nova-details/1.0.0",
        "site": снимок.get("site") or "",
        "catalog_revision": снимок.get("revision") or "",
        "catalog_built_at": снимок.get("builtAt") or "",
        "items_total": len(записи),
        "details_total": связей,
        "source": "detail-cache",
        "details": подробности,
    }


def main(argv=None) -> int:
    разбор = argparse.ArgumentParser(description=__doc__)
    разбор.add_argument("--catalog", required=True, type=Path,
                        help="снимок каталога витрины (<site>-catalog.json)")
    разбор.add_argument("--cache", required=True, type=Path,
                        help="каталог кэша detail API")
    разбор.add_argument("--out", required=True, type=Path)
    арг = разбор.parse_args(argv)

    if not арг.catalog.is_file():
        print(f"нет снимка каталога: {арг.catalog}", file=sys.stderr)
        return 2
    if not арг.cache.is_dir():
        print(f"нет кэша подробностей: {арг.cache}", file=sys.stderr)
        return 2

    собранное = собрать(арг.catalog, арг.cache)
    # Запись через временный файл: витрина читает боковой файл на старте, и
    # перезапуск посреди записи поднял бы её на обрезанном JSON.
    арг.out.parent.mkdir(parents=True, exist_ok=True)
    врем = арг.out.with_suffix(арг.out.suffix + ".tmp")
    врем.write_text(json.dumps(собранное, ensure_ascii=False), encoding="utf-8")
    врем.replace(арг.out)
    доля = (100 * собранное["details_total"] // собранное["items_total"]) if собранное["items_total"] else 0
    print(f"[details] {собранное['site']}: {собранное['details_total']} из "
          f"{собранное['items_total']} ({доля}%) → {арг.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
